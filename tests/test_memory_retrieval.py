"""Memory retrieval policy tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.memory import VectorMemory
from app.models.user import User
from app.services.memory import build_memory_context


def test_retrieval_prefers_relevant_memory_text(db_session: Session) -> None:
    """Top-k retrieval should prioritize query-relevant memory."""

    user = User(email="retrieval@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="I am preparing for an interview at OpenAI.",
                importance=0.45,
                created_at=now - timedelta(hours=2),
            ),
            VectorMemory(
                user_id=user.id,
                text="I enjoy drinking coffee in the morning.",
                importance=1.0,
                created_at=now - timedelta(hours=2),
            ),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="Can you help me prepare for interview questions?",
        max_items=1,
    )

    assert "interview" in context.lower()


def test_retrieval_respects_character_budget(db_session: Session) -> None:
    """Context builder should enforce max_chars and truncate oversized entries."""

    user = User(email="retrieval-budget@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    db_session.add(
        VectorMemory(
            user_id=user.id,
            text="x" * 300,
            importance=0.9,
        )
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="x",
        max_items=3,
        max_chars=80,
    )

    assert context.startswith("Retrieved memory context:")
    assert "..." in context
