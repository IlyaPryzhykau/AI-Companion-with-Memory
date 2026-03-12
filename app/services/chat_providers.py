"""Chat model provider abstraction and implementations."""

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from openai import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ChatProvider(Protocol):
    """Provider interface for assistant chat completion generation."""

    name: str

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Generate assistant text from messages."""


@dataclass(frozen=True)
class EchoChatProvider:
    """Deterministic local placeholder chat provider."""

    name: str = "local"

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Return simple echo fallback."""

        return f"Echo: {user_message.strip()}"


@dataclass(frozen=True)
class OpenAIChatProvider:
    """OpenAI chat provider."""

    api_key: str
    model: str
    timeout_seconds: float = 15.0
    name: str = "openai"

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Generate assistant reply from OpenAI chat completions."""

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()
        except (
            AuthenticationError,
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIError,
            APIStatusError,
            ValueError,
            TypeError,
            KeyError,
            IndexError,
        ) as exc:
            logger.warning(
                "openai_chat_call_failed model=%s error_type=%s",
                self.model,
                type(exc).__name__,
            )
            raise RuntimeError(f"OpenAI chat request failed for model '{self.model}'.")


@dataclass(frozen=True)
class LocalHTTPChatProvider:
    """OpenAI-compatible local HTTP chat provider."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 15.0
    name: str = "local_http"

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Generate assistant reply using local OpenAI-compatible endpoint."""

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            return (response.choices[0].message.content or "").strip()
        except (
            AuthenticationError,
            RateLimitError,
            APITimeoutError,
            APIConnectionError,
            APIError,
            APIStatusError,
            ValueError,
            TypeError,
            KeyError,
            IndexError,
        ) as exc:
            logger.warning(
                "local_http_chat_call_failed model=%s base_url=%s error_type=%s",
                self.model,
                self.base_url,
                type(exc).__name__,
            )
            raise RuntimeError(f"Local HTTP chat request failed for model '{self.model}'.")


def get_chat_provider(settings: Settings | None = None) -> ChatProvider:
    """Resolve chat provider from runtime settings."""

    if settings is None:
        settings = get_settings()

    provider = settings.primary_llm_provider.lower().strip()
    # Backward compatibility for older ASSISTANT_PROVIDER-based configuration.
    if os.getenv("PRIMARY_LLM_PROVIDER") is None and getattr(settings, "assistant_provider", "local") == "openai":
        provider = "openai"
    if provider == "openai":
        if not settings.openai_api_key.strip():
            logger.warning("chat_provider_openai_missing_key fallback=local")
            return EchoChatProvider()
        return OpenAIChatProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_chat_model,
            timeout_seconds=settings.openai_chat_timeout_seconds,
        )
    if provider == "local_http":
        return LocalHTTPChatProvider(
            base_url=settings.local_llm_base_url,
            api_key=settings.local_llm_api_key,
            model=settings.local_llm_chat_model,
            timeout_seconds=settings.openai_chat_timeout_seconds,
        )
    if provider == "local":
        return EchoChatProvider()
    raise ValueError(
        f"Unsupported PRIMARY_LLM_PROVIDER '{settings.primary_llm_provider}'. "
        "Use 'local', 'openai', or 'local_http'."
    )


def resolve_chat_provider_with_fallback() -> ChatProvider:
    """Resolve chat provider with safe local fallback on invalid settings."""

    try:
        return get_chat_provider()
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "chat_provider_resolution_failed error=%s fallback=local",
            f"{type(exc).__name__}: {exc}",
        )
        return EchoChatProvider()
