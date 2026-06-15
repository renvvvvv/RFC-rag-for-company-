"""Collaboration models: comments and bookmarks on documents/chunks."""
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Comment(Base):
    """用户评论/回复表，支持对文档或片段进行讨论。"""

    __tablename__ = "comments"

    __table_args__ = (
        Index("idx_comments_target", "target_type", "target_id"),
        Index("idx_comments_user_id", "user_id"),
        Index("idx_comments_parent_id", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="评论ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="评论用户ID",
    )
    target_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="评论对象类型：document/chunk",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="评论对象ID（文档或片段）",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="评论内容",
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,
        comment="父评论ID，用于回复",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )


class Bookmark(Base):
    """用户书签/收藏表，支持对文档或片段进行收藏。"""

    __tablename__ = "bookmarks"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "target_type", "target_id", name="uix_bookmark_user_target"
        ),
        Index("idx_bookmarks_user_id", "user_id"),
        Index("idx_bookmarks_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="书签ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户ID",
    )
    target_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="收藏对象类型：document/chunk",
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        comment="收藏对象ID（文档或片段）",
    )
    note: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="收藏备注",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
