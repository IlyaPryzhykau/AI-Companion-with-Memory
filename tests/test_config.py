"""Settings validation tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_strips_model_names() -> None:
    """Model names should be trimmed before pattern validation."""

    settings = Settings(
        OPENAI_CHAT_MODEL="  gpt-4o-mini  ",
        OPENAI_EMBEDDING_MODEL="  text-embedding-3-small  ",
        LOCAL_LLM_CHAT_MODEL="  llama3.1:8b  ",
        LOCAL_LLM_EMBEDDING_MODEL="  nomic-embed-text  ",
    )

    assert settings.openai_chat_model == "gpt-4o-mini"
    assert settings.openai_embedding_model == "text-embedding-3-small"
    assert settings.local_llm_chat_model == "llama3.1:8b"
    assert settings.local_llm_embedding_model == "nomic-embed-text"


def test_settings_rejects_blank_model_name() -> None:
    """Whitespace-only model names should fail settings validation."""

    with pytest.raises(ValidationError):
        Settings(OPENAI_CHAT_MODEL="   ")
