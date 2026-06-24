"""Pydantic schemas for API key management."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApiKeyBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] = Field(default_factory=list)
    rate_limit_rpm: int = Field(default=60, ge=1, le=10000)
    expires_at: datetime | None = None


class ApiKeyCreate(ApiKeyBase):
    """Request schema for creating an API key."""

    @field_validator("scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v)


class ApiKeyUpdate(BaseModel):
    """Request schema for updating an API key (currently only name)."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    """Public API key metadata returned by list/get endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    rate_limit_rpm: int
    expires_at: datetime | None
    last_used_at: datetime | None
    is_active: bool
    created_at: datetime


class ApiKeyCreateResponse(ApiKeyResponse):
    """Response schema that includes the plaintext key exactly once."""

    plain_key: str
