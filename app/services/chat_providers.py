"""Chat model provider abstraction and implementations."""

import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

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

_PROVIDER_EXCEPTIONS = (
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
)


def _validate_http_base_url(value: str, setting_name: str, app_env: str) -> str:
    """Validate OpenAI-compatible HTTP base URL."""

    base_url = value.strip()
    parsed = urlparse(base_url)
    if not base_url or parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(
            f"Invalid {setting_name} value. Expected absolute http(s) URL, got: {value!r}."
        )
    if parsed.scheme == "http" and app_env.lower().strip() not in {"development", "dev", "local", "test"}:
        raise ValueError(
            f"Unsafe {setting_name} value for APP_ENV={app_env!r}. "
            "Use https URL outside local/development environments."
        )
    return base_url


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
        except _PROVIDER_EXCEPTIONS as exc:
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
        except _PROVIDER_EXCEPTIONS as exc:
            logger.warning(
                "local_http_chat_call_failed model=%s error_type=%s",
                self.model,
                type(exc).__name__,
            )
            raise RuntimeError(f"Local HTTP chat request failed for model '{self.model}'.")


def get_chat_provider(settings: Settings | None = None) -> ChatProvider:
    """Resolve chat provider from runtime settings."""

    if settings is None:
        settings = get_settings()

    provider = settings.primary_llm_provider.lower().strip()
    fields_set = getattr(settings, "model_fields_set", set())
    primary_explicitly_set = "primary_llm_provider" in fields_set
    # Backward compatibility for older ASSISTANT_PROVIDER-based configuration.
    if (
        not primary_explicitly_set
        and provider == "local"
        and getattr(settings, "assistant_provider", "local") == "openai"
    ):
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
        if not settings.local_llm_api_key.strip():
            raise ValueError(
                "LOCAL_LLM_API_KEY must be non-empty when PRIMARY_LLM_PROVIDER=local_http."
            )
        base_url = _validate_http_base_url(
            settings.local_llm_base_url,
            "LOCAL_LLM_BASE_URL",
            getattr(settings, "app_env", "development"),
        )
        return LocalHTTPChatProvider(
            base_url=base_url,
            api_key=settings.local_llm_api_key,
            model=settings.local_llm_chat_model,
            timeout_seconds=settings.local_llm_chat_timeout_seconds,
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
            "chat_provider_resolution_failed error_type=%s fallback=local",
            type(exc).__name__,
        )
        return EchoChatProvider()
