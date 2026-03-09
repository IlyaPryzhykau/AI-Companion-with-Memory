"""Authentication endpoint tests."""


def test_signup_creates_user(client) -> None:
    """Signup should create a user and return public payload."""

    response = client.post(
        "/api/v1/auth/signup",
        json={"email": "user@example.com", "password": "strongpass123"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "user@example.com"
    assert "id" in payload


def test_signup_duplicate_email_returns_409(client) -> None:
    """Duplicate signup should be rejected."""

    body = {"email": "dup@example.com", "password": "strongpass123"}
    first = client.post("/api/v1/auth/signup", json=body)
    second = client.post("/api/v1/auth/signup", json=body)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_returns_jwt_token(client) -> None:
    """Login should return an access token for valid credentials."""

    client.post(
        "/api/v1/auth/signup",
        json={"email": "login@example.com", "password": "strongpass123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "strongpass123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]


def test_login_invalid_password_returns_401(client) -> None:
    """Login should fail with invalid password."""

    client.post(
        "/api/v1/auth/signup",
        json={"email": "invalid@example.com", "password": "strongpass123"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid@example.com", "password": "wrongpass123"},
    )

    assert response.status_code == 401


def test_get_me_requires_auth_and_returns_user(client) -> None:
    """Protected endpoint should return current user with valid bearer token."""

    client.post(
        "/api/v1/auth/signup",
        json={"email": "me@example.com", "password": "strongpass123"},
    )
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "me@example.com", "password": "strongpass123"},
    )
    token = login_response.json()["access_token"]

    unauthorized = client.get("/api/v1/auth/me")
    authorized = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert authorized.json()["email"] == "me@example.com"
