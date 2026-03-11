"""Vector store backend tests."""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.services.vector_store import JsonVectorStore, PgVectorStore, embed_text, get_vector_store


def test_embed_text_is_deterministic() -> None:
    """Same input should produce stable embedding output."""

    first = embed_text("prepare for interview")
    second = embed_text("prepare for interview")
    assert first == second


def test_json_vector_store_prefers_semantically_related_memory(db_session: Session) -> None:
    """JSON vector backend should rank similar memory above unrelated text."""

    user = User(email="vector-store@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    store = JsonVectorStore(dimensions=64)
    store.store(
        db=db_session,
        user_id=user.id,
        text_value="I am preparing for an interview loop.",
        importance=0.4,
    )
    store.store(
        db=db_session,
        user_id=user.id,
        text_value="I enjoy coffee brewing techniques.",
        importance=0.95,
    )
    db_session.commit()

    results = store.search(
        db=db_session,
        user_id=user.id,
        query="help with interview questions",
        limit=1,
    )

    assert len(results) == 1
    assert "interview" in results[0].text.lower()


def test_get_vector_store_rejects_unsupported_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configured dimensions must stay compatible with DB schema."""

    monkeypatch.setenv("VECTOR_EMBEDDING_DIMENSIONS", "32")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match="VECTOR_EMBEDDING_DIMENSIONS"):
            get_vector_store()
    finally:
        get_settings.cache_clear()


def test_pgvector_store_falls_back_to_json_when_sql_fails(db_session: Session) -> None:
    """PgVectorStore should return fallback results if pgvector SQL path errors."""

    user = User(email="vector-fallback@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    # existing JSON-compatible payload is enough for fallback path
    # and avoids dependence on PostgreSQL runtime in tests.
    JsonVectorStore(dimensions=64).store(
        db=db_session,
        user_id=user.id,
        text_value="I am preparing for interview loops.",
        importance=0.8,
    )
    db_session.commit()

    class FailingPgSession:
        """Session wrapper that simulates PostgreSQL SQL execution failure."""

        def __init__(self, real_session: Session) -> None:
            self._real = real_session
            self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

        def execute(self, *args, **kwargs):
            raise OperationalError("select 1", {}, Exception("simulated pgvector SQL error"))

        def query(self, *args, **kwargs):
            return self._real.query(*args, **kwargs)

    store = PgVectorStore(dimensions=64)
    results = store.search(
        db=FailingPgSession(db_session),  # type: ignore[arg-type]
        user_id=user.id,
        query="interview help",
        limit=1,
    )

    assert len(results) == 1
    assert "interview" in results[0].text.lower()
