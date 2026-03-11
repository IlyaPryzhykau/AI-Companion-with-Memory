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

    op.execute(
        """
        DO $$
        BEGIN
            BEGIN
                CREATE EXTENSION IF NOT EXISTS vector;
            EXCEPTION
                WHEN insufficient_privilege THEN
                    RAISE NOTICE 'Skipping CREATE EXTENSION vector due to insufficient privileges';
            END;
        END $$;
        """
    )
    op.execute("ALTER TABLE vector_memory ADD COLUMN IF NOT EXISTS embedding_vector vector(64)")

    # Backfill from legacy JSON embeddings is intentionally deferred to a dedicated
    # operational job to avoid long-running migration locks on large tables.
    op.execute(
        """
        DO $$
        DECLARE vector_count BIGINT;
        BEGIN
            SELECT COUNT(*) INTO vector_count
            FROM vector_memory
            WHERE embedding_vector IS NOT NULL;

            IF vector_count >= 1000 THEN
                EXECUTE '
                    CREATE INDEX IF NOT EXISTS ix_vector_memory_embedding_vector_ivfflat
                    ON vector_memory
                    USING ivfflat (embedding_vector vector_cosine_ops)
                ';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    """Drop pgvector embedding column from vector_memory table."""

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_vector_memory_embedding_vector_ivfflat")

    op.drop_column("vector_memory", "embedding_vector")
