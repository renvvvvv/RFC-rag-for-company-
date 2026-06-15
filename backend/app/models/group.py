"""User group models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserGroup(Base):
    """用户组/部门表，支持层级结构。"""

    __tablename__ = "user_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="用户组ID",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        comment="用户组名称",
    )
    description: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="用户组描述",
    )
    group_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="组类型：department/project/custom",
    )
    parent_group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_groups.id", ondelete="SET NULL"),
        nullable=True,
        comment="父级组ID",
    )
    admin_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="管理员ID列表",
    )
    member_ids: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="成员ID列表",
    )
    max_security_level: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="组内最高安全等级：L0-L4",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="创建者ID",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
