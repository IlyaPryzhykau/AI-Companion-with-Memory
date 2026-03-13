"""Rules-based memory orchestration and action audit helpers."""

import re

from sqlalchemy.orm import Session

from app.models.memory import MemoryActionAudit
from app.services.memory_actions import MemoryAction
from app.services.memory import extract_structured_facts, store_vector_memory, upsert_structured_memory
from app.services.memory_policy import apply_memory_policy

_SKIP_PHRASES = {
    "ok",
    "okay",
    "thanks",
    "thank you",
    "got it",
    "понял",
    "понял спасибо",
    "ок",
    "спасибо",
    "ясно",
    "добре",
    "diky",
    "děkuji",
}

class MemoryOrchestrator:
    """Deterministic rules-based orchestrator for memory persistence."""

    def plan(self, user_message: str) -> list[MemoryAction]:
        """Build ordered memory actions for an incoming user message."""

        text = user_message.strip()
        if not text:
            return [MemoryAction(action_type="SKIP", reason="empty_message", payload={})]

        facts = extract_structured_facts(text)
        actions: list[MemoryAction] = []

        if facts:
            payload_facts = [{"key": key, "value": value, "importance": importance} for key, value, importance in facts]
            actions.append(
                MemoryAction(
                    action_type="UPSERT_FACTS",
                    reason="structured_facts_detected",
                    payload={"facts": payload_facts},
                )
            )

        if self._should_store_episodic(text=text, facts=facts):
            actions.append(
                MemoryAction(
                    action_type="STORE_EPISODIC",
                    reason="episodic_signal_detected",
                    payload={
                        "text": text,
                        "importance": self._episodic_importance(text=text, facts=facts),
                    },
                )
            )

        if actions:
            return actions
        return [MemoryAction(action_type="SKIP", reason="no_memory_signal", payload={})]

    def _should_store_episodic(self, text: str, facts: list[tuple[str, str, float]]) -> bool:
        """Return True when message is a relevant episodic memory candidate."""

        if facts:
            return True

        normalized = self._normalize_phrase(text)
        if normalized in _SKIP_PHRASES:
            return False

        tokens = re.findall(r"[^\W_]{2,}", normalized, flags=re.UNICODE)
        if len(tokens) < 3:
            return False

        personal_markers = (
            " i ",
            " my ",
            " me ",
            " я ",
            " меня ",
            " мне ",
            " мой ",
            " моя ",
            " у меня ",
            " jsem ",
            " mám ",
            " muj ",
            " můj ",
            " moje ",
        )
        marker_text = f" {normalized} "
        has_personal_signal = any(marker in marker_text for marker in personal_markers)
        if has_personal_signal:
            return True

        if normalized.endswith("?"):
            return len(tokens) >= 8

        return len(text) >= 28

    def _episodic_importance(self, text: str, facts: list[tuple[str, str, float]]) -> float:
        """Compute deterministic importance score for episodic storage."""

        importance = 0.55
        if facts:
            importance = max(importance, max(item[2] for item in facts))

        lowered = text.lower()
        if any(marker in lowered for marker in ("goal", "цель", "cíl", "хочу", "want", "chci")):
            importance += 0.15
        if len(text) >= 160:
            importance += 0.05
        return min(0.95, round(importance, 2))

    @staticmethod
    def _normalize_phrase(text: str) -> str:
        """Normalize text into lowercase phrase for deterministic matching."""

        lowered = text.lower().strip()
        lowered = re.sub(r"\s+", " ", lowered)
        lowered = re.sub(r"[^\w\sа-яёčďěňřšťůžáíéýúů]", "", lowered, flags=re.IGNORECASE)
        return lowered.strip()


def apply_memory_actions(
    db: Session,
    user_id: int,
    chat_id: int | None,
    user_message: str,
    source: str = "chat_message",
) -> list[MemoryAction]:
    """Run rules orchestration, execute actions, and persist action audit."""

    orchestrator = MemoryOrchestrator()
    planned_actions = orchestrator.plan(user_message)
    actions = apply_memory_policy(user_message=user_message, actions=planned_actions)

    for action in actions:
        if action.action_type == "UPSERT_FACTS":
            facts_payload = action.payload.get("facts", [])
            facts: list[tuple[str, str, float]] = [
                (item["key"], item["value"], float(item["importance"]))
                for item in facts_payload
            ]
            upsert_structured_memory(db, user_id=user_id, facts=facts, source=source)
        elif action.action_type == "STORE_EPISODIC":
            store_vector_memory(
                db,
                user_id=user_id,
                text=action.payload["text"],
                importance=float(action.payload["importance"]),
            )

        db.add(
            MemoryActionAudit(
                user_id=user_id,
                chat_id=chat_id,
                action_type=action.action_type,
                reason=action.reason,
                payload_json=action.payload,
            )
        )

    return actions
