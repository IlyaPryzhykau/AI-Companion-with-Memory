"""Custom SQLAlchemy types used across database models."""

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

from pgvector.sqlalchemy import Vector


class EmbeddingVector(TypeDecorator):
    """Store vectors as pgvector on PostgreSQL and JSON on other dialects."""

    cache_ok = True
    impl = JSON
    comparator_factory = Vector.comparator_factory

    def __init__(self, dimensions: int = 64) -> None:
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        """Select the most appropriate storage type per SQL dialect."""

        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        """Validate embedding payload shape before writing to DB."""

        if value is None:
            return value
        if not isinstance(value, list):
            raise ValueError("Embedding value must be a list of floats.")
        if len(value) != self.dimensions:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self.dimensions}, got {len(value)}."
            )
        if not all(isinstance(item, (int, float)) for item in value):
            raise ValueError("Embedding list must contain only numeric values.")
        return [float(item) for item in value]
