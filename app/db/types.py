"""Custom SQLAlchemy types used across database models."""

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

from pgvector.sqlalchemy import Vector


class EmbeddingVector(TypeDecorator):
    """Store vectors as pgvector on PostgreSQL and JSON on other dialects."""

    cache_ok = True
    impl = JSON

    def __init__(self, dimensions: int = 64) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        """Select the most appropriate storage type per SQL dialect."""

        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())
