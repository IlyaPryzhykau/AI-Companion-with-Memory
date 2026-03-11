"""Vector store backend tests."""

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.vector_store import JsonVectorStore, embed_text


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
