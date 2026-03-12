"""LLM orchestration service layer."""

import logging
import re

from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _extract_name_from_memory(memory_context: str | None) -> str | None:
    """Extract user name from structured memory context if available."""

    if not memory_context:
        return None
    match = re.search(r"\[S\]\s+name:\s+([^\n]+)", memory_context, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def generate_assistant_reply(user_message: str, memory_context: str | None = None) -> str:
    """Return assistant reply using configured provider with safe local fallback."""

    normalized = user_message.strip().lower()
    if "what is my name" in normalized or "who am i" in normalized:
        remembered_name = _extract_name_from_memory(memory_context)
        if remembered_name:
            return f"You told me your name is {remembered_name}."

    settings = get_settings()
    provider = settings.assistant_provider.lower().strip()
    if provider == "openai" and settings.openai_api_key.strip():
        try:
            client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_chat_timeout_seconds,
            )
            prompt = user_message.strip()
            if memory_context:
                prompt = (
                    "Use the following memory context when helpful.\n\n"
                    f"{memory_context}\n\n"
                    f"User message: {user_message.strip()}"
                )
            response = client.chat.completions.create(
                model=settings.openai_chat_model,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.choices[0].message.content or ""
            if text.strip():
                return text.strip()
        except Exception as exc:  # pragma: no cover
            logger.warning(
                "assistant_openai_call_failed model=%s error_type=%s fallback=echo",
                settings.openai_chat_model,
                type(exc).__name__,
            )

    return f"Echo: {user_message.strip()}"
