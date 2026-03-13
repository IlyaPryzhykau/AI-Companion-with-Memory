"""Shared memory action types."""

from dataclasses import dataclass
from typing import Any, Literal

MemoryActionType = Literal["UPSERT_FACTS", "STORE_EPISODIC", "SKIP"]


@dataclass(frozen=True)
class MemoryAction:
    """Typed memory action produced by memory orchestration."""

    action_type: MemoryActionType
    reason: str
    payload: dict[str, Any]
