"""High-level permission cache manager built on top of ``RedisClient``.

All methods are async and degrade gracefully when Redis is unavailable:
they return ``None`` (or an empty container) instead of raising exceptions.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.redis_client import redis_client, RedisClient

logger = logging.getLogger(__name__)

DEFAULT_USER_TTL = 300
DEFAULT_FIELD_TTL = 600
DEFAULT_ACL_VERSION_TTL = 86400  # 1 day


class CacheManager:
    """Caches ACL/permission data with the ``rag_kb:`` key prefix."""

    def __init__(self, client: RedisClient = redis_client) -> None:
        self._r = client

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _json_loads(value: str | None) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.warning("Failed to decode cached JSON: %s", value)
            return None

    @staticmethod
    def _json_dumps(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

    # ------------------------------------------------------------------ #
    # User ↔ Document permission
    # ------------------------------------------------------------------ #
    @staticmethod
    def _user_doc_key(user_id: str | int, doc_id: str | int) -> str:
        return f"user_doc_permission:{user_id}:{doc_id}"

    async def get_user_doc_permission(
        self,
        user_id: str | int,
        doc_id: str | int,
    ) -> str | None:
        """Return ALLOW/DENY/PARTIAL, or ``None`` if not cached."""
        return await self._r.get(self._user_doc_key(user_id, doc_id))

    async def set_user_doc_permission(
        self,
        user_id: str | int,
        doc_id: str | int,
        permission: str,
        ttl: int = DEFAULT_USER_TTL,
    ) -> bool | None:
        return await self._r.setex(
            self._user_doc_key(user_id, doc_id),
            permission,
            ttl,
        )

    # ------------------------------------------------------------------ #
    # User tag permission
    # ------------------------------------------------------------------ #
    @staticmethod
    def _user_tag_key(user_id: str | int) -> str:
        return f"user_tag_permission:{user_id}"

    async def get_user_tag_permission(
        self,
        user_id: str | int,
    ) -> dict[str, list[str]] | None:
        """Return ``{'allowed': [...], 'denied': [...]}`` or ``None``."""
        data = await self._r.hgetall(self._user_tag_key(user_id))
        if not data:
            return None
        return {
            "allowed": self._json_loads(data.get("allowed", "[]")),
            "denied": self._json_loads(data.get("denied", "[]")),
        }

    async def set_user_tag_permission(
        self,
        user_id: str | int,
        permissions: dict[str, list[str]],
        ttl: int = DEFAULT_USER_TTL,
    ) -> bool | None:
        """Cache tag permissions using a hash + EXPIRE via pipeline."""
        allowed = permissions.get("allowed", [])
        denied = permissions.get("denied", [])
        key = self._user_tag_key(user_id)

        return await self._set_hash_with_ttl(
            key,
            {"allowed": self._json_dumps(allowed), "denied": self._json_dumps(denied)},
            ttl,
        )

    # ------------------------------------------------------------------ #
    # Field-level permission
    # ------------------------------------------------------------------ #
    @staticmethod
    def _user_field_key(doc_id: str | int, user_id: str | int) -> str:
        return f"user_field_permission:{doc_id}:{user_id}"

    async def get_user_field_permission(
        self,
        doc_id: str | int,
        user_id: str | int,
    ) -> dict[str, Any] | None:
        """Return the cached field-permission config dict, or ``None``."""
        raw = await self._r.get(self._user_field_key(doc_id, user_id))
        return self._json_loads(raw)

    async def set_user_field_permission(
        self,
        doc_id: str | int,
        user_id: str | int,
        config: dict[str, Any],
        ttl: int = DEFAULT_FIELD_TTL,
    ) -> bool | None:
        return await self._r.setex(
            self._user_field_key(doc_id, user_id),
            self._json_dumps(config),
            ttl,
        )

    # ------------------------------------------------------------------ #
    # Allowed file types
    # ------------------------------------------------------------------ #
    @staticmethod
    def _user_file_types_key(user_id: str | int) -> str:
        return f"user_file_types:{user_id}"

    async def get_user_file_types(
        self,
        user_id: str | int,
    ) -> set[str] | None:
        return await self._r.smembers(self._user_file_types_key(user_id))

    async def set_user_file_types(
        self,
        user_id: str | int,
        file_types: list[str] | set[str],
        ttl: int = DEFAULT_USER_TTL,
    ) -> bool | None:
        """Cache file types as a Redis set with TTL via pipeline."""
        key = self._user_file_types_key(user_id)
        members = list(set(file_types))

        pipe = await self._r.pipeline()
        if pipe is None:
            return None

        if members:
            pipe.sadd(key, *members)
        # EXPIRE works on the key regardless of its type (set/string).
        pipe.expire(key, ttl)
        result = await pipe.execute()
        return result is not None

    # ------------------------------------------------------------------ #
    # Security level
    # ------------------------------------------------------------------ #
    @staticmethod
    def _user_security_level_key(user_id: str | int) -> str:
        return f"user_security_level:{user_id}"

    async def get_user_security_level(
        self,
        user_id: str | int,
    ) -> str | None:
        return await self._r.get(self._user_security_level_key(user_id))

    async def set_user_security_level(
        self,
        user_id: str | int,
        level: str,
        ttl: int = DEFAULT_USER_TTL,
    ) -> bool | None:
        return await self._r.setex(
            self._user_security_level_key(user_id),
            level,
            ttl,
        )

    # ------------------------------------------------------------------ #
    # Document ACL version
    # ------------------------------------------------------------------ #
    @staticmethod
    def _doc_acl_version_key(doc_id: str | int) -> str:
        return f"doc_acl_version:{doc_id}"

    async def get_doc_acl_version(
        self,
        doc_id: str | int,
    ) -> str | None:
        return await self._r.get(self._doc_acl_version_key(doc_id))

    async def set_doc_acl_version(
        self,
        doc_id: str | int,
        version: str,
        ttl: int = DEFAULT_ACL_VERSION_TTL,
    ) -> bool | None:
        return await self._r.setex(
            self._doc_acl_version_key(doc_id),
            version,
            ttl,
        )

    # ------------------------------------------------------------------ #
    # Invalidation
    # ------------------------------------------------------------------ #
    async def invalidate_user_cache(self, user_id: str | int) -> int | None:
        """Remove all cached entries related to ``user_id``.

        Returns the total number of keys removed, or ``None`` on Redis error.
        """
        patterns = [
            f"user_doc_permission:{user_id}:*",
            f"user_tag_permission:{user_id}",
            f"user_field_permission:*:{user_id}",
            f"user_file_types:{user_id}",
            f"user_security_level:{user_id}",
        ]
        total = 0
        for pattern in patterns:
            count = await self._r.scan_delete(pattern)
            if count is None:
                return None
            total += count
        return total

    async def invalidate_document_cache(self, doc_id: str | int) -> int | None:
        """Remove all cached entries related to ``doc_id``.

        Returns the total number of keys removed, or ``None`` on Redis error.
        """
        patterns = [
            f"user_doc_permission:*:{doc_id}",
            f"user_field_permission:{doc_id}:*",
            f"doc_acl_version:{doc_id}",
        ]
        total = 0
        for pattern in patterns:
            count = await self._r.scan_delete(pattern)
            if count is None:
                return None
            total += count
        return total

    # ------------------------------------------------------------------ #
    # Internal helpers using pipeline
    # ------------------------------------------------------------------ #
    async def _set_hash_with_ttl(
        self,
        key: str,
        fields: dict[str, str],
        ttl: int,
    ) -> bool | None:
        """Set hash fields and expire the key, using a pipeline."""
        pipe = await self._r.pipeline()
        if pipe is None:
            return None

        for field, value in fields.items():
            pipe.hset(key, field, value)
        pipe.expire(key, ttl)
        result = await pipe.execute()
        return result is not None
