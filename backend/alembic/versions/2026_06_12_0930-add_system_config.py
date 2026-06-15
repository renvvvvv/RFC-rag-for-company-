"""add system_config table

Revision ID: 20260612_add_system_config
Revises: 20260610_init
Create Date: 2026-06-12 09:30:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260612_add_system_config"
down_revision = "20260610_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("idx_system_config_key", "system_config", ["key"])


def downgrade() -> None:
    op.drop_index("idx_system_config_key", table_name="system_config")
    op.drop_table("system_config")
