"""Embedding providers used by memory vector storage/search."""

import hashlib
import logging
import math
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
from app.services.vector_validation import validate_embedding_vector

logger = logging.getLogger(__name__)


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


class EmbeddingProvider(Protocol):
    """Provider interface for generating text embeddings."""

    name: str

    def embed(self, text: str, dimensions: int) -> list[float]:
        """Return an embedding vector for input text."""


def _normalize(values: list[float]) -> list[float]:
    """Normalize vector values to unit length."""

    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        return values
    return [value / norm for value in values]


@dataclass(frozen=True)
class LocalHashEmbeddingProvider:
    """Deterministic local embedding provider for offline/fallback mode."""

    name: str = "local"

    def embed(self, text: str, dimensions: int) -> list[float]:
        """Build deterministic token-hash embedding and validate dimensions."""

        vector = [0.0] * dimensions
        tokens = [token for token in text.lower().split() if token]
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], byteorder="big") % dimensions
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + (digest[3] / 255.0) * 0.1
            vector[index] += sign * weight

        return validate_embedding_vector(_normalize(vector), expected_dimensions=dimensions)


@dataclass(frozen=True)
class OpenAIEmbeddingProvider:
    """OpenAI embeddings provider."""

    api_key: str
    model: str
    timeout_seconds: float = 10.0
    name: str = "openai"

    def embed(self, text: str, dimensions: int) -> list[float]:
        """Generate embedding from OpenAI API and validate output shape."""

        client = OpenAI(api_key=self.api_key, timeout=self.timeout_seconds)
        try:
            response = client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=dimensions,
            )
            if (
                not getattr(response, "data", None)
                or not response.data
                or not getattr(response.data[0], "embedding", None)
            ):
                raise ValueError("OpenAI embedding response is missing embedding payload.")
            if len(response.data[0].embedding) != dimensions:
                raise ValueError(
                    "OpenAI embedding response dimension mismatch: "
                    f"expected {dimensions}, got {len(response.data[0].embedding)}."
                )
            vector = [float(value) for value in response.data[0].embedding]
            return validate_embedding_vector(vector, expected_dimensions=dimensions)
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
                "openai_embedding_call_failed model=%s error_type=%s",
                self.model,
                type(exc).__name__,
            )
            raise RuntimeError(
                f"OpenAI embedding request failed for model '{self.model}'."
            )


@dataclass(frozen=True)
class LocalHTTPEmbeddingProvider:
    """OpenAI-compatible local HTTP embedding provider."""

    base_url: str
    api_key: str
    model: str
    timeout_seconds: float = 10.0
    name: str = "local_http"

    def embed(self, text: str, dimensions: int) -> list[float]:
        """Generate embedding from local OpenAI-compatible API and validate output shape."""

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout_seconds,
        )
        try:
            response = client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=dimensions,
            )
            if (
                not getattr(response, "data", None)
                or not response.data
                or not getattr(response.data[0], "embedding", None)
            ):
                raise ValueError("Local HTTP embedding response is missing embedding payload.")
            if len(response.data[0].embedding) != dimensions:
                raise ValueError(
                    "Local HTTP embedding response dimension mismatch: "
                    f"expected {dimensions}, got {len(response.data[0].embedding)}."
                )
            vector = [float(value) for value in response.data[0].embedding]
            return validate_embedding_vector(vector, expected_dimensions=dimensions)
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
                "local_http_embedding_call_failed model=%s base_url=%s error_type=%s",
                self.model,
                self.base_url,
                type(exc).__name__,
            )
            raise RuntimeError(
                f"Local HTTP embedding request failed for model '{self.model}'."
            )


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Resolve embedding provider from settings with safe local fallback."""

    if settings is None:
        settings = get_settings()

    provider = settings.embedding_provider.lower().strip()
    if provider not in {"local", "openai", "local_http"}:
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. "
            "Use 'local', 'openai', or 'local_http'."
        )

    if provider == "openai":
        if not settings.openai_api_key.strip():
            logger.warning("embedding_provider_openai_missing_key fallback=local")
            return LocalHashEmbeddingProvider()
        return OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            timeout_seconds=settings.openai_embedding_timeout_seconds,
        )
    if provider == "local_http":
        base_url = _validate_http_base_url(
            settings.local_llm_base_url,
            "LOCAL_LLM_BASE_URL",
            getattr(settings, "app_env", "development"),
        )
        return LocalHTTPEmbeddingProvider(
            base_url=base_url,
            api_key=settings.local_llm_api_key,
            model=settings.local_llm_embedding_model,
            timeout_seconds=settings.local_llm_embedding_timeout_seconds,
        )

    return LocalHashEmbeddingProvider()


def resolve_embedding_provider_with_fallback() -> EmbeddingProvider:
    """Resolve provider with guard against settings validation failures."""

    try:
        return get_embedding_provider()
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "embedding_provider_resolution_failed error_type=%s fallback=local",
            type(exc).__name__,
        )
        return LocalHashEmbeddingProvider()
