"""API Key model for external service access."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import BOOLEAN, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ApiKey(Base):
    """API keys used by external systems to access knowledge base APIs.

    Each key belongs to a user and inherits that user's security level and
    permissions. The raw key is returned only once at creation time; only its
    hash is persisted.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="API Key ID",
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属用户ID",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Key名称，如OA系统集成",
    )
    key_prefix: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        index=True,
        comment="Key前缀，用于展示和日志",
    )
    key_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Key哈希（bcrypt）",
    )
    scopes: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="权限范围列表",
    )
    rate_limit_rpm: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
        comment="每分钟请求上限",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="过期时间",
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="最后使用时间",
    )
    is_active: Mapped[bool] = mapped_column(
        BOOLEAN,
        default=True,
        nullable=False,
        comment="是否激活",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
