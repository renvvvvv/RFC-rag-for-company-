"""Unit tests for API key scope validation and key hashing."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.exceptions import AuthorizationException
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate
from app.services.api_key_service import ApiKeyService


def test_scopes_for_level():
    assert ApiKeyService.scopes_for_level("L0") == ["kb:read", "search", "chat"]
    assert "doc:write" in ApiKeyService.scopes_for_level("L1")
    assert "kb:write" in ApiKeyService.scopes_for_level("L2")
    assert "apikey:admin" in ApiKeyService.scopes_for_level("L3")
    assert "*" in ApiKeyService.scopes_for_level("L4")


def test_validate_scopes_for_level_defaults():
    assert ApiKeyService.validate_scopes_for_level(["search"], "L0") == ["search"]


def test_validate_scopes_for_level_wildcard():
    assert ApiKeyService.validate_scopes_for_level(["*"], "L4") == ["*"]


def test_validate_scopes_for_level_denied():
    with pytest.raises(AuthorizationException) as exc_info:
        ApiKeyService.validate_scopes_for_level(["kb:write"], "L1")
    assert "kb:write" in str(exc_info.value)


def test_generate_and_verify_key():
    service = ApiKeyService(db=MagicMock())
    plain = service._generate_plain_key()
    assert plain.startswith("rag_live_")
    hashed = service._hash_key(plain)
    assert service._verify_key(plain, hashed) is True
    assert service._verify_key(plain + "x", hashed) is False


def test_key_has_scope():
    key = ApiKey(scopes=["search", "kb:read"])
    assert ApiKeyService.key_has_scope(key, "search") is True
    assert ApiKeyService.key_has_scope(key, "chat") is False

    wildcard = ApiKey(scopes=["*"])
    assert ApiKeyService.key_has_scope(wildcard, "apikey:admin") is True


def test_api_key_create_schema_normalizes_string_scopes():
    payload = ApiKeyCreate(name="test", scopes="search,kb:read")
    assert payload.scopes == ["search", "kb:read"]


@pytest.mark.asyncio
async def test_create_key_denied_scope():
    """L0 owner cannot request kb:write."""
    mock_user = User(
        id="00000000-0000-0000-0000-000000000001",
        username="l0user",
        security_level="L0",
        status="active",
        is_active=True,
    )

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = mock_user
    db = MagicMock()
    db.execute = AsyncMock(return_value=result_mock)

    service = ApiKeyService(db=db)
    with pytest.raises(AuthorizationException):
        await service.create_key(
            owner_id=mock_user.id,
            name="bad-key",
            scopes=["kb:write"],
        )
