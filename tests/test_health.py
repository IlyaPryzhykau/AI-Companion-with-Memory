"""Health endpoint tests."""


def test_health_check(client) -> None:
    """Health endpoint should return service status."""

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
