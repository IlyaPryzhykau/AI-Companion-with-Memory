"""LLM orchestration service layer."""

import logging
import re

from app.services.chat_providers import resolve_chat_provider_with_fallback

logger = logging.getLogger(__name__)


def _extract_name_from_memory(memory_context: str | None) -> str | None:
    """Extract user name from structured memory context if available."""

    if not memory_context:
        return None
    match = re.search(r"\[S\]\s+name:\s+([^\n]+)", memory_context, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _build_openai_messages(
    user_message: str,
    memory_context: str | None,
    chat_history: list[tuple[str, str]] | None,
) -> list[dict[str, str]]:
    """Build chat-completions messages with history and anti-repeat greeting policy."""

    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are a helpful AI companion. "
                "If this conversation is already in progress, do not greet again. "
                "Continue naturally from prior context."
            ),
        }
    ]

    if memory_context:
        messages.append(
            {
                "role": "system",
                "content": f"Memory context:\n{memory_context}",
            }
        )

    normalized_history: list[tuple[str, str]] = []
    for role, content in chat_history or []:
        role_value = role.lower().strip()
        if role_value not in {"user", "assistant"}:
            continue
        text = content.strip()
        if not text:
            continue
        normalized_history.append((role_value, text))

    for role, content in normalized_history:
        messages.append({"role": role, "content": content})

    if not normalized_history or normalized_history[-1] != ("user", user_message.strip()):
        messages.append({"role": "user", "content": user_message.strip()})

    return messages


def generate_assistant_reply(
    user_message: str,
    memory_context: str | None = None,
    chat_history: list[tuple[str, str]] | None = None,
) -> str:
    """Return assistant reply using configured provider with safe local fallback."""

    normalized = user_message.strip().lower()
    if "what is my name" in normalized or "who am i" in normalized:
        remembered_name = _extract_name_from_memory(memory_context)
        if remembered_name:
            return f"You told me your name is {remembered_name}."

    provider = resolve_chat_provider_with_fallback()
    try:
        text = provider.generate(
            messages=_build_openai_messages(
                user_message=user_message,
                memory_context=memory_context,
                chat_history=chat_history,
            ),
            user_message=user_message,
        )
        if text.strip():
            return text.strip()
    except RuntimeError as exc:
        logger.warning(
            "assistant_provider_call_failed provider=%s error_type=%s fallback=echo",
            getattr(provider, "name", type(provider).__name__),
            type(exc).__name__,
        )
    return f"Echo: {user_message.strip()}"
