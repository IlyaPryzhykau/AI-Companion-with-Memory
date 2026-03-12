"""Chat provider abstraction tests."""

from types import SimpleNamespace

import pytest

from app.services.chat_providers import (
    EchoChatProvider,
    LocalHTTPChatProvider,
    OpenAIChatProvider,
    get_chat_provider,
    resolve_chat_provider_with_fallback,
)


def test_get_chat_provider_falls_back_to_local_without_openai_key() -> None:
    """OpenAI provider config should degrade to local if API key is absent."""

    settings = SimpleNamespace(
        primary_llm_provider="openai",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
    )
    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, EchoChatProvider)


def test_get_chat_provider_returns_local_http_provider() -> None:
    """PRIMARY_LLM_PROVIDER=local_http should resolve local HTTP adapter."""

    settings = SimpleNamespace(
        primary_llm_provider="local_http",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
        local_llm_chat_timeout_seconds=20.0,
    )
    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, LocalHTTPChatProvider)
    assert provider.timeout_seconds == 20.0


def test_get_chat_provider_rejects_invalid_local_http_base_url() -> None:
    """Invalid local HTTP base URL should fail fast at provider resolution."""

    settings = SimpleNamespace(
        primary_llm_provider="local_http",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
        local_llm_chat_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="LOCAL_LLM_BASE_URL"):
        get_chat_provider(settings=settings)


def test_get_chat_provider_rejects_http_url_outside_development() -> None:
    """HTTP local LLM URL must be rejected in non-local environments."""

    settings = SimpleNamespace(
        app_env="production",
        primary_llm_provider="local_http",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://llm.internal/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
        local_llm_chat_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="Unsafe LOCAL_LLM_BASE_URL"):
        get_chat_provider(settings=settings)


def test_get_chat_provider_accepts_https_url_outside_development() -> None:
    """HTTPS local LLM URL should be accepted in non-local environments."""

    settings = SimpleNamespace(
        app_env="production",
        primary_llm_provider="local_http",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="https://llm.internal/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
        local_llm_chat_timeout_seconds=20.0,
    )

    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, LocalHTTPChatProvider)


def test_get_chat_provider_rejects_empty_api_key_for_local_http() -> None:
    """local_http provider should fail fast on empty LOCAL_LLM_API_KEY."""

    settings = SimpleNamespace(
        app_env="development",
        primary_llm_provider="local_http",
        openai_api_key="",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="   ",
        local_llm_chat_model="llama3.1:8b",
        local_llm_chat_timeout_seconds=20.0,
    )

    with pytest.raises(ValueError, match="LOCAL_LLM_API_KEY"):
        get_chat_provider(settings=settings)


def test_resolve_chat_provider_with_invalid_local_http_url_falls_back(monkeypatch) -> None:
    """Resolver should return local fallback when local_http URL is invalid."""

    monkeypatch.setattr(
        "app.services.chat_providers.get_settings",
        lambda: SimpleNamespace(
            primary_llm_provider="local_http",
            assistant_provider="local",
            model_fields_set={"primary_llm_provider"},
            openai_api_key="",
            openai_chat_model="gpt-4o-mini",
            openai_chat_timeout_seconds=15.0,
            local_llm_base_url="localhost:11434/v1",
            local_llm_api_key="local-key",
            local_llm_chat_model="llama3.1:8b",
            local_llm_chat_timeout_seconds=20.0,
        ),
    )
    provider = resolve_chat_provider_with_fallback()
    assert isinstance(provider, EchoChatProvider)


def test_get_chat_provider_uses_legacy_assistant_provider_when_primary_not_set() -> None:
    """Legacy ASSISTANT_PROVIDER=openai should work when primary provider is unset."""

    settings = SimpleNamespace(
        primary_llm_provider="local",
        model_fields_set={"assistant_provider"},
        assistant_provider="openai",
        openai_api_key="test-key",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
    )

    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, OpenAIChatProvider)


def test_get_chat_provider_keeps_explicit_primary_provider() -> None:
    """Explicit PRIMARY_LLM_PROVIDER should override legacy ASSISTANT_PROVIDER."""

    settings = SimpleNamespace(
        primary_llm_provider="local",
        model_fields_set={"primary_llm_provider", "assistant_provider"},
        assistant_provider="openai",
        openai_api_key="test-key",
        openai_chat_model="gpt-4o-mini",
        openai_chat_timeout_seconds=15.0,
        local_llm_base_url="http://localhost:11434/v1",
        local_llm_api_key="local-key",
        local_llm_chat_model="llama3.1:8b",
    )

    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, EchoChatProvider)


def test_openai_chat_provider_uses_model(monkeypatch) -> None:
    """OpenAI provider should pass configured model to client call."""

    class _FakeCompletions:
        def __init__(self) -> None:
            self.last_model = ""

        def create(self, **kwargs):
            self.last_model = kwargs["model"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )

    fake_completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = SimpleNamespace(completions=fake_completions)

    monkeypatch.setattr("app.services.chat_providers.OpenAI", _FakeOpenAI)

    provider = OpenAIChatProvider(api_key="test-key", model="gpt-4o-mini")
    result = provider.generate(messages=[{"role": "user", "content": "hello"}], user_message="hello")

    assert result == "ok"
    assert fake_completions.last_model == "gpt-4o-mini"


def test_local_http_chat_provider_maps_failures_to_runtime_error(monkeypatch) -> None:
    """Local HTTP provider should raise RuntimeError on API failures."""

    class _FailingCompletions:
        def create(self, **kwargs):
            raise ValueError("simulated malformed response")

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = SimpleNamespace(completions=_FailingCompletions())

    monkeypatch.setattr("app.services.chat_providers.OpenAI", _FakeOpenAI)

    provider = LocalHTTPChatProvider(
        base_url="http://localhost:11434/v1",
        api_key="local-key",
        model="llama3.1:8b",
    )
    with pytest.raises(RuntimeError, match="Local HTTP chat request failed"):
        provider.generate(messages=[{"role": "user", "content": "hello"}], user_message="hello")


def test_openai_chat_provider_maps_client_init_failures_to_runtime_error(monkeypatch) -> None:
    """OpenAI provider should map client initialization failure to RuntimeError."""

    class _BrokenOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            raise ValueError("bad client init")

    monkeypatch.setattr("app.services.chat_providers.OpenAI", _BrokenOpenAI)

    provider = OpenAIChatProvider(api_key="test-key", model="gpt-4o-mini")
    with pytest.raises(RuntimeError, match="OpenAI chat request failed"):
        provider.generate(messages=[{"role": "user", "content": "hello"}], user_message="hello")


def test_local_http_chat_provider_maps_client_init_failures_to_runtime_error(monkeypatch) -> None:
    """Local HTTP provider should map client initialization failure to RuntimeError."""

    class _BrokenOpenAI:
        def __init__(self, *args, **kwargs) -> None:
            raise ValueError("bad client init")

    monkeypatch.setattr("app.services.chat_providers.OpenAI", _BrokenOpenAI)

    provider = LocalHTTPChatProvider(
        base_url="http://localhost:11434/v1",
        api_key="local-key",
        model="llama3.1:8b",
    )
    with pytest.raises(RuntimeError, match="Local HTTP chat request failed"):
        provider.generate(messages=[{"role": "user", "content": "hello"}], user_message="hello")
