"""Vector storage and retrieval backends."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.memory import VectorMemory
from app.services.embeddings import (
    EmbeddingProvider,
    LocalHashEmbeddingProvider,
    resolve_embedding_provider_with_fallback,
)
from app.services.vector_validation import validate_embedding_vector

logger = logging.getLogger(__name__)
SUPPORTED_EMBEDDING_DIMENSIONS = 64


@dataclass
class VectorSearchResult:
    """Normalized semantic retrieval item returned by vector backends."""

    text: str
    importance: float
    created_at: datetime | None
    similarity: float


def _ensure_safe_vector(values: list[float], expected_dimensions: int) -> list[float]:
    """Validate vector payload before using it in DB similarity expressions."""

    if not all(isinstance(value, float | int) for value in values):
        raise ValueError("Embedding vector must contain numeric values.")
    return validate_embedding_vector(values, expected_dimensions=expected_dimensions)


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    """Backward-compatible helper using local deterministic embeddings."""

    return LocalHashEmbeddingProvider().embed(text=text, dimensions=dimensions)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for two equal-length vectors."""

    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_i * right_i for left_i, right_i in zip(left, right, strict=True))


class JsonVectorStore:
    """Vector backend that stores and searches embeddings in application code."""

    def __init__(
        self,
        dimensions: int,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.dimensions = dimensions
        self.embedding_provider = embedding_provider or resolve_embedding_provider_with_fallback()
        self._local_provider = LocalHashEmbeddingProvider()

    def _embed_with_fallback(self, text: str) -> list[float]:
        """Generate embeddings with fallback to local deterministic provider."""

        try:
            return self.embedding_provider.embed(text=text, dimensions=self.dimensions)
        except Exception as exc:
            logger.warning(
                "embedding_provider_failed provider=%s error=%s fallback=local",
                getattr(self.embedding_provider, "name", type(self.embedding_provider).__name__),
                f"{type(exc).__name__}: {exc}",
            )
            return self._local_provider.embed(text=text, dimensions=self.dimensions)

    def store(
        self,
        db: Session,
        user_id: int,
        text_value: str,
        importance: float,
        embedding: list[float] | None = None,
    ) -> None:
        """Persist semantic memory with deterministic embedding payload."""

        computed_embedding = embedding or self._embed_with_fallback(text_value)
        computed_embedding = self._validate_embedding(computed_embedding)
        try:
            db.add(
                VectorMemory(
                    user_id=user_id,
                    text=text_value.strip(),
                    importance=importance,
                    embedding=computed_embedding,
                    embedding_vector=computed_embedding,
                )
            )
        except SQLAlchemyError as exc:
            logger.warning(
                "vector_store_add_failed user_id=%s backend=%s error=%s",
                user_id,
                type(self).__name__,
                f"{type(exc).__name__}: {exc}",
            )
            raise

    def search(
        self,
        db: Session,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[VectorSearchResult]:
        """Return top semantic memories ranked by cosine similarity."""

        query_embedding = self._embed_with_fallback(query)
        candidate_limit = max(100, limit * 20)
        items = (
            db.query(VectorMemory)
            .filter(VectorMemory.user_id == user_id)
            .order_by(VectorMemory.created_at.desc())
            .limit(candidate_limit)
            .all()
        )

        scored: list[VectorSearchResult] = []
        for item in items:
            item_embedding = item.embedding
            if item_embedding is None:
                item_embedding = self._local_provider.embed(item.text, dimensions=self.dimensions)

            similarity = cosine_similarity(query_embedding, item_embedding)
            scored.append(
                VectorSearchResult(
                    text=item.text,
                    importance=item.importance,
                    created_at=item.created_at,
                    similarity=max(0.0, similarity),
                )
            )

        scored.sort(
            key=lambda item: (item.similarity, item.importance, _safe_utc(item.created_at)),
            reverse=True,
        )
        return scored[:limit]

    def _validate_embedding(self, embedding: list[float]) -> list[float]:
        """Validate embedding dimensions for current backend configuration."""

        return validate_embedding_vector(embedding, expected_dimensions=self.dimensions)


class PgVectorStore(JsonVectorStore):
    """Vector backend using pgvector similarity on PostgreSQL."""

    def search(
        self,
        db: Session,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[VectorSearchResult]:
        """Return top semantic memories with pgvector distance when available."""

        if db.bind is None or db.bind.dialect.name != "postgresql":
            return super().search(db, user_id, query, limit)

        try:
            query_embedding = _ensure_safe_vector(
                self._embed_with_fallback(query),
                expected_dimensions=self.dimensions,
            )
            distance_expr = VectorMemory.embedding_vector.cosine_distance(query_embedding)
            stmt = (
                select(
                    VectorMemory.text,
                    VectorMemory.importance,
                    VectorMemory.created_at,
                    (1 - distance_expr).label("similarity"),
                )
                .where(
                    VectorMemory.user_id == user_id,
                    VectorMemory.embedding_vector.is_not(None),
                )
                .order_by(distance_expr)
                .limit(limit)
            )
            rows = db.execute(stmt).mappings()
        except (SQLAlchemyError, AttributeError, ValueError) as exc:  # pragma: no cover
            logger.warning(
                "pgvector_search_failed user_id=%s error=%s fallback=json",
                user_id,
                f"{type(exc).__name__}: {exc}",
            )
            return super().search(db, user_id, query, limit)

        results: list[VectorSearchResult] = []
        for row in rows:
            results.append(
                VectorSearchResult(
                    text=row["text"],
                    importance=float(row["importance"]),
                    created_at=row["created_at"],
                    similarity=max(0.0, float(row["similarity"] or 0.0)),
                )
            )
        return results


def _safe_utc(dt: datetime | None) -> datetime:
    """Normalize nullable datetime to UTC for deterministic sorting."""

    if dt is None:
        return datetime.now(UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def get_vector_store() -> JsonVectorStore | PgVectorStore:
    """Resolve configured vector backend implementation."""

    settings = get_settings()
    if settings.vector_embedding_dimensions != SUPPORTED_EMBEDDING_DIMENSIONS:
        raise ValueError(
            "VECTOR_EMBEDDING_DIMENSIONS must be 64 for current schema compatibility."
        )

    backend = settings.vector_backend.lower().strip()
    if backend not in {"json", "pgvector"}:
        raise ValueError(
            f"Unsupported VECTOR_BACKEND '{settings.vector_backend}'. Use 'json' or 'pgvector'."
        )
    embedding_provider = resolve_embedding_provider_with_fallback()
    if backend == "pgvector":
        return PgVectorStore(
            dimensions=settings.vector_embedding_dimensions,
            embedding_provider=embedding_provider,
        )
    return JsonVectorStore(
        dimensions=settings.vector_embedding_dimensions,
        embedding_provider=embedding_provider,
    )
