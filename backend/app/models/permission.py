"""Permission models for RBAC + ABAC multi-level access control."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FileTypePermission(Base):
    """L1 文件类型权限：基于角色控制可访问/操作的文件类型。"""

    __tablename__ = "file_type_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="权限ID",
    )
    role_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="角色ID",
    )
    file_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="文件类型：PDF/DOCX/EXCEL/VIDEO/AUDIO/IMAGE等",
    )
    permissions: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="权限列表：[READ, UPLOAD, DELETE, ADMIN]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )


class DocumentPermission(Base):
    """L2 文档级别权限：控制用户/组/角色对单篇文档的访问。"""

    __tablename__ = "document_permissions"

    __table_args__ = (
        Index("idx_document_permissions_doc_id", "doc_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="权限ID",
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档ID",
    )
    grantee_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="授权对象类型：user/group/role/all",
    )
    grantee_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="授权对象ID，all时为空",
    )
    permission: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="权限级别：none/read/write/admin",
    )
    inherit_from_kb: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否继承知识库默认权限",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )


class FieldPermission(Base):
    """L3 字段/内容级别权限：Word段落、Excel单元格/列/工作表级可见性控制。"""

    __tablename__ = "field_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="权限ID",
    )
    doc_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="文档ID",
    )
    field_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="字段路径，如段落索引、Excel单元格坐标、列名等",
    )
    field_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="字段类型：word_paragraph/excel_cell/excel_column/excel_sheet",
    )
    allowed_roles: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="允许访问的角色ID列表",
    )
    allowed_groups: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="允许访问的用户组ID列表",
    )
    allowed_users: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="允许访问的用户ID列表",
    )
    denied_roles: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="拒绝访问的角色ID列表",
    )
    denied_groups: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="拒绝访问的用户组ID列表",
    )
    denied_users: Mapped[list] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
        comment="拒绝访问的用户ID列表",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )


class TagPermission(Base):
    """L4 标签级别权限：控制特定标签的可见性。"""

    __tablename__ = "tag_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="权限ID",
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        nullable=False,
        comment="标签ID",
    )
    grantee_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        comment="授权对象类型：user/group/role/all",
    )
    grantee_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="授权对象ID",
    )
    permission: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="deny",
        comment="权限结果：allow/deny",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )


class GroupPermission(Base):
    """用户组级别的资源权限映射。"""

    __tablename__ = "group_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="权限ID",
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        nullable=False,
        comment="用户组ID",
    )
    resource_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="资源类型：knowledge_base/document/field/tag",
    )
    resource_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="资源ID，为空表示对该类型资源的默认权限",
    )
    permission: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
        comment="权限详情",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
