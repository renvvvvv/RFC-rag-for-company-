"""Sensitive keyword detection models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SensitiveKeyword(Base):
    """敏感关键词表，支持多模态匹配。"""

    __tablename__ = "sensitive_keywords"

    __table_args__ = (
        Index("idx_sensitive_keywords_keyword", "keyword"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="关键词ID",
    )
    keyword: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="关键词",
    )
    level: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="L1",
        comment="敏感等级：L0-L4",
    )
    category: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="分类：confidential/privacy/compliance/custom",
    )
    match_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="exact",
        comment="匹配方式：exact/fuzzy/regex",
    )
    variants: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="关键词变体列表",
    )
    apply_to_modalities: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="适用的模态：[text/image/audio/video]",
    )
    action: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="audit",
        comment="命中动作：block/mask/audit",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )


class KeywordMatchLog(Base):
    """敏感关键词命中日志。"""

    __tablename__ = "keyword_match_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="日志ID",
    )
    keyword_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensitive_keywords.id", ondelete="SET NULL"),
        nullable=True,
        comment="命中关键词ID",
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="来源类型：document/chunk/audit",
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="来源ID",
    )
    matched_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="命中文本片段",
    )
    matched_variant: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="命中的变体形式",
    )
    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="匹配置信度",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
