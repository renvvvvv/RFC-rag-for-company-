"""Document models."""
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    """文档表，保存原始文件元数据和处理状态。"""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="文档ID",
    )
    kb_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=True,
        comment="所属知识库ID",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="原始文件名",
    )
    file_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="文件类型：PDF/DOCX/XLSX/PPT/TXT/MARKDOWN/HTML/VIDEO/AUDIO/IMAGE",
    )
    file_size: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment="文件大小（字节）",
    )
    mime_type: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="MIME类型",
    )
    storage_key: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="对象存储Key",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        comment="状态：pending/processing/indexed/failed/stored_only",
    )
    processing_info: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="处理信息：进度、错误、分块配置等",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        nullable=False,
        comment="文档元数据",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="上传者ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
