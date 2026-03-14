"""Memory retrieval policy tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.models.chat import Chat, Message
from app.models.memory import UserMemory
from app.models.memory import VectorMemory
from app.models.user import User
from app.services.memory import _normalize_weights, build_memory_context


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


def test_retrieval_uses_configured_weights(db_session: Session, monkeypatch) -> None:
    """Configured weights should influence ranking outcomes."""

    monkeypatch.setattr(
        "app.services.memory.get_settings",
        lambda: SimpleNamespace(
            memory_retrieval_top_k=6,
            memory_context_max_chars=800,
            memory_context_max_tokens=220,
            memory_retrieval_candidate_multiplier=3,
            memory_retrieval_profile_top_k=2,
            memory_retrieval_episodic_top_k=2,
            memory_retrieval_semantic_top_k=6,
            memory_weight_relevance=0.05,
            memory_weight_importance=0.90,
            memory_weight_recency=0.05,
        ),
    )

    user = User(email="retrieval-weights@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="Interview prep checklist",
                importance=0.2,
            ),
            VectorMemory(
                user_id=user.id,
                text="Unrelated hobby notes",
                importance=0.95,
            ),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="help me with interview preparation",
        max_items=1,
    )

    assert "unrelated hobby notes" in context.lower()


def test_retrieval_uses_configured_top_k_and_char_budget(db_session: Session, monkeypatch) -> None:
    """Top-k and char budget defaults should be sourced from settings."""

    monkeypatch.setattr(
        "app.services.memory.get_settings",
        lambda: SimpleNamespace(
            memory_retrieval_top_k=1,
            memory_context_max_chars=90,
            memory_context_max_tokens=220,
            memory_retrieval_candidate_multiplier=3,
            memory_retrieval_profile_top_k=2,
            memory_retrieval_episodic_top_k=2,
            memory_retrieval_semantic_top_k=6,
            memory_weight_relevance=0.65,
            memory_weight_importance=0.25,
            memory_weight_recency=0.10,
        ),
    )

    user = User(email="retrieval-config-budget@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="first memory about interview planning " + ("x" * 80),
                importance=0.9,
            ),
            VectorMemory(
                user_id=user.id,
                text="second memory that should not fit due to top-k",
                importance=0.8,
            ),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="interview planning",
    )

    assert context.startswith("Retrieved memory context:")
    assert context.count("\n- [") == 1
    assert len(context) <= 90


def test_normalize_weights_falls_back_for_zero_sum() -> None:
    """Zero/near-zero weights should use deterministic default fallback."""

    weights = _normalize_weights(0.0, 0.0, 0.0)
    assert weights == (0.65, 0.25, 0.10)


def test_normalize_weights_clamps_negative_values() -> None:
    """Negative weights should be clamped to zero before normalization."""

    relevance, importance, recency = _normalize_weights(-1.0, 2.0, -3.0)
    assert relevance == 0.0
    assert importance == 1.0
    assert recency == 0.0


def test_retrieval_v2_combines_profile_episodic_and_semantic_layers(db_session: Session) -> None:
    """Layered retrieval should include profile, episodic, and semantic entries."""

    user = User(email="retrieval-layered@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    chat = Chat(user_id=user.id, assistant_id="default")
    db_session.add(chat)
    db_session.flush()
    db_session.add_all(
        [
            UserMemory(user_id=user.id, key="name", value="Alex", importance=0.9),
            Message(chat_id=chat.id, role="user", content="I had a mock interview yesterday."),
            VectorMemory(user_id=user.id, text="Practice STAR method for interviews.", importance=0.8),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user.id,
        user_query="interview prep",
        max_items=6,
        max_chars=400,
    )

    assert "[S] name: Alex" in context
    assert "[E] I had a mock interview yesterday." in context
    assert "[V] Practice STAR method for interviews." in context


def test_retrieval_v2_respects_token_budget(db_session: Session, monkeypatch) -> None:
    """Token-budget packer should cap number of context lines when token budget is tight."""

    monkeypatch.setattr(
        "app.services.memory.get_settings",
        lambda: SimpleNamespace(
            memory_retrieval_top_k=6,
            memory_context_max_chars=2000,
            memory_context_max_tokens=14,
            memory_retrieval_candidate_multiplier=3,
            memory_retrieval_profile_top_k=0,
            memory_retrieval_episodic_top_k=0,
            memory_retrieval_semantic_top_k=6,
            memory_weight_relevance=0.65,
            memory_weight_importance=0.25,
            memory_weight_recency=0.10,
        ),
    )

    user = User(email="retrieval-token-budget@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            VectorMemory(user_id=user.id, text="first memory line with several tokens", importance=0.9),
            VectorMemory(user_id=user.id, text="second memory line with several tokens", importance=0.85),
            VectorMemory(user_id=user.id, text="third memory line with several tokens", importance=0.8),
        ]
    )
    db_session.commit()

    context = build_memory_context(db_session, user_id=user.id, user_query="memory line")
    assert context.count("\n- [") <= 2


def test_retrieval_v2_has_deterministic_tie_ordering(db_session: Session) -> None:
    """Tie scores should be resolved deterministically across repeated calls."""

    user = User(email="retrieval-tie@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(user_id=user.id, text="alpha item", importance=0.7, created_at=now),
            VectorMemory(user_id=user.id, text="beta item", importance=0.7, created_at=now),
        ]
    )
    db_session.commit()

    first = build_memory_context(db_session, user_id=user.id, user_query="", max_items=2, max_chars=200)
    second = build_memory_context(db_session, user_id=user.id, user_query="", max_items=2, max_chars=200)
    assert first == second


def test_retrieval_v2_episodic_layer_is_user_scoped(db_session: Session) -> None:
    """Episodic retrieval must not leak messages across users."""

    user_1 = User(email="retrieval-episodic-scope-1@example.com", password_hash="hash")
    user_2 = User(email="retrieval-episodic-scope-2@example.com", password_hash="hash")
    db_session.add_all([user_1, user_2])
    db_session.flush()

    chat_1 = Chat(user_id=user_1.id, assistant_id="default")
    chat_2 = Chat(user_id=user_2.id, assistant_id="default")
    db_session.add_all([chat_1, chat_2])
    db_session.flush()
    db_session.add_all(
        [
            Message(chat_id=chat_1.id, role="user", content="I am preparing for backend interviews."),
            Message(chat_id=chat_2.id, role="user", content="I am preparing for frontend interviews."),
        ]
    )
    db_session.commit()

    context = build_memory_context(
        db_session,
        user_id=user_1.id,
        user_query="interviews",
        max_items=5,
        max_chars=400,
    )

    assert "backend interviews" in context.lower()
    assert "frontend interviews" not in context.lower()
