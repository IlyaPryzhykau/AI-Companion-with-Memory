"""Chat endpoint tests."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.chat import Chat, Message


def _signup_and_login(client, email: str, password: str = "strongpass123") -> str:
    """Create a user and return access token."""

    client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
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
