"""Operational metrics endpoint tests."""

from uuid import uuid4


def _signup_and_login(client, email: str, password: str = "strongpass123") -> str:
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


def test_metrics_endpoint_returns_expected_shape(client) -> None:
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert "memory_write_rate_total" in payload
    assert "retrieval" in payload
    assert "context_budget_usage" in payload
    assert "provider" in payload


def test_metrics_endpoint_reports_provider_and_memory_activity(client) -> None:
    token = _signup_and_login(client, "metrics@example.com")
    response = client.post(
        "/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "My name is Alex and I live in Berlin."},
    )
    assert response.status_code == 200

    metrics_response = client.get("/api/v1/metrics")
    assert metrics_response.status_code == 200
    payload = metrics_response.json()

    assert payload["memory_write_rate_total"]["upsert_facts"] >= 1
    assert payload["memory_write_rate_total"]["store_episodic"] >= 1
    assert payload["retrieval"]["requests_total"] >= 1
    assert payload["provider"]["chat:local"]["calls_total"] >= 1
    assert payload["provider"]["embedding:local"]["calls_total"] >= 1
