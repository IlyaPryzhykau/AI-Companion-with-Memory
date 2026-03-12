"""LLM service tests."""

from types import SimpleNamespace

from openai import OpenAIError

from app.services.llm import generate_assistant_reply


def test_generate_assistant_reply_uses_configured_openai_model(monkeypatch) -> None:
    """Configured OpenAI chat model should be used for assistant calls."""

    class _FakeCompletions:
        def __init__(self) -> None:
            self.last_model = ""

        def create(self, **kwargs):
            self.last_model = kwargs["model"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="Model-based response"))]
            )

    fake_completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = SimpleNamespace(completions=fake_completions)

    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(
            assistant_provider="openai",
            openai_api_key="test-key",
            openai_chat_model="gpt-4.1-mini",
            openai_chat_timeout_seconds=15.0,
        ),
    )
    monkeypatch.setattr("app.services.llm.OpenAI", _FakeClient)

    reply = generate_assistant_reply("Hello")

    assert reply == "Model-based response"
    assert fake_completions.last_model == "gpt-4.1-mini"


def test_generate_assistant_reply_falls_back_to_echo_on_openai_error(monkeypatch) -> None:
    """OpenAI call errors should not break response generation."""

    class _FailingCompletions:
        def create(self, **kwargs):
            raise OpenAIError("simulated openai failure")

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self.chat = SimpleNamespace(completions=_FailingCompletions())

    monkeypatch.setattr(
        "app.services.llm.get_settings",
        lambda: SimpleNamespace(
            assistant_provider="openai",
            openai_api_key="test-key",
            openai_chat_model="gpt-4.1-mini",
            openai_chat_timeout_seconds=15.0,
        ),
    )
    monkeypatch.setattr("app.services.llm.OpenAI", _FakeClient)

    reply = generate_assistant_reply("Hello")

    assert reply == "Echo: Hello"
