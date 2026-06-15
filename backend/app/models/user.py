"""User and authentication models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """系统用户表。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="用户ID",
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="用户名",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="邮箱地址",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="密码哈希",
    )
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="角色ID（RBAC角色）",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="显示名称",
    )
    department: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="所属部门",
    )
    security_level: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="L0",
        comment="安全等级：L0-L4",
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="active",
        comment="用户状态：active/inactive/locked",
    )
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
        comment="是否激活",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
