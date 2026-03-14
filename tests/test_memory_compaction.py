"""Memory deduplication and compaction tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import VectorMemory
from app.models.user import User
from app.services.memory_compaction import compact_vector_memory


def test_compaction_removes_exact_duplicates_for_same_user(db_session: Session) -> None:
    """Exact same normalized text for one user should keep one strongest row."""

    user = User(email="dedup-exact@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="I am preparing for interview loops.",
                importance=0.60,
                created_at=now - timedelta(minutes=5),
            ),
            VectorMemory(
                user_id=user.id,
                text=" i am preparing for   interview loops ",
                importance=0.75,
                created_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db_session.commit()

    result = compact_vector_memory(db_session, dry_run=False)
    db_session.commit()

    rows = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user.id)).scalars().all()
    assert len(rows) == 1
    assert rows[0].importance == 0.75
    assert result.rows_deleted == 1
    assert result.exact_duplicates_deleted == 1
    assert result.near_duplicates_deleted == 0


def test_compaction_removes_near_duplicates_for_same_user(db_session: Session) -> None:
    """High-overlap near-duplicates should be compacted deterministically."""

    user = User(email="dedup-near@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    now = datetime.now(UTC)
    db_session.add_all(
        [
            VectorMemory(
                user_id=user.id,
                text="I am preparing for backend system design interviews next week.",
                importance=0.55,
                created_at=now - timedelta(minutes=8),
            ),
            VectorMemory(
                user_id=user.id,
                text="I am preparing for backend system design interview next week",
                importance=0.90,
                created_at=now - timedelta(minutes=2),
            ),
        ]
    )
    db_session.commit()

    result = compact_vector_memory(db_session, dry_run=False)
    db_session.commit()

    rows = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user.id)).scalars().all()
    assert len(rows) == 1
    assert "backend system design interview" in rows[0].text.lower()
    assert result.rows_deleted == 1
    assert result.near_duplicates_deleted == 1


def test_compaction_preserves_false_positive_guard(db_session: Session) -> None:
    """Semantically different short statements should not be merged."""

    user = User(email="dedup-guard@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            VectorMemory(user_id=user.id, text="I like tea", importance=0.7),
            VectorMemory(user_id=user.id, text="I do not like tea", importance=0.8),
        ]
    )
    db_session.commit()

    result = compact_vector_memory(db_session, dry_run=False)
    db_session.commit()

    rows = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user.id)).scalars().all()
    assert len(rows) == 2
    assert result.rows_deleted == 0


def test_compaction_respects_user_isolation(db_session: Session) -> None:
    """Duplicate texts across different users must never be compacted together."""

    user_1 = User(email="dedup-scope-1@example.com", password_hash="hash")
    user_2 = User(email="dedup-scope-2@example.com", password_hash="hash")
    db_session.add_all([user_1, user_2])
    db_session.flush()
    db_session.add_all(
        [
            VectorMemory(user_id=user_1.id, text="My favorite drink is coffee", importance=0.6),
            VectorMemory(user_id=user_2.id, text="My favorite drink is coffee", importance=0.9),
        ]
    )
    db_session.commit()

    result = compact_vector_memory(db_session, dry_run=False)
    db_session.commit()

    rows_1 = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user_1.id)).scalars().all()
    rows_2 = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user_2.id)).scalars().all()
    assert len(rows_1) == 1
    assert len(rows_2) == 1
    assert result.rows_deleted == 0


def test_compaction_supports_dry_run_mode(db_session: Session) -> None:
    """Dry-run mode should report deletions without mutating data."""

    user = User(email="dedup-dry-run@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            VectorMemory(user_id=user.id, text="My name is Ilya", importance=0.7),
            VectorMemory(user_id=user.id, text=" my name is ilya ", importance=0.6),
        ]
    )
    db_session.commit()

    result = compact_vector_memory(db_session, dry_run=True)
    rows = db_session.execute(select(VectorMemory).where(VectorMemory.user_id == user.id)).scalars().all()

    assert len(rows) == 2
    assert result.rows_deleted == 1
    assert result.exact_duplicates_deleted == 1

