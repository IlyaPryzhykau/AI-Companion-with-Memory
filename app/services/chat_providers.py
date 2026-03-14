"""Chat model provider abstraction and implementations."""

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.observability import record_provider_call
from app.services.provider_utils import PROVIDER_EXCEPTIONS, validate_http_base_url

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

        started = perf_counter()
        try:
            return f"Echo: {user_message.strip()}"
        finally:
            record_provider_call(
                provider_kind="chat",
                provider_name=self.name,
                latency_ms=(perf_counter() - started) * 1000.0,
                success=True,
            )


@dataclass(frozen=True)
class OpenAIChatProvider:
    """OpenAI chat provider."""

    api_key: str
    model: str
    timeout_seconds: float = 15.0
    name: str = "openai"

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        """Generate assistant reply from OpenAI chat completions."""

        started = perf_counter()
        try:
            client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            record_provider_call(
                provider_kind="chat",
                provider_name=self.name,
                latency_ms=(perf_counter() - started) * 1000.0,
                success=True,
            )
            return (response.choices[0].message.content or "").strip()
        except PROVIDER_EXCEPTIONS as exc:
            record_provider_call(
                provider_kind="chat",
                provider_name=self.name,
                latency_ms=(perf_counter() - started) * 1000.0,
                success=False,
            )
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

        started = perf_counter()
        try:
            client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout_seconds,
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
            )
            record_provider_call(
                provider_kind="chat",
                provider_name=self.name,
                latency_ms=(perf_counter() - started) * 1000.0,
                success=True,
            )
            return (response.choices[0].message.content or "").strip()
        except PROVIDER_EXCEPTIONS as exc:
            record_provider_call(
                provider_kind="chat",
                provider_name=self.name,
                latency_ms=(perf_counter() - started) * 1000.0,
                success=False,
            )
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
        base_url = validate_http_base_url(
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
