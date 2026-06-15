"""Pydantic schemas for sensitive keyword management."""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


LEVEL_PATTERN = r"^L[0-4]$"
MATCH_TYPE_PATTERN = r"^(exact|fuzzy|regex)$"
ACTION_PATTERN = r"^(audit|block|mask)$"


class SensitiveKeywordBase(BaseModel):
    """Shared fields for sensitive keyword schemas."""

    keyword: str = Field(..., max_length=255, description="关键词")
    level: str = Field(
        default="L1",
        pattern=LEVEL_PATTERN,
        description="敏感等级：L0-L4",
    )
    category: Optional[str] = Field(
        default=None,
        max_length=64,
        description="分类：confidential/privacy/compliance/custom",
    )
    match_type: str = Field(
        default="exact",
        pattern=MATCH_TYPE_PATTERN,
        description="匹配方式：exact/fuzzy/regex",
    )
    variants: List[str] = Field(
        default_factory=list,
        description="关键词变体列表，例如 ['工资', '薪酬', '月收入']",
    )
    apply_to_modalities: List[str] = Field(
        default_factory=list,
        description="适用的模态：[text/image/audio/video/table]",
    )
    action: str = Field(
        default="audit",
        pattern=ACTION_PATTERN,
        description="命中动作：block/mask/audit",
    )

    @field_validator("variants", "apply_to_modalities", mode="before")
    @classmethod
    def _ensure_list(cls, value):
        if value is None:
            return []
        return value


class SensitiveKeywordCreate(SensitiveKeywordBase):
    """Schema for creating a new sensitive keyword."""

    pass


class SensitiveKeywordUpdate(BaseModel):
    """Schema for updating an existing sensitive keyword."""

    keyword: Optional[str] = Field(default=None, max_length=255)
    level: Optional[str] = Field(default=None, pattern=LEVEL_PATTERN)
    category: Optional[str] = Field(default=None, max_length=64)
    match_type: Optional[str] = Field(default=None, pattern=MATCH_TYPE_PATTERN)
    variants: Optional[List[str]] = None
    apply_to_modalities: Optional[List[str]] = None
    action: Optional[str] = Field(default=None, pattern=ACTION_PATTERN)


class SensitiveKeywordResponse(SensitiveKeywordBase):
    """Schema returned by the API."""

    id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
