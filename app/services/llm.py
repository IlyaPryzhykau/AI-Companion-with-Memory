"""LLM orchestration service layer."""


def generate_assistant_reply(user_message: str, memory_context: str | None = None) -> str:
    """Return a placeholder assistant reply for bootstrap stage."""

    _ = memory_context
    return f"Echo: {user_message.strip()}"
