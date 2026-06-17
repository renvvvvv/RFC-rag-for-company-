"""add created_by to evaluation tables

Revision ID: add_eval_created_by
Revises: 60cfcaa07bfb
Create Date: 2026-06-17 04:03:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_eval_created_by"
down_revision = "60cfcaa07bfb"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_datasets",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "evaluation_tasks",
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("evaluation_tasks", "created_by")
    op.drop_column("evaluation_datasets", "created_by")
