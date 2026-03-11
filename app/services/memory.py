"""Memory extraction, storage, and retrieval service helpers."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.memory import UserMemory
from app.services.vector_store import (
    SUPPORTED_EMBEDDING_DIMENSIONS,
    JsonVectorStore,
    VectorSearchResult,
    get_vector_store,
)

logger = logging.getLogger(__name__)


def _resolve_vector_store():
    """Resolve configured vector store with safe JSON fallback on misconfiguration."""

    try:
        return get_vector_store()
    except ValueError as exc:
        logger.warning("vector_store_config_invalid error=%s fallback=JsonVectorStore", exc)
        return JsonVectorStore(dimensions=SUPPORTED_EMBEDDING_DIMENSIONS)

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


@dataclass(frozen=True)
class RetrievalPolicy:
    """Runtime retrieval policy resolved from config + request overrides."""

    top_k: int
    max_chars: int
    candidate_multiplier: int
    weight_relevance: float
    weight_importance: float
    weight_recency: float


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

    vector_store = _resolve_vector_store()
    savepoint = db.begin_nested()
    try:
        vector_store.store(
            db=db,
            user_id=user_id,
            text_value=text,
            importance=importance,
            embedding=embedding,
        )
        savepoint.commit()
    except (SQLAlchemyError, ValueError) as exc:
        savepoint.rollback()
        if isinstance(exc, DBAPIError) and exc.connection_invalidated:
            raise
        logger.warning(
            "vector_store_write_failed user_id=%s backend=%s error=%s",
            user_id,
            type(vector_store).__name__,
            f"{type(exc).__name__}: {exc}",
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
    policy: RetrievalPolicy,
) -> list[MemoryCandidate]:
    """Build scored structured-memory candidates."""

    candidates: list[MemoryCandidate] = []
    for fact in facts:
        text = f"{fact.key}: {fact.value}"
        relevance = _relevance_score(user_query, text)
        recency = _recency_score(fact.updated_at, now)
        score = (
            (fact.importance * policy.weight_importance)
            + (relevance * policy.weight_relevance)
            + (recency * policy.weight_recency)
        )
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
    policy: RetrievalPolicy,
) -> list[MemoryCandidate]:
    """Build scored vector-memory candidates."""

    candidates: list[MemoryCandidate] = []
    for item in semantic:
        relevance = item.similarity
        recency = _recency_score(item.created_at, now)
        score = (
            (item.importance * policy.weight_importance)
            + (relevance * policy.weight_relevance)
            + (recency * policy.weight_recency)
        )
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
    max_items: int | None = None,
    max_chars: int | None = None,
) -> str:
    """Build ranked memory context for prompt assembly with budget limits."""

    policy = _resolve_retrieval_policy(max_items=max_items, max_chars=max_chars)
    vector_store = _resolve_vector_store()
    facts = db.execute(select(UserMemory).where(UserMemory.user_id == user_id)).scalars().all()
    semantic = vector_store.search(
        db=db,
        user_id=user_id,
        query=user_query,
        limit=policy.top_k * policy.candidate_multiplier,
    )

    now = datetime.now(UTC)
    candidates = _build_structured_candidates(facts, user_query, now, policy=policy)
    candidates.extend(_build_vector_candidates(semantic, now, policy=policy))

    sorted_candidates = sorted(
        candidates,
        key=lambda item: (item.final_score, item.importance, item.recency_score),
        reverse=True,
    )
    top_candidates = sorted_candidates[: policy.top_k]

    header = "Retrieved memory context:"
    content_budget = max(0, policy.max_chars - len(header) - 1)
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

    selected_details = [
        (
            f"{item.kind}|score={item.final_score:.3f}|rel={item.relevance_score:.3f}|"
            f"imp={item.importance:.3f}|rec={item.recency_score:.3f}|text={item.text[:48]!r}"
        )
        for item in top_candidates[: min(len(top_candidates), 5)]
    ]
    logger.info(
        "memory_retrieval user_id=%s backend=%s query_tokens=%s candidates=%s selected=%s dropped_budget=%s top_k=%s max_chars=%s used_chars=%s weights=(rel=%.2f,imp=%.2f,rec=%.2f) selected_candidates=%s",
        user_id,
        type(vector_store).__name__,
        len(_tokenize(user_query)),
        len(candidates),
        len(lines),
        dropped_due_to_budget,
        policy.top_k,
        content_budget,
        chars_used,
        policy.weight_relevance,
        policy.weight_importance,
        policy.weight_recency,
        selected_details,
    )

    return header + "\n" + "\n".join(lines)


def _coerce_int(value: int, default: int, min_value: int, max_value: int) -> int:
    """Clamp integer config values to safe limits."""

    if not isinstance(value, int):
        return default
    return max(min_value, min(value, max_value))


def _normalize_weights(relevance: float, importance: float, recency: float) -> tuple[float, float, float]:
    """Normalize retrieval weights to sum to 1.0 with safe defaults."""

    weights = [max(0.0, relevance), max(0.0, importance), max(0.0, recency)]
    total = sum(weights)
    if total < 1e-10:
        logger.warning(
            "memory_retrieval_weight_normalization_fallback reason=near_zero_sum raw_weights=(%.6f,%.6f,%.6f)",
            relevance,
            importance,
            recency,
        )
        return 0.65, 0.25, 0.10
    return (weights[0] / total, weights[1] / total, weights[2] / total)


def _resolve_retrieval_policy(max_items: int | None, max_chars: int | None) -> RetrievalPolicy:
    """Resolve retrieval knobs from settings with optional runtime overrides."""

    try:
        settings = get_settings()
    except ValidationError as exc:
        logger.error(
            "memory_retrieval_settings_resolution_failed error=%s using_defaults=true",
            f"{type(exc).__name__}: {exc}",
        )
        return RetrievalPolicy(
            top_k=_coerce_int(max_items if max_items is not None else 6, default=6, min_value=1, max_value=20),
            max_chars=_coerce_int(
                max_chars if max_chars is not None else 800,
                default=800,
                min_value=80,
                max_value=8000,
            ),
            candidate_multiplier=3,
            weight_relevance=0.65,
            weight_importance=0.25,
            weight_recency=0.10,
        )
    configured_top_k = settings.memory_retrieval_top_k if max_items is None else max_items
    configured_max_chars = settings.memory_context_max_chars if max_chars is None else max_chars
    top_k = _coerce_int(configured_top_k, default=6, min_value=1, max_value=20)
    max_context_chars = _coerce_int(configured_max_chars, default=800, min_value=80, max_value=8000)
    multiplier = _coerce_int(
        settings.memory_retrieval_candidate_multiplier,
        default=3,
        min_value=1,
        max_value=10,
    )
    weights = _normalize_weights(
        settings.memory_weight_relevance,
        settings.memory_weight_importance,
        settings.memory_weight_recency,
    )
    return RetrievalPolicy(
        top_k=top_k,
        max_chars=max_context_chars,
        candidate_multiplier=multiplier,
        weight_relevance=weights[0],
        weight_importance=weights[1],
        weight_recency=weights[2],
    )
