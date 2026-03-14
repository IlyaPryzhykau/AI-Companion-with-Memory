"""Memory extraction, storage, and retrieval service helpers."""

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chat import Chat, Message
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
    "ahoj",
    "ale",
    "co",
    "do",
    "ja",
    "jak",
    "jako",
    "je",
    "na",
    "nebo",
    "pro",
    "se",
    "to",
    "ve",
    "z",
    "а",
    "без",
    "в",
    "во",
    "да",
    "для",
    "и",
    "или",
    "к",
    "как",
    "на",
    "не",
    "но",
    "о",
    "по",
    "под",
    "с",
    "со",
    "то",
    "у",
    "что",
    "это",
    "я",
}

FACT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("name", re.compile(r"\bmy name is\s+([^\W\d_][^\n\r\.\!\?,]{1,50})", re.IGNORECASE), 0.9),
    ("name", re.compile(r"\bменя зовут\s+([^\W\d_][^\n\r\.\!\?,]{1,50})", re.IGNORECASE), 0.9),
    ("name", re.compile(r"\bjmenuji se\s+([^\W\d_][^\n\r\.\!\?,]{1,50})", re.IGNORECASE), 0.9),
    (
        "name",
        re.compile(r"^\s*я\s+([А-Яа-яЁё][А-Яа-яЁё\-]{1,30})(?:\s*[,.!?]|$)", re.IGNORECASE),
        0.8,
    ),
    ("profession", re.compile(r"\bi am an?\s+([^\W\d_][^\n\r\.\!\?,]{1,50})", re.IGNORECASE), 0.7),
    ("profession", re.compile(r"\bя работаю\s+([^\n\r\.\!\?]{2,80})", re.IGNORECASE), 0.7),
    ("profession", re.compile(r"\bpracuji jako\s+([^\n\r\.\!\?]{2,80})", re.IGNORECASE), 0.7),
    ("location", re.compile(r"\bi live in\s+([^\n\r\.\!\?]{2,80})", re.IGNORECASE), 0.7),
    ("location", re.compile(r"\bя живу в\s+([^\n\r\.\!\?]{2,80})", re.IGNORECASE), 0.7),
    ("location", re.compile(r"\bbydl[ií]m v\s+([^\n\r\.\!\?]{2,80})", re.IGNORECASE), 0.7),
    ("goal", re.compile(r"\bmy goal is to\s+([^\.\!\?]{3,100})", re.IGNORECASE), 0.8),
    ("goal", re.compile(r"\bмоя цель\s*[-: ]\s*([^\.\!\?]{3,100})", re.IGNORECASE), 0.8),
    ("goal", re.compile(r"\bm[ůu]j c[ií]l\s*[-: ]\s*([^\.\!\?]{3,100})", re.IGNORECASE), 0.8),
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
    max_tokens: int
    candidate_multiplier: int
    profile_top_k: int
    episodic_top_k: int
    semantic_top_k: int
    weight_relevance: float
    weight_importance: float
    weight_recency: float


def extract_structured_facts(text: str) -> list[tuple[str, str, float]]:
    """Extract simple structured facts from a user message."""

    facts: list[tuple[str, str, float]] = []
    seen: set[tuple[str, str]] = set()
    for key, pattern, importance in FACT_PATTERNS:
        match = pattern.search(text)
        if match:
            value = _normalize_fact_value(key=key, value=match.group(1))
            if not value:
                continue
            dedupe_key = (key, value.lower())
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            facts.append((key, value, importance))
    return facts


def _normalize_fact_value(key: str, value: str) -> str:
    """Normalize captured fact values for stable multilingual storage."""

    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n,.;:!?-")
    if not cleaned:
        return ""

    if key == "name":
        name_tokens = re.findall(r"[^\W\d_][^\W\d_'\-]{0,30}", cleaned, flags=re.UNICODE)
        if not name_tokens:
            return ""
        return " ".join(name_tokens[:3]).strip()

    return cleaned


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
    """Tokenize plain text into lowercase Unicode words."""

    return {
        token
        for token in re.findall(r"[^\W\d_]{2,}", text.lower(), flags=re.UNICODE)
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


def _build_episodic_candidates(
    db: Session,
    user_id: int,
    user_query: str,
    now: datetime,
    policy: RetrievalPolicy,
) -> list[MemoryCandidate]:
    """Build scored episodic candidates from recent user messages."""

    safe_user_id = _validate_user_id(user_id, log_prefix="episodic_retrieval")
    if safe_user_id is None:
        return []

    row_limit = min(100, max(5, policy.episodic_top_k * policy.candidate_multiplier * 3))
    try:
        rows = (
            db.execute(
                select(Message.content, Message.created_at)
                .join(Chat, Chat.id == Message.chat_id)
                .where(Chat.user_id == safe_user_id, Message.role == "user")
                .order_by(Message.id.desc())
                .limit(row_limit)
            )
            .all()
        )
    except (SQLAlchemyError, DBAPIError) as exc:
        logger.warning(
            "episodic_retrieval_failed user_id=%s error_type=%s",
            safe_user_id,
            type(exc).__name__,
        )
        return []

    candidates: list[MemoryCandidate] = []
    for content, created_at in rows:
        text = (content or "").strip()
        if not text:
            continue
        relevance = _relevance_score(user_query, text)
        recency = _recency_score(created_at, now)
        importance = 0.50
        score = (
            (importance * policy.weight_importance)
            + (relevance * policy.weight_relevance)
            + (recency * policy.weight_recency)
        )
        candidates.append(
            MemoryCandidate(
                kind="episodic",
                text=text,
                importance=importance,
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

    safe_user_id = _validate_user_id(user_id, log_prefix="memory_retrieval")
    if safe_user_id is None:
        return ""

    policy = _resolve_retrieval_policy(max_items=max_items, max_chars=max_chars)
    vector_store = _resolve_vector_store()
    try:
        facts = db.execute(select(UserMemory).where(UserMemory.user_id == safe_user_id)).scalars().all()
    except (SQLAlchemyError, DBAPIError) as exc:
        logger.warning(
            "structured_retrieval_failed user_id=%s error_type=%s",
            safe_user_id,
            type(exc).__name__,
        )
        facts = []

    semantic_limit = max(1, policy.semantic_top_k) * policy.candidate_multiplier
    try:
        semantic = vector_store.search(
            db=db,
            user_id=safe_user_id,
            query=user_query,
            limit=semantic_limit,
        )
    except Exception as exc:
        logger.warning(
            "semantic_retrieval_failed user_id=%s backend=%s error_type=%s",
            safe_user_id,
            type(vector_store).__name__,
            type(exc).__name__,
        )
        semantic = []

    now = datetime.now(UTC)
    structured_candidates = _build_structured_candidates(facts, user_query, now, policy=policy)
    episodic_candidates = _build_episodic_candidates(db, safe_user_id, user_query, now, policy=policy)
    semantic_candidates = _build_vector_candidates(semantic, now, policy=policy)

    structured_candidates = _rank_candidates(structured_candidates)[: policy.profile_top_k]
    episodic_candidates = _rank_candidates(episodic_candidates)[: policy.episodic_top_k]
    semantic_candidates = _rank_candidates(semantic_candidates)[: policy.semantic_top_k]

    candidates: list[MemoryCandidate] = []
    candidates.extend(structured_candidates)
    candidates.extend(episodic_candidates)
    candidates.extend(semantic_candidates)

    sorted_candidates = _rank_candidates(candidates)
    top_candidates = sorted_candidates[: policy.top_k]

    header = "Retrieved memory context:"
    content_budget = max(0, policy.max_chars - len(header) - 1)
    if content_budget == 0:
        return ""

    lines, chars_used, tokens_used, dropped_due_to_budget = _pack_candidates(
        candidates=top_candidates,
        char_budget=content_budget,
        token_budget=policy.max_tokens,
    )

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
        "memory_retrieval user_id=%s backend=%s query_tokens=%s candidates_total=%s structured=%s episodic=%s semantic=%s selected=%s dropped_budget=%s top_k=%s max_chars=%s max_tokens=%s used_chars=%s used_tokens=%s layer_limits=(profile=%s,episodic=%s,semantic=%s) weights=(rel=%.2f,imp=%.2f,rec=%.2f) selected_candidates=%s",
        safe_user_id,
        type(vector_store).__name__,
        len(_tokenize(user_query)),
        len(candidates),
        len(structured_candidates),
        len(episodic_candidates),
        len(semantic_candidates),
        len(lines),
        dropped_due_to_budget,
        policy.top_k,
        content_budget,
        policy.max_tokens,
        chars_used,
        tokens_used,
        policy.profile_top_k,
        policy.episodic_top_k,
        policy.semantic_top_k,
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
            max_tokens=220,
            candidate_multiplier=3,
            profile_top_k=2,
            episodic_top_k=2,
            semantic_top_k=6,
            weight_relevance=0.65,
            weight_importance=0.25,
            weight_recency=0.10,
        )
    try:
        configured_top_k = settings.memory_retrieval_top_k if max_items is None else max_items
        configured_max_chars = settings.memory_context_max_chars if max_chars is None else max_chars
        raw_max_tokens = settings.memory_context_max_tokens
        raw_multiplier = settings.memory_retrieval_candidate_multiplier
        raw_profile_top_k = settings.memory_retrieval_profile_top_k
        raw_episodic_top_k = settings.memory_retrieval_episodic_top_k
        raw_semantic_top_k = settings.memory_retrieval_semantic_top_k
        raw_weight_relevance = settings.memory_weight_relevance
        raw_weight_importance = settings.memory_weight_importance
        raw_weight_recency = settings.memory_weight_recency
    except AttributeError as exc:
        logger.warning(
            "memory_retrieval_settings_attribute_missing error_type=%s using_defaults=true",
            type(exc).__name__,
        )
        configured_top_k = 6 if max_items is None else max_items
        configured_max_chars = 800 if max_chars is None else max_chars
        raw_max_tokens = 220
        raw_multiplier = 3
        raw_profile_top_k = 2
        raw_episodic_top_k = 2
        raw_semantic_top_k = 6
        raw_weight_relevance = 0.65
        raw_weight_importance = 0.25
        raw_weight_recency = 0.10

    top_k = _coerce_int(_coalesce(configured_top_k, 6), default=6, min_value=1, max_value=20)
    max_context_chars = _coerce_int(_coalesce(configured_max_chars, 800), default=800, min_value=80, max_value=8000)
    max_context_tokens = _coerce_int(_coalesce(raw_max_tokens, 220), default=220, min_value=20, max_value=4000)
    multiplier = _coerce_int(_coalesce(raw_multiplier, 3), default=3, min_value=1, max_value=10)
    profile_top_k = _coerce_int(_coalesce(raw_profile_top_k, 2), default=2, min_value=0, max_value=20)
    episodic_top_k = _coerce_int(_coalesce(raw_episodic_top_k, 2), default=2, min_value=0, max_value=20)
    semantic_top_k = _coerce_int(_coalesce(raw_semantic_top_k, 6), default=6, min_value=0, max_value=50)
    weights = _normalize_weights(
        _coalesce(raw_weight_relevance, 0.65),
        _coalesce(raw_weight_importance, 0.25),
        _coalesce(raw_weight_recency, 0.10),
    )
    return RetrievalPolicy(
        top_k=top_k,
        max_chars=max_context_chars,
        max_tokens=max_context_tokens,
        candidate_multiplier=multiplier,
        profile_top_k=profile_top_k,
        episodic_top_k=episodic_top_k,
        semantic_top_k=semantic_top_k,
        weight_relevance=weights[0],
        weight_importance=weights[1],
        weight_recency=weights[2],
    )


def _rank_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    """Sort candidates deterministically by score and stable tie-breakers."""

    kind_priority = {"structured": 3, "episodic": 2, "semantic": 1}
    return sorted(
        candidates,
        key=lambda item: (
            item.final_score,
            item.importance,
            item.recency_score,
            kind_priority.get(item.kind, 0),
            item.text.lower(),
        ),
        reverse=True,
    )


def _estimate_token_count(text: str) -> int:
    """Approximate token count for budget packing."""

    if not isinstance(text, str):
        return 1
    try:
        words = len(re.findall(r"\S+", text))
    except re.error:
        return max(1, len(text) // 4)
    return max(1, int(words * 1.3))


def _coalesce(value, fallback):
    """Return fallback when value is None."""

    return fallback if value is None else value


def _validate_user_id(user_id: int, log_prefix: str) -> int | None:
    """Validate user identifier for retrieval queries."""

    try:
        safe_user_id = int(user_id)
    except (TypeError, ValueError):
        logger.warning("%s_invalid_user_id user_id=%r", log_prefix, user_id)
        return None
    if safe_user_id <= 0:
        logger.warning("%s_invalid_user_id_non_positive user_id=%r", log_prefix, user_id)
        return None
    return safe_user_id


def _pack_candidates(
    candidates: list[MemoryCandidate],
    char_budget: int,
    token_budget: int,
) -> tuple[list[str], int, int, int]:
    """Pack context lines under char and token budgets."""

    lines: list[str] = []
    chars_used = 0
    tokens_used = 0
    dropped_due_to_budget = 0

    for candidate in candidates:
        prefix = {"structured": "S", "episodic": "E", "semantic": "V"}.get(candidate.kind, "M")
        line = f"- [{prefix}] {candidate.text.strip()}"
        if len(line) > char_budget:
            if char_budget <= 3:
                dropped_due_to_budget += 1
                continue
            line = f"{line[: char_budget - 3].rstrip()}..."

        line_tokens = _estimate_token_count(line)
        projected_chars = chars_used + len(line) + (1 if lines else 0)
        projected_tokens = tokens_used + line_tokens
        if projected_chars > char_budget or projected_tokens > token_budget:
            dropped_due_to_budget += 1
            continue

        lines.append(line)
        chars_used = projected_chars
        tokens_used = projected_tokens

    return lines, chars_used, tokens_used, dropped_due_to_budget
