"""Add pgvector-backed vector tables.

Revision ID: 20260624_add_pgvector_vectors
Revises: f7111a21954a
Create Date: 2026-06-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260624_add_pgvector_vectors"
down_revision = "f7111a21954a"
branch_labels = None
depends_on = None

try:
    from pgvector.sqlalchemy import Vector

    _PGVECTOR_AVAILABLE = True
except Exception:  # pragma: no cover
    Vector = None  # type: ignore
    _PGVECTOR_AVAILABLE = False


def _pgvector_available(conn) -> bool:
    """Return True if the pgvector extension is available in PostgreSQL."""
    result = conn.execute(
        sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'")
    )
    return bool(result.scalar())


def upgrade() -> None:
    if not _PGVECTOR_AVAILABLE:
        return

    conn = op.get_bind()
    if not _pgvector_available(conn):
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))

    # === text_chunk_vectors ===
    op.create_table(
        "text_chunk_vectors",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("kb_id", sa.String(length=128), nullable=False),
        sa.Column("modality", sa.String(length=32), nullable=False),
        sa.Column("doc_acl_version", sa.String(length=128), nullable=True),
        sa.Column("max_keyword_level", sa.Integer(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String(length=64)), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === image_frame_vectors ===
    op.create_table(
        "image_frame_vectors",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("doc_id", sa.String(length=128), nullable=False),
        sa.Column("kb_id", sa.String(length=128), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(length=512), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # === indexes ===
    op.create_index("idx_text_chunk_kb_id", "text_chunk_vectors", ["kb_id"])
    op.create_index("idx_text_chunk_doc_id", "text_chunk_vectors", ["doc_id"])
    op.create_index("idx_text_chunk_modality", "text_chunk_vectors", ["modality"])
    op.create_index("idx_text_chunk_status", "text_chunk_vectors", ["status"])
    op.create_index(
        "idx_text_chunk_embedding_hnsw",
        "text_chunk_vectors",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    op.create_index("idx_image_frame_kb_id", "image_frame_vectors", ["kb_id"])
    op.create_index("idx_image_frame_doc_id", "image_frame_vectors", ["doc_id"])
    op.create_index(
        "idx_image_frame_embedding_hnsw",
        "image_frame_vectors",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 200},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    if not _PGVECTOR_AVAILABLE:
        return

    # Indexes
    op.drop_index("idx_image_frame_embedding_hnsw", table_name="image_frame_vectors")
    op.drop_index("idx_image_frame_doc_id", table_name="image_frame_vectors")
    op.drop_index("idx_image_frame_kb_id", table_name="image_frame_vectors")
    op.drop_index("idx_text_chunk_embedding_hnsw", table_name="text_chunk_vectors")
    op.drop_index("idx_text_chunk_status", table_name="text_chunk_vectors")
    op.drop_index("idx_text_chunk_modality", table_name="text_chunk_vectors")
    op.drop_index("idx_text_chunk_doc_id", table_name="text_chunk_vectors")
    op.drop_index("idx_text_chunk_kb_id", table_name="text_chunk_vectors")

    # Tables
    op.drop_table("image_frame_vectors")
    op.drop_table("text_chunk_vectors")

    # Dropping the extension is intentionally omitted because it may be shared
    # across databases and could fail if objects still reference it.
