"""Memory extraction, storage, and retrieval service helpers."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import UserMemory
from app.services.vector_store import VectorSearchResult, get_vector_store

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "can",
    "for",
    "from",
    "help",
    "i",
    "in",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "you",
    "your",
}

FACT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("name", re.compile(r"\bmy name is ([a-zA-Z][a-zA-Z\- ]{1,40})\b", re.IGNORECASE), 0.9),
    ("profession", re.compile(r"\bi am an? ([a-zA-Z][a-zA-Z\- ]{1,40})\b", re.IGNORECASE), 0.7),
    ("location", re.compile(r"\bi live in ([a-zA-Z][a-zA-Z\- ]{1,60})\b", re.IGNORECASE), 0.7),
    ("goal", re.compile(r"\bmy goal is to ([^\.\!\?]{3,100})", re.IGNORECASE), 0.8),
]


@dataclass
class MemoryCandidate:
    """Normalized memory candidate used by retrieval policy."""

    kind: str
    text: str
    importance: float
    recency_score: float
    relevance_score: float
    final_score: float


def extract_structured_facts(text: str) -> list[tuple[str, str, float]]:
    """Extract simple structured facts from a user message."""

    facts: list[tuple[str, str, float]] = []
    for key, pattern, importance in FACT_PATTERNS:
        match = pattern.search(text)
        if match:
            value = match.group(1).strip(" .")
            facts.append((key, value, importance))
    return facts


def upsert_structured_memory(
    db: Session,
    user_id: int,
    facts: list[tuple[str, str, float]],
    source: str = "chat_message",
) -> None:
    """Insert or update structured memory records for a user."""

    for key, value, importance in facts:
        existing = db.execute(
            select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.key == key)
        ).scalar_one_or_none()
        if existing:
            existing.value = value
            existing.importance = max(existing.importance, importance)
            existing.source = source
        else:
            db.add(
                UserMemory(
                    user_id=user_id,
                    key=key,
                    value=value,
                    importance=importance,
                    source=source,
                )
            )


def store_vector_memory(
    db: Session,
    user_id: int,
    text: str,
    importance: float = 0.5,
    embedding: list[float] | None = None,
) -> None:
    """Store a semantic memory chunk with optional embedding."""

    vector_store = get_vector_store()
    vector_store.store(
        db=db,
        user_id=user_id,
        text_value=text,
        importance=importance,
        embedding=embedding,
    )


def _safe_utc(dt: datetime | None) -> datetime:
    """Normalize a datetime value to UTC."""

    if dt is None:
        return datetime.now(UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _recency_score(created_at: datetime | None, now: datetime) -> float:
    """Convert age to a 0..1 recency score with a simple 7-day decay window."""

    age_hours = max(0.0, (now - _safe_utc(created_at)).total_seconds() / 3600.0)
    return max(0.0, 1.0 - min(age_hours / (24.0 * 7.0), 1.0))


def _tokenize(text: str) -> set[str]:
    """Tokenize plain text into lowercase alphanumeric words."""

    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]{2,}", text.lower())
        if token not in STOP_WORDS
    }


def _relevance_score(query: str, text: str) -> float:
    """Estimate lexical relevance score between query and memory text."""

    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    memory_tokens = _tokenize(text)
    if not memory_tokens:
        return 0.0

    match_count = 0
    for query_token in query_tokens:
        query_prefix = query_token[:5]
        if any(
            query_token == memory_token
            or memory_token.startswith(query_prefix)
            or query_token.startswith(memory_token[:5])
            for memory_token in memory_tokens
        ):
            match_count += 1
    return match_count / len(query_tokens)


def _build_structured_candidates(
    facts: list[UserMemory],
    user_query: str,
    now: datetime,
) -> list[MemoryCandidate]:
    """Build scored structured-memory candidates."""

    candidates: list[MemoryCandidate] = []
    for fact in facts:
        text = f"{fact.key}: {fact.value}"
        relevance = _relevance_score(user_query, text)
        recency = _recency_score(fact.updated_at, now)
        score = (fact.importance * 0.55) + (relevance * 0.30) + (recency * 0.15)
        candidates.append(
            MemoryCandidate(
                kind="structured",
                text=text,
                importance=fact.importance,
                recency_score=recency,
                relevance_score=relevance,
                final_score=score,
            )
        )
    return candidates


def _build_vector_candidates(
    semantic: list[VectorSearchResult],
    now: datetime,
) -> list[MemoryCandidate]:
    """Build scored vector-memory candidates."""

    candidates: list[MemoryCandidate] = []
    for item in semantic:
        relevance = item.similarity
        recency = _recency_score(item.created_at, now)
        score = (item.importance * 0.20) + (relevance * 0.70) + (recency * 0.10)
        candidates.append(
            MemoryCandidate(
                kind="semantic",
                text=item.text,
                importance=item.importance,
                recency_score=recency,
                relevance_score=relevance,
                final_score=score,
            )
        )
    return candidates


def build_memory_context(
    db: Session,
    user_id: int,
    user_query: str = "",
    max_items: int = 6,
    max_chars: int = 800,
) -> str:
    """Build ranked memory context for prompt assembly with budget limits."""

    vector_store = get_vector_store()
    facts = db.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalars().all()
    semantic = vector_store.search(
        db=db,
        user_id=user_id,
        query=user_query,
        limit=max_items * 3,
    )

    now = datetime.now(UTC)
    candidates = _build_structured_candidates(facts, user_query, now)
    candidates.extend(_build_vector_candidates(semantic, now))

    sorted_candidates = sorted(
        candidates,
        key=lambda item: (item.final_score, item.importance, item.recency_score),
        reverse=True,
    )
    top_candidates = sorted_candidates[:max_items]

    header = "Retrieved memory context:"
    content_budget = max(0, max_chars - len(header) - 1)
    if content_budget == 0:
        return ""

    lines: list[str] = []
    chars_used = 0
    dropped_due_to_budget = 0
    for candidate in top_candidates:
        prefix = "S" if candidate.kind == "structured" else "V"
        line = f"- [{prefix}] {candidate.text.strip()}"
        if len(line) > content_budget:
            if content_budget <= 3:
                dropped_due_to_budget += 1
                continue
            line = f"{line[: content_budget - 3].rstrip()}..."

        projected = chars_used + len(line) + (1 if lines else 0)
        if projected > content_budget:
            dropped_due_to_budget += 1
            continue
        lines.append(line)
        chars_used = projected

    if not lines:
        return ""

    logger.info(
        "memory_retrieval user_id=%s backend=%s query_tokens=%s candidates=%s selected=%s dropped_budget=%s max_items=%s max_chars=%s used_chars=%s",
        user_id,
        type(vector_store).__name__,
        len(_tokenize(user_query)),
        len(candidates),
        len(lines),
        dropped_due_to_budget,
        max_items,
        content_budget,
        chars_used,
    )

    return header + "\n" + "\n".join(lines)
