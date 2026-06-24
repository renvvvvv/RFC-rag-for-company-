"""API Key lifecycle service.

Generates, validates, and rate-limits external API keys. Keys are stored as
bcrypt hashes; only the plaintext is returned once at creation time.
"""
from __future__ import annotations

import base64
import logging
import secrets
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.redis_client import redis_client
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.permission_service import PermissionService

logger = logging.getLogger(__name__)

API_KEY_PREFIX = "rag_live_"
API_KEY_BYTES = 32

# Scope matrix determined by the owner's security level.
# An API key can never claim a scope outside the owner's level.
ALLOWED_SCOPES_BY_LEVEL: dict[str, list[str]] = {
    "L0": ["kb:read", "search", "chat"],
    "L1": ["kb:read", "search", "chat", "doc:write"],
    "L2": ["kb:read", "search", "chat", "doc:write", "kb:write"],
    "L3": [
        "kb:read",
        "search",
        "chat",
        "doc:write",
        "kb:write",
        "user:read",
        "apikey:admin",
    ],
    "L4": ["*"],
}

# All concrete scopes known to the system. ``*`` means everything.
ALL_SCOPES: set[str] = {
    "kb:read",
    "search",
    "chat",
    "doc:write",
    "kb:write",
    "user:read",
    "apikey:admin",
}


class ApiKeyService:
    """Manage external API keys and perform key-based authentication."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _generate_plain_key() -> str:
        """Return a new plaintext API key with a fixed prefix."""
        token = secrets.token_urlsafe(API_KEY_BYTES)
        return f"{API_KEY_PREFIX}{token}"

    @staticmethod
    def _hash_key(plain_key: str) -> str:
        """Hash a plaintext key with bcrypt."""
        return bcrypt.hashpw(plain_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def _verify_key(plain_key: str, hashed_key: str) -> bool:
        """Verify a plaintext key against a stored bcrypt hash."""
        return bcrypt.checkpw(
            plain_key.encode("utf-8"),
            hashed_key.encode("utf-8"),
        )

    @staticmethod
    def get_prefix(plain_key: str) -> str:
        """Return the first 16 characters of the key for indexing."""
        return plain_key[:16]

    @classmethod
    def scopes_for_level(cls, security_level: str) -> list[str]:
        """Return the scopes an owner at ``security_level`` may assign."""
        return list(ALLOWED_SCOPES_BY_LEVEL.get(security_level.upper(), []))

    @classmethod
    def validate_scopes_for_level(
        cls,
        scopes: Sequence[str],
        security_level: str,
    ) -> list[str]:
        """Validate and normalize requested scopes.

        Raises:
            AuthorizationException: if a scope is not permitted for the level.
        """
        allowed = set(cls.scopes_for_level(security_level))
        if "*" in allowed:
            # L4 owner: all concrete scopes are allowed.
            allowed = ALL_SCOPES | {"*"}

        requested = set(scopes)
        invalid = requested - allowed
        if invalid:
            raise AuthorizationException(
                f"Scopes not permitted for level {security_level}: {sorted(invalid)}"
            )

        # Normalize ``*`` if present; otherwise keep requested concrete scopes.
        if "*" in requested:
            return ["*"]
        return sorted(requested)

    async def create_key(
        self,
        owner_id: UUID,
        name: str,
        scopes: Sequence[str] | None = None,
        rate_limit_rpm: int = 60,
        expires_at: datetime | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a new API key for ``owner_id``.

        Returns:
            A tuple of ``(ApiKey model, plaintext_key)``.
        """
        result = await self.db.execute(select(User).where(User.id == owner_id))
        owner = result.scalar_one_or_none()
        if owner is None:
            raise AuthenticationException("Owner user not found")
        if owner.status != "active" or not owner.is_active:
            raise AuthenticationException("Owner user is disabled")

        normalized_scopes = self.validate_scopes_for_level(
            scopes or self.scopes_for_level(owner.security_level),
            owner.security_level,
        )

        plain_key = self._generate_plain_key()
        key_hash = self._hash_key(plain_key)

        api_key = ApiKey(
            owner_id=owner_id,
            name=name.strip() or "API Key",
            key_prefix=self.get_prefix(plain_key),
            key_hash=key_hash,
            scopes=normalized_scopes,
            rate_limit_rpm=max(1, rate_limit_rpm),
            expires_at=expires_at,
            is_active=True,
        )
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key, plain_key

    async def list_keys(
        self,
        owner_id: UUID,
        include_inactive: bool = False,
    ) -> list[ApiKey]:
        """List API keys belonging to ``owner_id``."""
        stmt = select(ApiKey).where(ApiKey.owner_id == owner_id)
        if not include_inactive:
            stmt = stmt.where(ApiKey.is_active.is_(True))
        stmt = stmt.order_by(ApiKey.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_key(self, key_id: UUID, owner_id: UUID | None = None) -> ApiKey | None:
        """Fetch a single API key, optionally scoped to an owner."""
        stmt = select(ApiKey).where(ApiKey.id == key_id)
        if owner_id is not None:
            stmt = stmt.where(ApiKey.owner_id == owner_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_key(self, key_id: UUID, owner_id: UUID) -> bool:
        """Soft-delete (deactivate) an API key."""
        api_key = await self.get_key(key_id, owner_id)
        if api_key is None:
            return False
        api_key.is_active = False
        await self.db.commit()
        return True

    async def authenticate_key(self, plain_key: str) -> ApiKey:
        """Validate a plaintext API key and enforce rate limits.

        Raises:
            AuthenticationException: if the key is invalid, expired,
                deactivated, or rate limited.
        """
        prefix = self.get_prefix(plain_key)
        result = await self.db.execute(
            select(ApiKey).where(
                ApiKey.key_prefix == prefix,
                ApiKey.is_active.is_(True),
            )
        )
        candidates = result.scalars().all()

        api_key: ApiKey | None = None
        for candidate in candidates:
            if self._verify_key(plain_key, candidate.key_hash):
                api_key = candidate
                break

        if api_key is None:
            raise AuthenticationException("Invalid API key")

        if api_key.expires_at is not None and api_key.expires_at < datetime.now(timezone.utc):
            raise AuthenticationException("API key has expired")

        await self._check_rate_limit(api_key)

        api_key.last_used_at = datetime.now(timezone.utc)
        await self.db.commit()
        return api_key

    async def _check_rate_limit(self, api_key: ApiKey) -> None:
        """Enforce per-minute rate limit using a Redis counter.

        Degrades gracefully if Redis is unavailable.
        """
        rpm = api_key.rate_limit_rpm
        window = 60
        key = f"apikey_ratelimit:{api_key.id}:{self._current_minute()}"

        try:
            current = await redis_client.incr(key)
            if current == 1:
                await redis_client.expire(key, window)

            if current is not None and current > rpm:
                raise AuthenticationException(
                    f"Rate limit exceeded: {rpm} requests per minute"
                )
        except AuthenticationException:
            raise
        except Exception as exc:  # pragma: no cover - Redis failures
            logger.warning("API key rate limit check failed: %s", exc)

    @staticmethod
    def _current_minute() -> str:
        """Return the current UTC minute as a sortable string."""
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

    @staticmethod
    def key_has_scope(api_key: ApiKey, scope: str) -> bool:
        """Return True if ``api_key`` may act on ``scope``."""
        if not api_key.scopes:
            return False
        if "*" in api_key.scopes:
            return True
        return scope in api_key.scopes

    async def load_owner(self, api_key: ApiKey) -> User:
        """Load the owner user for an authenticated API key."""
        result = await self.db.execute(select(User).where(User.id == api_key.owner_id))
        owner = result.scalar_one_or_none()
        if owner is None or owner.status != "active" or not owner.is_active:
            raise AuthenticationException("API key owner is disabled")
        return owner

    async def permission_service(self) -> PermissionService:
        """Return a PermissionService instance bound to the same session."""
        return PermissionService(self.db)
