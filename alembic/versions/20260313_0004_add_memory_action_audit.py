"""add memory action audit table

Revision ID: 20260313_0004
Revises: 20260311_0003
Create Date: 2026-03-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260313_0004"
down_revision: str | None = "20260311_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Create memory_action_audit table for memory orchestration debugging."""

    op.create_table(
        "memory_action_audit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_action_audit_id", "memory_action_audit", ["id"], unique=False)
    op.create_index("ix_memory_action_audit_user_id", "memory_action_audit", ["user_id"], unique=False)
    op.create_index("ix_memory_action_audit_chat_id", "memory_action_audit", ["chat_id"], unique=False)


def downgrade() -> None:
    """Drop memory_action_audit table."""

    op.drop_index("ix_memory_action_audit_chat_id", table_name="memory_action_audit")
    op.drop_index("ix_memory_action_audit_user_id", table_name="memory_action_audit")
    op.drop_index("ix_memory_action_audit_id", table_name="memory_action_audit")
    op.drop_table("memory_action_audit")
