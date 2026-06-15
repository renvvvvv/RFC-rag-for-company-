"""Audit log models."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditLog(Base):
    """全链路审计日志表，覆盖权限检查、敏感词拦截、API调用。"""

    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="日志ID",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="事件发生时间",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="操作类型：search/upload/download/delete/login",
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="操作用户ID",
    )
    user_groups: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="用户所属组ID列表",
    )
    target_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="目标资源类型：knowledge_base/document/chunk/user/audit",
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="目标资源ID",
    )
    user_security_level: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="用户安全等级",
    )
    content_max_level: Mapped[str | None] = mapped_column(
        String(8),
        nullable=True,
        comment="内容最高安全等级",
    )
    keywords_detected: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="检测到的敏感关键词列表",
    )
    permission_result: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        comment="权限判定结果：allow/deny/mask",
    )
    api_provider: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="外部API提供商",
    )
    masking_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否已脱敏",
    )
    intercepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否被拦截",
    )
    intercept_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="拦截原因",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="请求耗时（毫秒）",
    )
    request_summary: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="请求摘要",
    )
    response_summary: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="响应摘要",
    )
