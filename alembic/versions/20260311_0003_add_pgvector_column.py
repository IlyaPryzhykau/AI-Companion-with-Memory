"""add pgvector embedding column

Revision ID: 20260311_0003
Revises: 20260310_0002
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260311_0003"
down_revision: str | None = "20260310_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Add pgvector-backed embedding column to vector_memory table."""

    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        op.add_column("vector_memory", sa.Column("embedding_vector", sa.JSON(), nullable=True))
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE vector_memory ADD COLUMN IF NOT EXISTS embedding_vector vector(64)")
    op.execute(
        """
        UPDATE vector_memory
        SET embedding_vector = embedding::vector
        WHERE embedding IS NOT NULL
          AND embedding_vector IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_vector_memory_embedding_vector_ivfflat
        ON vector_memory
        USING ivfflat (embedding_vector vector_cosine_ops)
        """
    )


def downgrade() -> None:
    """Drop pgvector embedding column from vector_memory table."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_vector_memory_embedding_vector_ivfflat")

    op.drop_column("vector_memory", "embedding_vector")
