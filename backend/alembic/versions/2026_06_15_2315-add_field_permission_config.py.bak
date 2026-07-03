"""add field permission config column

Revision ID: 20260615_add_field_permission_config
Revises: 20260615_add_user_display_name_is_active
Create Date: 2026-06-15 23:15:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260615_add_field_permission_config"
down_revision = "20260615_add_user_display_name_is_active"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "field_permissions",
        sa.Column(
            "config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("field_permissions", "config")
