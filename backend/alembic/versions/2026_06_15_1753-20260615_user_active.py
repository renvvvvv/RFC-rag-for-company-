"""add user display_name and is_active columns

Revision ID: 20260615_user_active
Revises: 20260615_conv_eval
Create Date: 2026-06-15 17:53:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260615_user_active"
down_revision = "20260615_conv_eval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "display_name")
