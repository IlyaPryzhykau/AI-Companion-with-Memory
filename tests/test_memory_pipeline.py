"""Memory pipeline tests for chat endpoint."""

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import UserMemory, VectorMemory


def _signup_and_login(client, email: str, password: str = "strongpass123") -> str:
    """Create a user and return access token."""

    local, domain = email.split("@", maxsplit=1)
    unique_email = f"{local}+{uuid4().hex[:8]}@{domain}"

    signup_response = client.post(
        "/api/v1/auth/signup",
        json={"email": unique_email, "password": password},
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": unique_email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def test_chat_stores_structured_and_vector_memory(client, db_session: Session) -> None:
    """Chat message should create both structured and semantic memory records."""

    token = _signup_and_login(client, "memory@example.com")
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "My name is Alex and I live in Berlin."},
    )

    assert response.status_code == 200

    structured = db_session.execute(select(UserMemory)).scalars().all()
    semantic = db_session.execute(select(VectorMemory)).scalars().all()

    assert len(structured) >= 1
    assert any(item.key == "name" and "Alex" in item.value for item in structured)
    assert len(semantic) == 1
    assert semantic[0].text == "My name is Alex and I live in Berlin."
    assert semantic[0].embedding is not None
    assert semantic[0].embedding_vector is not None


def test_chat_uses_retrieved_memory_in_follow_up_reply(client) -> None:
    """Follow-up question should use stored name memory in assistant response."""

    token = _signup_and_login(client, "memory-followup@example.com")
    first = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "My name is Alex."},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What is my name?"},
    )

    assert second.status_code == 200
    assert "Alex" in second.json()["response"]


def test_chat_does_not_invent_name_when_none_is_stored(client) -> None:
    """Identity question should not claim a name when no structured name memory exists."""

    token = _signup_and_login(client, "memory-no-name@example.com")
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What is my name?"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Echo: What is my name?"


def test_chat_memory_context_influences_answer_generation(client, monkeypatch) -> None:
    """Chat flow should pass retrieved memory context into assistant generation."""

    token = _signup_and_login(client, "memory-influence@example.com")
    seed = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "I am preparing for a distributed systems interview."},
    )
    assert seed.status_code == 200

    def _fake_generate_assistant_reply(
        user_message: str,
        memory_context: str | None = None,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> str:
        if "focus" in user_message.lower():
            return f"Context seen: {memory_context or ''} history={len(chat_history or [])}"
        return f"Echo: {user_message}"

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.generate_assistant_reply",
        _fake_generate_assistant_reply,
    )

    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "What should I focus on for prep?"},
    )

    assert response.status_code == 200
    assert "distributed systems interview" in response.json()["response"].lower()
