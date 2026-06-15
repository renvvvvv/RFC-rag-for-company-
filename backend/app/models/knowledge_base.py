"""Knowledge base models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KnowledgeBase(Base):
    """知识库表。"""

    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="知识库ID",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="知识库名称",
    )
    description: Mapped[str | None] = mapped_column(
        String(1024),
        nullable=True,
        comment="知识库描述",
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="所有者ID",
    )
    config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="知识库配置：embedding模型、分块策略等",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        comment="状态：active/inactive/archived",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
