"""Chat endpoint tests."""

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import Chat, Message


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


def test_chat_without_chat_id_creates_chat_and_two_messages(client, db_session: Session) -> None:
    """New chat request should create chat plus user/assistant messages."""

    token = _signup_and_login(client, "chat1@example.com")
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Hello there"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["chat_id"] > 0
    assert payload["response"] == "Echo: Hello there"

    chat_count = db_session.execute(select(func.count()).select_from(Chat)).scalar_one()
    message_count = db_session.execute(select(func.count()).select_from(Message)).scalar_one()
    assert chat_count == 1
    assert message_count == 2


def test_chat_with_foreign_chat_id_returns_404(client) -> None:
    """User should not access chat owned by another user."""

    token_user_1 = _signup_and_login(client, "chat-owner@example.com")
    token_user_2 = _signup_and_login(client, "chat-other@example.com")

    chat_response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token_user_1}"},
        json={"message": "Owner message"},
    )
    chat_id = chat_response.json()["chat_id"]

    forbidden_response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token_user_2}"},
        json={"chat_id": chat_id, "message": "Intruder message"},
    )

    assert forbidden_response.status_code == 404


def test_chat_passes_recent_history_to_generation(client, monkeypatch) -> None:
    """Follow-up turn should include chat history when generating assistant reply."""

    token = _signup_and_login(client, "chat-history@example.com")
    first = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "Привет"},
    )
    assert first.status_code == 200
    chat_id = first.json()["chat_id"]

    captured_history_size = {"value": 0}

    def _fake_generate_assistant_reply(
        user_message: str,
        memory_context: str | None = None,
        chat_history: list[tuple[str, str]] | None = None,
    ) -> str:
        captured_history_size["value"] = len(chat_history or [])
        return "ok"

    monkeypatch.setattr(
        "app.api.v1.endpoints.chat.generate_assistant_reply",
        _fake_generate_assistant_reply,
    )

    second = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"chat_id": chat_id, "message": "Дальше по теме"},
    )

    assert second.status_code == 200
    assert captured_history_size["value"] >= 3
