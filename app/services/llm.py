"""LLM orchestration service layer."""

import re


def _extract_name_from_memory(memory_context: str | None) -> str | None:
    """Extract user name from structured memory context if available."""

    if not memory_context:
        return None
    match = re.search(r"\[S\]\s+name:\s+([^\n]+)", memory_context, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def generate_assistant_reply(user_message: str, memory_context: str | None = None) -> str:
    """Return a placeholder assistant reply for bootstrap stage."""

    normalized = user_message.strip().lower()
    if "what is my name" in normalized or "who am i" in normalized:
        remembered_name = _extract_name_from_memory(memory_context)
        if remembered_name:
            return f"You told me your name is {remembered_name}."

    return f"Echo: {user_message.strip()}"
