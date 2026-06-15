"""Initial schema for enterprise private multimodal RAG.

Revision ID: 20260610_init
Revises:
Create Date: 2026-06-10 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260610_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === users ===
    op.create_table(
        "users",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("security_level", sa.String(length=8), server_default=sa.text("'L0'"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )

    # === user_groups ===
    op.create_table(
        "user_groups",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("group_type", sa.String(length=32), nullable=True),
        sa.Column(
            "parent_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_groups.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("admin_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("member_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("max_security_level", sa.String(length=8), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # === knowledge_bases ===
    op.create_table(
        "knowledge_bases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("config", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === documents ===
    op.create_table(
        "documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "kb_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column(
            "processing_info",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === chunks ===
    op.create_table(
        "chunks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("modality", sa.String(length=16), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column(
            "position_info",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("vector_id", sa.String(length=255), nullable=True),
        sa.Column("content_tsv", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === tags ===
    op.create_table(
        "tags",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "category", name="uix_tag_name_category"),
    )

    # === document_tags ===
    op.create_table(
        "document_tags",
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("document_id", "tag_id"),
    )

    # === chunk_tags ===
    op.create_table(
        "chunk_tags",
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("chunk_id", "tag_id"),
    )

    # === file_type_permissions ===
    op.create_table(
        "file_type_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column(
            "permissions",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === document_permissions ===
    op.create_table(
        "document_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grantee_type", sa.String(length=16), nullable=False),
        sa.Column("grantee_id", sa.String(length=64), nullable=True),
        sa.Column("permission", sa.String(length=16), nullable=False),
        sa.Column(
            "inherit_from_kb",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === field_permissions ===
    op.create_table(
        "field_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "doc_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("field_path", sa.String(length=512), nullable=False),
        sa.Column("field_type", sa.String(length=32), nullable=False),
        sa.Column("allowed_roles", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("allowed_groups", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("allowed_users", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("denied_roles", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("denied_groups", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("denied_users", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === tag_permissions ===
    op.create_table(
        "tag_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("grantee_type", sa.String(length=16), nullable=False),
        sa.Column("grantee_id", sa.String(length=64), nullable=True),
        sa.Column("permission", sa.String(length=16), server_default=sa.text("'deny'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === group_permissions ===
    op.create_table(
        "group_permissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("permission", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === sensitive_keywords ===
    op.create_table(
        "sensitive_keywords",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(length=255), nullable=False),
        sa.Column("level", sa.String(length=8), server_default=sa.text("'L1'"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("match_type", sa.String(length=16), server_default=sa.text("'exact'"), nullable=False),
        sa.Column("variants", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "apply_to_modalities",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("action", sa.String(length=16), server_default=sa.text("'audit'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === keyword_match_logs ===
    op.create_table(
        "keyword_match_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "keyword_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sensitive_keywords.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("matched_text", sa.Text(), nullable=True),
        sa.Column("matched_variant", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === audit_logs ===
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("user_groups", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_security_level", sa.String(length=8), nullable=True),
        sa.Column("content_max_level", sa.String(length=8), nullable=True),
        sa.Column(
            "keywords_detected",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("permission_result", sa.String(length=16), nullable=True),
        sa.Column("api_provider", sa.String(length=64), nullable=True),
        sa.Column("masking_applied", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("intercepted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("intercept_reason", sa.String(length=255), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("request_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("response_summary", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === indexes ===
    op.create_index("idx_chunks_doc_id", "chunks", ["doc_id"])
    op.create_index(
        "idx_chunks_content_tsv",
        "chunks",
        ["content_tsv"],
        postgresql_using="gin",
    )
    op.create_index("idx_document_permissions_doc_id", "document_permissions", ["doc_id"])
    op.create_index("idx_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("idx_sensitive_keywords_keyword", "sensitive_keywords", ["keyword"])


def downgrade() -> None:
    # Indexes
    op.drop_index("idx_sensitive_keywords_keyword", table_name="sensitive_keywords")
    op.drop_index("idx_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("idx_document_permissions_doc_id", table_name="document_permissions")
    op.drop_index("idx_chunks_content_tsv", table_name="chunks")
    op.drop_index("idx_chunks_doc_id", table_name="chunks")

    # Tables in reverse dependency order
    op.drop_table("audit_logs")
    op.drop_table("keyword_match_logs")
    op.drop_table("sensitive_keywords")
    op.drop_table("group_permissions")
    op.drop_table("tag_permissions")
    op.drop_table("field_permissions")
    op.drop_table("document_permissions")
    op.drop_table("file_type_permissions")
    op.drop_table("chunk_tags")
    op.drop_table("document_tags")
    op.drop_table("tags")
    op.drop_table("chunks")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    op.drop_table("user_groups")
    op.drop_table("users")
