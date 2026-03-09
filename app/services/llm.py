"""LLM orchestration service layer."""


def generate_assistant_reply(user_message: str) -> str:
    """Return a placeholder assistant reply for bootstrap stage."""

    return f"Echo: {user_message.strip()}"
