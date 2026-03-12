"""Chat provider abstraction tests."""

from types import SimpleNamespace

import pytest

from app.services.chat_providers import (
    EchoChatProvider,
    LocalHTTPChatProvider,
    OpenAIChatProvider,
    get_chat_provider,
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
    )
    provider = get_chat_provider(settings=settings)
    assert isinstance(provider, LocalHTTPChatProvider)


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
