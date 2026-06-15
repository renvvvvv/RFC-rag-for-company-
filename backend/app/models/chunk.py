"""Document chunk models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Chunk(Base):
    """文档片段表，支持多模态和全文检索。"""

    __tablename__ = "chunks"

    __table_args__ = (
        Index("idx_chunks_doc_id", "doc_id"),
        Index("idx_chunks_content_tsv", "content_tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="片段ID",
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档ID",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="片段文本内容",
    )
    modality: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="模态类型：text/image/audio/video/table",
    )
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="片段在文档中的序号",
    )
    position_info: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="位置信息：页码、段落、单元格坐标等",
    )
    vector_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="向量数据库中的ID",
    )
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        nullable=True,
        comment="PostgreSQL全文检索向量",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        comment="片段元数据：max_keyword_level/sensitive_keywords/tags",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        comment="状态：active/inactive/deprecated",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
