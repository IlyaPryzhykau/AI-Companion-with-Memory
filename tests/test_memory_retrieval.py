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


def test_retrieval_is_scoped_to_user_id(db_session: Session) -> None:
    """Retrieval context should contain only memories of the requested user."""

    user_1 = User(email="retrieval-scope-1@example.com", password_hash="hash")
    user_2 = User(email="retrieval-scope-2@example.com", password_hash="hash")
    db_session.add_all([user_1, user_2])
    db_session.flush()

    db_session.add_all(
        [
            VectorMemory(user_id=user_1.id, text="I prefer tea in the evening.", importance=0.7),
            VectorMemory(user_id=user_2.id, text="I prefer coffee every morning.", importance=0.9),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user_1.id,
        user_query="What do I prefer?",
        max_items=3,
    )

    assert "prefer tea" in context.lower()
    assert "prefer coffee" not in context.lower()


def test_retrieval_prefers_more_recent_memory_on_score_tie(db_session: Session) -> None:
    """Recency should break ties when relevance and importance are equal."""

    user = User(email="retrieval-recency@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="Project alpha status is pending.",
                importance=0.6,
                created_at=now - timedelta(days=6),
            ),
            VectorMemory(
                user_id=user.id,
                text="Project beta status is pending.",
                importance=0.6,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="Project status update",
        max_items=1,
    )

    assert "beta" in context.lower()


def test_retrieval_uses_importance_when_query_has_only_stop_words(db_session: Session) -> None:
    """If query has no meaningful tokens, ranking should fall back to importance/recency."""

    user = User(email="retrieval-stopwords@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="low priority memory",
                importance=0.2,
                created_at=now - timedelta(hours=1),
            ),
            VectorMemory(
                user_id=user.id,
                text="high priority memory",
                importance=0.95,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="the and to my",
        max_items=1,
    )

    assert "high priority memory" in context.lower()
