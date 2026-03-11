"""add pgvector embedding column

Revision ID: 20260311_0003
Revises: 20260310_0002
Create Date: 2026-03-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.types import EmbeddingVector

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

    extension_installed = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
    ).scalar_one()
    if not extension_installed:
        try:
            op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        except Exception as exc:  # pragma: no cover - depends on DB privileges
            raise RuntimeError(
                "Failed to create pgvector extension. "
                "Install extension or grant privileges before migration."
            ) from exc

    extension_installed = bind.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
    ).scalar_one()
    if not extension_installed:
        raise RuntimeError(
            "pgvector extension is not installed. Install extension or grant permissions before migration."
        )

    op.add_column("vector_memory", sa.Column("embedding_vector", EmbeddingVector(64), nullable=True))

    # Backfill from legacy JSON embeddings is intentionally deferred to a dedicated
    # operational job to avoid long-running migration locks on large tables.
    # Index creation is intentionally deferred to a dedicated operational migration
    # where CREATE INDEX CONCURRENTLY can be used without long write locks.


def downgrade() -> None:
    """Drop pgvector embedding column from vector_memory table."""

    op.drop_column("vector_memory", "embedding_vector")
