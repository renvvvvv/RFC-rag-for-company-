"""Tag and association models."""
import uuid

from sqlalchemy import Column, ForeignKey, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tag(Base):
    """标签表，用于文档和片段分类及权限控制。"""

    __tablename__ = "tags"

    __table_args__ = (
        UniqueConstraint("name", "category", name="uix_tag_name_category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="标签ID",
    )
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="标签名称",
    )
    category: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="标签分类：security/business/auto/permission",
    )
    color: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="标签颜色",
    )
    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="标签描述",
    )


document_tags = Table(
    "document_tags",
    Base.metadata,
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
        comment="文档ID",
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        comment="标签ID",
    ),
)

chunk_tags = Table(
    "chunk_tags",
    Base.metadata,
    Column(
        "chunk_id",
        UUID(as_uuid=True),
        ForeignKey("chunks.id", ondelete="CASCADE"),
        primary_key=True,
        comment="片段ID",
    ),
    Column(
        "tag_id",
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
        comment="标签ID",
    ),
)
