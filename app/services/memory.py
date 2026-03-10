"""Memory extraction, storage, and retrieval service helpers."""

import re

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.memory import UserMemory, VectorMemory

FACT_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    ("name", re.compile(r"\bmy name is ([a-zA-Z][a-zA-Z\- ]{1,40})\b", re.IGNORECASE), 0.9),
    ("profession", re.compile(r"\bi am an? ([a-zA-Z][a-zA-Z\- ]{1,40})\b", re.IGNORECASE), 0.7),
    ("location", re.compile(r"\bi live in ([a-zA-Z][a-zA-Z\- ]{1,60})\b", re.IGNORECASE), 0.7),
    ("goal", re.compile(r"\bmy goal is to ([^\.\!\?]{3,100})", re.IGNORECASE), 0.8),
]


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

    db.add(
        VectorMemory(
            user_id=user_id,
            text=text.strip(),
            importance=importance,
            embedding=embedding,
        )
    )


def build_memory_context(db: Session, user_id: int, max_items: int = 5) -> str:
    """Build a compact memory context block for prompt assembly."""

    facts = db.execute(
        select(UserMemory)
        .where(UserMemory.user_id == user_id)
        .order_by(desc(UserMemory.importance), desc(UserMemory.updated_at))
        .limit(max_items)
    ).scalars().all()

    semantic = db.execute(
        select(VectorMemory)
        .where(VectorMemory.user_id == user_id)
        .order_by(desc(VectorMemory.created_at))
        .limit(max_items)
    ).scalars().all()

    lines: list[str] = []
    if facts:
        lines.append("Structured memory:")
        for fact in facts:
            lines.append(f"- {fact.key}: {fact.value}")
    if semantic:
        lines.append("Recent semantic memory:")
        for item in semantic:
            lines.append(f"- {item.text}")

    return "\n".join(lines).strip()
