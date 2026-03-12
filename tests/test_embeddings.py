"""Embedding provider tests."""

from types import SimpleNamespace

import pytest

from app.models.user import User
from app.services.embeddings import (
    LocalHashEmbeddingProvider,
    LocalHTTPEmbeddingProvider,
    OpenAIEmbeddingProvider,
    get_embedding_provider,
    resolve_embedding_provider_with_fallback,
)
from app.services.vector_store import JsonVectorStore


def test_local_hash_embedding_provider_is_deterministic() -> None:
    """Local provider should produce stable output for identical input."""

    provider = LocalHashEmbeddingProvider()
    first = provider.embed("prepare for interview", dimensions=64)
    second = provider.embed("prepare for interview", dimensions=64)
    assert first == second


def test_get_embedding_provider_falls_back_to_local_without_openai_key() -> None:
    """OpenAI provider config should degrade to local if API key is absent."""

    settings = SimpleNamespace(
        embedding_provider="openai",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
    )
    provider = get_embedding_provider(settings=settings)
    assert isinstance(provider, LocalHashEmbeddingProvider)


def test_get_embedding_provider_returns_local_http_provider() -> None:
    """Local HTTP provider config should resolve HTTP-compatible adapter."""

    settings = SimpleNamespace(
        embedding_provider="local_http",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_embedding_model="nomic-embed-text",
        local_llm_embedding_timeout_seconds=20.0,
    )
    provider = get_embedding_provider(settings=settings)
    assert isinstance(provider, LocalHTTPEmbeddingProvider)
    assert provider.timeout_seconds == 20.0


def test_get_embedding_provider_rejects_invalid_local_http_base_url() -> None:
    """Invalid local HTTP base URL should fail fast at provider resolution."""

    settings = SimpleNamespace(
        embedding_provider="local_http",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
        local_llm_base_url="localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_embedding_model="nomic-embed-text",
        local_llm_embedding_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="LOCAL_LLM_BASE_URL"):
        get_embedding_provider(settings=settings)


def test_get_embedding_provider_rejects_http_url_outside_development() -> None:
    """HTTP local embedding URL must be rejected in non-local environments."""

    settings = SimpleNamespace(
        app_env="production",
        embedding_provider="local_http",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
        local_llm_base_url="http://llm.internal/v1",
        local_llm_api_key="local-key",
        local_llm_embedding_model="nomic-embed-text",
        local_llm_embedding_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="Unsafe LOCAL_LLM_BASE_URL"):
        get_embedding_provider(settings=settings)


def test_get_embedding_provider_accepts_https_url_outside_development() -> None:
    """HTTPS local embedding URL should be accepted in non-local environments."""

    settings = SimpleNamespace(
        app_env="production",
        embedding_provider="local_http",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
        local_llm_base_url="https://llm.internal/v1",
        local_llm_api_key="local-key",
        local_llm_embedding_model="nomic-embed-text",
        local_llm_embedding_timeout_seconds=20.0,
    )

    provider = get_embedding_provider(settings=settings)
    assert isinstance(provider, LocalHTTPEmbeddingProvider)


def test_get_embedding_provider_rejects_empty_api_key_for_local_http() -> None:
    """local_http embedding provider should fail fast on empty API key."""

    settings = SimpleNamespace(
        app_env="development",
        embedding_provider="local_http",
        openai_api_key="",
        openai_embedding_model="text-embedding-3-small",
        openai_embedding_timeout_seconds=10.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="   ",
        local_llm_embedding_model="nomic-embed-text",
        local_llm_embedding_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="LOCAL_LLM_API_KEY"):
        get_embedding_provider(settings=settings)


def test_resolve_embedding_provider_with_invalid_local_http_url_falls_back(monkeypatch) -> None:
    """Resolver should return local fallback when local_http URL is invalid."""

    monkeypatch.setattr(
        "app.services.embeddings.get_settings",
        lambda: SimpleNamespace(
            embedding_provider="local_http",
            openai_api_key="",
            openai_embedding_model="text-embedding-3-small",
            openai_embedding_timeout_seconds=10.0,
            local_llm_base_url="localhost:11434/v1",
            local_llm_api_key="local-key",
            local_llm_embedding_model="nomic-embed-text",
            local_llm_embedding_timeout_seconds=20.0,
        ),
    )
    provider = resolve_embedding_provider_with_fallback()
    assert isinstance(provider, LocalHashEmbeddingProvider)


def test_openai_embedding_provider_uses_dimensions(monkeypatch) -> None:
    """OpenAI provider should pass requested embedding dimensions to client."""

    class _FakeEmbeddingsAPI:
        def __init__(self) -> None:
            self.last_dimensions = None

        def create(self, **kwargs):
            self.last_dimensions = kwargs["dimensions"]
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * kwargs["dimensions"])])

    fake_embeddings_api = _FakeEmbeddingsAPI()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = fake_embeddings_api

    monkeypatch.setattr("app.services.embeddings.OpenAI", _FakeOpenAI)

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    vector = provider.embed("hello", dimensions=64)

    assert len(vector) == 64
    assert fake_embeddings_api.last_dimensions == 64


def test_openai_embedding_provider_rejects_malformed_response(monkeypatch) -> None:
    """Provider should fail safely when API response misses embedding payload."""

    class _FakeEmbeddingsAPI:
        def create(self, **kwargs):
            return SimpleNamespace(data=[])

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = _FakeEmbeddingsAPI()

    monkeypatch.setattr("app.services.embeddings.OpenAI", _FakeOpenAI)

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    with pytest.raises(RuntimeError, match="embedding request failed"):
        provider.embed("hello", dimensions=64)


def test_openai_embedding_provider_rejects_dimension_mismatch(monkeypatch) -> None:
    """Provider should fail when API returns unexpected embedding dimensions."""

    class _FakeEmbeddingsAPI:
        def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 32)])

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.embeddings = _FakeEmbeddingsAPI()

    monkeypatch.setattr("app.services.embeddings.OpenAI", _FakeOpenAI)

    provider = OpenAIEmbeddingProvider(api_key="test-key", model="text-embedding-3-small")
    with pytest.raises(RuntimeError, match="embedding request failed"):
        provider.embed("hello", dimensions=64)


def test_resolve_embedding_provider_with_invalid_config_falls_back(monkeypatch) -> None:
    """Invalid provider config should return local fallback provider."""

    monkeypatch.setattr(
        "app.services.embeddings.get_settings",
        lambda: SimpleNamespace(
            embedding_provider="bad-provider",
            openai_api_key="",
            openai_embedding_model="text-embedding-3-small",
            openai_embedding_timeout_seconds=10.0,
        ),
    )
    provider = resolve_embedding_provider_with_fallback()
    assert isinstance(provider, LocalHashEmbeddingProvider)


def test_json_vector_store_falls_back_to_local_when_provider_fails(db_session) -> None:
    """Store/search should continue when primary embedding provider raises errors."""

    class _FailingProvider:
        name = "failing-test-provider"

        def embed(self, text: str, dimensions: int) -> list[float]:
            raise RuntimeError("simulated provider failure")

    user = User(email="embedding-fallback@example.com", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    store = JsonVectorStore(dimensions=64, embedding_provider=_FailingProvider())
    store.store(
        db=db_session,
        user_id=user.id,
        text_value="I am preparing for an interview loop.",
        importance=0.7,
    )
    db_session.commit()

    results = store.search(
        db=db_session,
        user_id=user.id,
        query="interview preparation",
        limit=1,
    )

    assert len(results) == 1
    assert "interview" in results[0].text.lower()
