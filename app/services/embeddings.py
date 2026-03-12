"""Embedding providers used by memory vector storage/search."""

import hashlib
import logging
import math
from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.vector_validation import validate_embedding_vector

logger = logging.getLogger(__name__)


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
            vector = [float(value) for value in response.data[0].embedding]
            return validate_embedding_vector(vector, expected_dimensions=dimensions)
        except Exception as exc:
            raise RuntimeError(
                f"OpenAI embedding request failed for model '{self.model}'."
            ) from exc


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Resolve embedding provider from settings with safe local fallback."""

    if settings is None:
        settings = get_settings()

    provider = settings.embedding_provider.lower().strip()
    if provider not in {"local", "openai"}:
        raise ValueError(
            f"Unsupported EMBEDDING_PROVIDER '{settings.embedding_provider}'. Use 'local' or 'openai'."
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

    return LocalHashEmbeddingProvider()


def resolve_embedding_provider_with_fallback() -> EmbeddingProvider:
    """Resolve provider with guard against settings validation failures."""

    try:
        return get_embedding_provider()
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "embedding_provider_resolution_failed error=%s fallback=local",
            f"{type(exc).__name__}: {exc}",
        )
        return LocalHashEmbeddingProvider()
