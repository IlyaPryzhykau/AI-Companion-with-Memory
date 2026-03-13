"""Optional LLM policy layer for memory persistence decisions."""

import json
import logging
import re
from typing import Protocol

from app.core.config import Settings, get_settings
from app.services.memory_actions import MemoryAction
from app.services.chat_providers import resolve_chat_provider_with_fallback

logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = (
    re.compile(r"\b(?:password|пароль|heslo)\b", re.IGNORECASE),
    re.compile(r"\b(?:api[_ -]?key|token|secret|private[_ -]?key)\b", re.IGNORECASE),
    re.compile(r"\bsk-[a-zA-Z0-9]{16,}\b"),
    re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # card-like digit sequences
)


class _PolicyProvider(Protocol):
    """Minimal protocol for memory policy provider dependency."""

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Generate raw model response."""


def apply_memory_policy(
    user_message: str,
    actions: list[MemoryAction],
    settings: Settings | None = None,
    provider: _PolicyProvider | None = None,
) -> list[MemoryAction]:
    """Apply optional LLM policy filtering with deterministic fallback."""

    if settings is None:
        settings = get_settings()

    if _contains_sensitive_content(user_message):
        return [
            MemoryAction(
                action_type="SKIP",
                reason="sensitive_data_guardrail",
                payload={},
            )
        ]

    if settings.memory_policy_mode != "llm":
        return actions

    candidate_actions = [action for action in actions if action.action_type != "SKIP"]
    if not candidate_actions:
        return actions

    if provider is None:
        provider = resolve_chat_provider_with_fallback()

    try:
        response = provider.generate(
            messages=_build_policy_messages(user_message=user_message, actions=candidate_actions),
            user_message=user_message,
        )
        decision = _parse_policy_decision(response)
    except (RuntimeError, ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning(
            "memory_policy_fallback reason=model_failure error_type=%s",
            type(exc).__name__,
        )
        return actions

    if decision["confidence"] < settings.memory_policy_min_confidence:
        logger.info(
            "memory_policy_fallback reason=low_confidence confidence=%.3f threshold=%.3f",
            decision["confidence"],
            settings.memory_policy_min_confidence,
        )
        return actions

    if decision["decision"] == "deny":
        return [
            MemoryAction(
                action_type="SKIP",
                reason=f"policy_denied:{decision['reason']}",
                payload={"confidence": decision["confidence"]},
            )
        ]

    return actions


def _contains_sensitive_content(text: str) -> bool:
    """Return True if text appears to contain secrets or credential material."""

    return any(pattern.search(text) is not None for pattern in _SENSITIVE_PATTERNS)


def _build_policy_messages(user_message: str, actions: list[MemoryAction]) -> list[dict[str, str]]:
    """Build deterministic prompt for policy decision."""

    action_lines = [f"- {action.action_type}: {action.reason}" for action in actions]
    instructions = (
        "You are a strict memory persistence policy checker.\n"
        "Task: decide whether the proposed memory actions should be persisted.\n"
        "Return JSON only with this schema:\n"
        '{"decision":"allow|deny","confidence":0.0,"reason":"short_reason"}\n'
        "Rules:\n"
        "- deny if message looks like secrets, credentials, or private keys\n"
        "- deny if persistence is unnecessary or risky\n"
        "- allow only if persistence is useful and safe\n"
        "- confidence must be 0..1\n"
    )
    context = (
        f"User message:\n{user_message}\n\n"
        "Proposed actions:\n"
        + "\n".join(action_lines)
    )
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": context},
    ]


def _parse_policy_decision(text: str) -> dict[str, float | str]:
    """Parse structured policy decision from model output."""

    content = text.strip()
    if not content:
        raise ValueError("Empty policy response.")

    start = content.find("{")
    end = content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("Policy response does not contain JSON object.")

    payload = json.loads(content[start : end + 1])
    decision_raw = str(payload.get("decision", "")).strip().lower()
    if decision_raw not in {"allow", "deny"}:
        raise ValueError("Policy decision must be 'allow' or 'deny'.")
    confidence = float(payload.get("confidence", 0.0))
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("Policy confidence must be in range 0..1.")
    reason = str(payload.get("reason", "unspecified")).strip() or "unspecified"
    return {"decision": decision_raw, "confidence": confidence, "reason": reason}
