"""Pydantic schemas for collaboration features (comments & bookmarks)."""
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


TARGET_TYPE = Literal["document", "chunk"]


class CommentCreate(BaseModel):
    """创建评论请求体。"""

    target_type: str = Field(
        ...,
        pattern=r"^(document|chunk)$",
        description="评论对象类型：document/chunk",
    )
    target_id: UUID = Field(..., description="评论对象ID")
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="评论内容",
    )
    parent_id: Optional[UUID] = Field(
        default=None,
        description="父评论ID，用于回复",
    )


class CommentUpdate(BaseModel):
    """更新评论请求体。"""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="评论内容",
    )


class CommentResponse(BaseModel):
    """评论响应体。"""

    id: UUID
    user_id: UUID
    target_type: str
    target_id: UUID
    content: str
    parent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BookmarkCreate(BaseModel):
    """创建书签请求体。"""

    target_type: str = Field(
        ...,
        pattern=r"^(document|chunk)$",
        description="收藏对象类型：document/chunk",
    )
    target_id: UUID = Field(..., description="收藏对象ID")
    note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="收藏备注",
    )


class BookmarkResponse(BaseModel):
    """书签响应体。"""

    id: UUID
    user_id: UUID
    target_type: str
    target_id: UUID
    note: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
