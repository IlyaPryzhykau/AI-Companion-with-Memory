"""Memory policy layer tests."""

from types import SimpleNamespace

from app.services.memory_actions import MemoryAction
from app.services.memory_policy import apply_memory_policy


class _FakeProvider:
    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, messages: list[dict[str, str]], user_message: str) -> str:
        return self.response


def _base_settings(mode: str = "rules", threshold: float = 0.7):
    return SimpleNamespace(
        memory_policy_mode=mode,
        memory_policy_min_confidence=threshold,
    )


def _actions() -> list[MemoryAction]:
    return [
        MemoryAction(
            action_type="STORE_EPISODIC",
            reason="episodic_signal_detected",
            payload={"text": "I am preparing interview", "importance": 0.55},
        )
    ]


def test_policy_mode_rules_returns_actions_unchanged() -> None:
    actions = _actions()
    result = apply_memory_policy(
        user_message="I am preparing interview",
        actions=actions,
        settings=_base_settings(mode="rules"),
    )
    assert result == actions


def test_policy_mode_llm_denies_when_confident() -> None:
    actions = _actions()
    result = apply_memory_policy(
        user_message="I am preparing interview",
        actions=actions,
        settings=_base_settings(mode="llm", threshold=0.7),
        provider=_FakeProvider('{"decision":"deny","confidence":0.91,"reason":"not_needed"}'),
    )
    assert len(result) == 1
    assert result[0].action_type == "SKIP"
    assert result[0].reason.startswith("policy_denied:")


def test_policy_mode_llm_falls_back_on_low_confidence() -> None:
    actions = _actions()
    result = apply_memory_policy(
        user_message="I am preparing interview",
        actions=actions,
        settings=_base_settings(mode="llm", threshold=0.8),
        provider=_FakeProvider('{"decision":"deny","confidence":0.40,"reason":"unsure"}'),
    )
    assert result == actions


def test_policy_mode_llm_falls_back_on_invalid_response() -> None:
    actions = _actions()
    result = apply_memory_policy(
        user_message="I am preparing interview",
        actions=actions,
        settings=_base_settings(mode="llm"),
        provider=_FakeProvider("not-json-response"),
    )
    assert result == actions


def test_sensitive_guardrail_skips_even_without_llm_policy() -> None:
    actions = _actions()
    result = apply_memory_policy(
        user_message="My password is 123456 and API key is sk-test1234567890123456",
        actions=actions,
        settings=_base_settings(mode="rules"),
    )
    assert len(result) == 1
    assert result[0].action_type == "SKIP"
    assert result[0].reason == "sensitive_data_guardrail"
