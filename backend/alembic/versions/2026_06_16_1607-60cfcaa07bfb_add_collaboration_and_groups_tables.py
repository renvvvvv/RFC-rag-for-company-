"""add_collaboration_and_groups_tables

Revision ID: 60cfcaa07bfb
Revises: 20260615_field_perm
Create Date: 2026-06-16 16:07:37.970044

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '60cfcaa07bfb'
down_revision = '20260615_field_perm'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # User groups/departments with hierarchical support
    op.create_table(
        'user_groups',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('group_type', sa.String(length=32), nullable=True),
        sa.Column('parent_group_id', sa.UUID(), nullable=True),
        sa.Column('admin_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('member_ids', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column('max_security_level', sa.String(length=8), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['parent_group_id'], ['user_groups.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        if_not_exists=True,
    )

    # Comments on documents/chunks
    op.create_table(
        'comments',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('target_type', sa.String(length=16), nullable=False),
        sa.Column('target_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index('idx_comments_target', 'comments', ['target_type', 'target_id'], unique=False, if_not_exists=True)
    op.create_index('idx_comments_user_id', 'comments', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('idx_comments_parent_id', 'comments', ['parent_id'], unique=False, if_not_exists=True)

    # Bookmarks on documents/chunks
    op.create_table(
        'bookmarks',
        sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('target_type', sa.String(length=16), nullable=False),
        sa.Column('target_id', sa.UUID(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'target_type', 'target_id', name='uix_bookmark_user_target'),
        if_not_exists=True,
    )
    op.create_index('idx_bookmarks_target', 'bookmarks', ['target_type', 'target_id'], unique=False, if_not_exists=True)
    op.create_index('idx_bookmarks_user_id', 'bookmarks', ['user_id'], unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index('idx_bookmarks_user_id', table_name='bookmarks', if_exists=True)
    op.drop_index('idx_bookmarks_target', table_name='bookmarks', if_exists=True)
    op.drop_table('bookmarks', if_exists=True)
    op.drop_index('idx_comments_parent_id', table_name='comments', if_exists=True)
    op.drop_index('idx_comments_user_id', table_name='comments', if_exists=True)
    op.drop_index('idx_comments_target', table_name='comments', if_exists=True)
    op.drop_table('comments', if_exists=True)
    op.drop_table('user_groups', if_exists=True)
