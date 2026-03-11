"""Vector storage and retrieval backends."""

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.memory import VectorMemory


@dataclass
class VectorSearchResult:
    """Normalized semantic retrieval item returned by vector backends."""

    text: str
    importance: float
    created_at: datetime | None
    similarity: float


def _normalize(values: list[float]) -> list[float]:
    """Normalize vector values to unit length."""

    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    """Build a deterministic local embedding for bootstrap retrieval behavior."""

    vector = [0.0] * dimensions
    tokens = [token for token in text.lower().split() if token]
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], byteorder="big") % dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        weight = 1.0 + (digest[3] / 255.0) * 0.1
        vector[index] += sign * weight
    return _normalize(vector)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity for two equal-length vectors."""

    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(left_i * right_i for left_i, right_i in zip(left, right, strict=True))


class JsonVectorStore:
    """Vector backend that stores and searches embeddings in application code."""

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def store(
        self,
        db: Session,
        user_id: int,
        text_value: str,
        importance: float,
        embedding: list[float] | None = None,
    ) -> None:
        """Persist semantic memory with deterministic embedding payload."""

        computed_embedding = embedding or embed_text(text_value, dimensions=self.dimensions)
        db.add(
            VectorMemory(
                user_id=user_id,
                text=text_value.strip(),
                importance=importance,
                embedding=computed_embedding,
                embedding_vector=computed_embedding,
            )
        )

    def search(
        self,
        db: Session,
        user_id: int,
        query: str,
        limit: int,
    ) -> list[VectorSearchResult]:
        """Return top semantic memories ranked by cosine similarity."""

        query_embedding = embed_text(query, dimensions=self.dimensions)
        items = db.query(VectorMemory).filter(VectorMemory.user_id == user_id).all()

        scored: list[VectorSearchResult] = []
        for item in items:
            item_embedding = item.embedding
            if item_embedding is None:
                item_embedding = embed_text(item.text, dimensions=self.dimensions)
                item.embedding = item_embedding
                item.embedding_vector = item_embedding

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

        query_embedding = embed_text(query, dimensions=self.dimensions)
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_embedding) + "]"
        stmt = text(
            """
            SELECT
                text,
                importance,
                created_at,
                (1 - (embedding_vector <=> CAST(:query_vector AS vector))) AS similarity
            FROM vector_memory
            WHERE user_id = :user_id
              AND embedding_vector IS NOT NULL
            ORDER BY embedding_vector <=> CAST(:query_vector AS vector)
            LIMIT :limit
            """
        )

        rows = db.execute(
            stmt,
            {"user_id": user_id, "query_vector": vector_literal, "limit": limit},
        ).mappings()

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
    backend = settings.vector_backend.lower().strip()
    if backend == "pgvector":
        return PgVectorStore(dimensions=settings.vector_embedding_dimensions)
    return JsonVectorStore(dimensions=settings.vector_embedding_dimensions)
