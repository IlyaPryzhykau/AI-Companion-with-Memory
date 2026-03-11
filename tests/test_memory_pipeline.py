"""Memory pipeline tests for chat endpoint."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory import UserMemory, VectorMemory


def _signup_and_login(client, email: str, password: str = "strongpass123") -> str:
    """Create a user and return access token."""

    client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
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
