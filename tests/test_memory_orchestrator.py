"""Rules-mode memory orchestrator tests."""

from app.services.memory_orchestrator import MemoryOrchestrator


def test_orchestrator_emits_structured_and_episodic_actions_in_english() -> None:
    """English personal fact message should produce structured + episodic actions."""

    orchestrator = MemoryOrchestrator()
    actions = orchestrator.plan("My name is Alex and I live in Berlin.")

    action_types = [action.action_type for action in actions]
    assert action_types == ["UPSERT_FACTS", "STORE_EPISODIC"]
    assert actions[0].reason == "structured_facts_detected"
    assert actions[1].payload["importance"] >= 0.55


def test_orchestrator_emits_structured_and_episodic_actions_in_russian() -> None:
    """Russian personal fact message should produce structured + episodic actions."""

    orchestrator = MemoryOrchestrator()
    actions = orchestrator.plan("Меня зовут Илья, моя цель - улучшить английский.")

    action_types = [action.action_type for action in actions]
    assert action_types == ["UPSERT_FACTS", "STORE_EPISODIC"]
    assert actions[0].payload["facts"][0]["key"] == "name"


def test_orchestrator_skips_irrelevant_message() -> None:
    """Irrelevant short acknowledgement should produce SKIP action."""

    orchestrator = MemoryOrchestrator()
    actions = orchestrator.plan("Ок, спасибо")

    assert len(actions) == 1
    assert actions[0].action_type == "SKIP"
    assert actions[0].reason == "no_memory_signal"


def test_orchestrator_is_deterministic_for_identical_input() -> None:
    """Rules-mode output must be deterministic for same message."""

    orchestrator = MemoryOrchestrator()
    first = orchestrator.plan("I am preparing for a distributed systems interview.")
    second = orchestrator.plan("I am preparing for a distributed systems interview.")

    assert first == second
