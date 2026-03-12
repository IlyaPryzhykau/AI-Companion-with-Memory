"""LLM service tests."""

from app.services.llm import generate_assistant_reply


def test_generate_assistant_reply_uses_resolved_provider(monkeypatch) -> None:
    """LLM service should use resolved chat provider output."""

    class _FakeProvider:
        name = "fake-provider"

        def generate(self, messages, user_message: str) -> str:
            return "Model-based response"

    monkeypatch.setattr(
        "app.services.llm.resolve_chat_provider_with_fallback",
        lambda: _FakeProvider(),
    )

    reply = generate_assistant_reply("Hello")

    assert reply == "Model-based response"


def test_generate_assistant_reply_falls_back_to_echo_on_provider_error(monkeypatch) -> None:
    """Provider runtime errors should not break response generation."""

    class _FailingProvider:
        name = "failing-provider"

        def generate(self, messages, user_message: str) -> str:
            raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(
        "app.services.llm.resolve_chat_provider_with_fallback",
        lambda: _FailingProvider(),
    )

    reply = generate_assistant_reply("Hello")

    assert reply == "Echo: Hello"
