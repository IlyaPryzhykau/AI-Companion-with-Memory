"""Deterministic memory deduplication and compaction utilities."""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.memory import VectorMemory

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryCompactionResult:
    """Compaction summary for operational reporting and tests."""

    users_scanned: int
    rows_scanned: int
    rows_deleted: int
    exact_duplicates_deleted: int
    near_duplicates_deleted: int


@dataclass(frozen=True)
class _KeepRecord:
    """Internal keeper representation for deterministic comparisons."""

    id: int
    text: str
    normalized_text: str
    tokens: set[str]
    importance: float
    created_at: datetime


def compact_vector_memory(
    db: Session,
    *,
    user_id: int | None = None,
    near_duplicate_threshold: float = 0.85,
    dry_run: bool = True,
) -> MemoryCompactionResult:
    """Deduplicate vector memory rows with deterministic exact/near-duplicate rules.

    Rules:
    - Exact duplicate: same normalized text under the same user.
    - Near duplicate: high token overlap and similar text length under the same user.
    - Cross-user rows are never compared.
    """

    safe_threshold = max(0.5, min(0.99, float(near_duplicate_threshold)))
    user_ids = _resolve_target_users(db, user_id=user_id)
    deleted_ids: set[int] = set()
    exact_deleted = 0
    near_deleted = 0
    rows_scanned = 0

    try:
        for target_user_id in user_ids:
            records = (
                db.execute(
                    select(VectorMemory)
                    .where(VectorMemory.user_id == target_user_id)
                    .order_by(VectorMemory.created_at.asc(), VectorMemory.id.asc())
                )
                .scalars()
                .all()
            )
            rows_scanned += len(records)

            keep_by_exact_key: dict[str, _KeepRecord] = {}
            keepers: list[_KeepRecord] = []

            for row in records:
                normalized = _normalize_text(row.text)
                tokens = _tokenize(normalized)
                current = _KeepRecord(
                    id=row.id,
                    text=row.text,
                    normalized_text=normalized,
                    tokens=tokens,
                    importance=float(row.importance),
                    created_at=_safe_utc(row.created_at),
                )

                exact_match = keep_by_exact_key.get(normalized)
                if exact_match is not None:
                    winner, loser = _choose_winner(current, exact_match)
                    if loser.id not in deleted_ids:
                        deleted_ids.add(loser.id)
                        exact_deleted += 1
                    if winner.id == current.id:
                        keep_by_exact_key[normalized] = winner
                        keepers = [winner if item.id == exact_match.id else item for item in keepers]
                    continue

                similar = _find_near_duplicate(current, keepers, threshold=safe_threshold)
                if similar is not None:
                    winner, loser = _choose_winner(current, similar)
                    if loser.id not in deleted_ids:
                        deleted_ids.add(loser.id)
                        near_deleted += 1
                    if winner.id == current.id:
                        keepers = [winner if item.id == similar.id else item for item in keepers]
                        keep_by_exact_key.pop(similar.normalized_text, None)
                        keep_by_exact_key[current.normalized_text] = winner
                    continue

                keep_by_exact_key[normalized] = current
                keepers.append(current)

        if not dry_run and deleted_ids:
            db.execute(delete(VectorMemory).where(VectorMemory.id.in_(deleted_ids)))
    except SQLAlchemyError as exc:
        logger.exception(
            "memory_compaction_failed user_id=%s dry_run=%s error_type=%s",
            user_id,
            dry_run,
            type(exc).__name__,
        )
        raise

    result = MemoryCompactionResult(
        users_scanned=len(user_ids),
        rows_scanned=rows_scanned,
        rows_deleted=len(deleted_ids),
        exact_duplicates_deleted=exact_deleted,
        near_duplicates_deleted=near_deleted,
    )
    logger.info(
        "memory_compaction finished user_id=%s dry_run=%s users=%s rows=%s deleted=%s exact=%s near=%s threshold=%.2f",
        user_id,
        dry_run,
        result.users_scanned,
        result.rows_scanned,
        result.rows_deleted,
        result.exact_duplicates_deleted,
        result.near_duplicates_deleted,
        safe_threshold,
    )
    return result


def _resolve_target_users(db: Session, user_id: int | None) -> list[int]:
    if user_id is not None:
        return [int(user_id)] if int(user_id) > 0 else []
    rows = db.execute(select(VectorMemory.user_id).distinct().order_by(VectorMemory.user_id.asc())).all()
    return [int(row[0]) for row in rows]


def _normalize_text(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    cleaned = re.sub(r"[^\w\sа-яёčďěňřšťůžáíéýúů]", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[^\W\d_]{2,}", text, flags=re.UNICODE)
    return {_normalize_token(token) for token in tokens}


def _normalize_token(token: str) -> str:
    normalized = token.strip().lower()
    if len(normalized) > 4 and normalized.endswith("ies"):
        return normalized[:-3] + "y"
    if len(normalized) > 4 and normalized.endswith("es"):
        return normalized[:-2]
    if len(normalized) > 4 and normalized.endswith("s"):
        return normalized[:-1]
    return normalized


def _find_near_duplicate(candidate: _KeepRecord, keepers: list[_KeepRecord], threshold: float) -> _KeepRecord | None:
    best: tuple[float, _KeepRecord] | None = None
    for keeper in keepers:
        score = _token_jaccard(candidate.tokens, keeper.tokens)
        if score < threshold:
            continue

        length_ratio = _length_ratio(candidate.normalized_text, keeper.normalized_text)
        if length_ratio < 0.85:
            continue

        if best is None or score > best[0] or (score == best[0] and keeper.id > best[1].id):
            best = (score, keeper)

    return best[1] if best is not None else None


def _token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    intersection = len(left.intersection(right))
    union = len(left.union(right))
    return float(intersection) / float(union) if union else 0.0


def _length_ratio(left: str, right: str) -> float:
    left_len = max(1, len(left))
    right_len = max(1, len(right))
    return float(min(left_len, right_len)) / float(max(left_len, right_len))


def _choose_winner(left: _KeepRecord, right: _KeepRecord) -> tuple[_KeepRecord, _KeepRecord]:
    left_key = (left.importance, left.created_at, left.id)
    right_key = (right.importance, right.created_at, right.id)
    if left_key >= right_key:
        return left, right
    return right, left


def _safe_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run vector-memory deduplication and compaction.")
    parser.add_argument("--user-id", type=int, default=None, help="Target a single user_id. Default: all users.")
    parser.add_argument(
        "--near-threshold",
        type=float,
        default=0.85,
        help="Near-duplicate token Jaccard threshold (0.50..0.99).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply deletions. Without this flag, runs in dry-run mode.",
    )
    return parser
