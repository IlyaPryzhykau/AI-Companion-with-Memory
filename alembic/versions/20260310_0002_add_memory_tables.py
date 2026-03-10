"""add memory tables

Revision ID: 20260310_0002
Revises: 20260309_0001
Create Date: 2026-03-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260310_0002"
down_revision: str | None = "20260309_0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create user_profiles, user_memory, and vector_memory tables."""

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("native_language", sa.String(length=32), nullable=True),
        sa.Column("english_level", sa.String(length=32), nullable=True),
        sa.Column("goals_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_profiles_id", "user_profiles", ["id"], unique=False)
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"], unique=True)

    op.create_table(
        "user_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_memory_user_key"),
    )
    op.create_index("ix_user_memory_id", "user_memory", ["id"], unique=False)
    op.create_index("ix_user_memory_user_id", "user_memory", ["user_id"], unique=False)

    op.create_table(
        "vector_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vector_memory_id", "vector_memory", ["id"], unique=False)
    op.create_index("ix_vector_memory_user_id", "vector_memory", ["user_id"], unique=False)


def downgrade() -> None:
    """Drop user_profiles, user_memory, and vector_memory tables."""

    op.drop_index("ix_vector_memory_user_id", table_name="vector_memory")
    op.drop_index("ix_vector_memory_id", table_name="vector_memory")
    op.drop_table("vector_memory")

    op.drop_index("ix_user_memory_user_id", table_name="user_memory")
    op.drop_index("ix_user_memory_id", table_name="user_memory")
    op.drop_table("user_memory")

    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_index("ix_user_profiles_id", table_name="user_profiles")
    op.drop_table("user_profiles")
