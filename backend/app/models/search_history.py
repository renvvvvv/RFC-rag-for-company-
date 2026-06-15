"""Search history model for audit and recent-query retrieval."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SearchHistory(Base):
    """用户搜索历史表。"""

    __tablename__ = "search_history"

    __table_args__ = (
        # Most common query: recent searches for a given user.
        # Also supports filtering by search mode.
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="搜索历史ID",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="用户ID",
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="查询文本",
    )
    mode: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="hybrid",
        comment="检索模式：hybrid/semantic/keyword",
    )
    kb_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="知识库ID列表",
    )
    result_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="返回结果数量",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        comment="附加元数据：top_k, rerank_top_k, modalities 等",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="搜索时间",
    )
