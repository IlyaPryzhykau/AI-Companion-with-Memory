"""Health-check API endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Service health check")
def health_check() -> dict[str, str]:
    """Return a basic health status for monitoring and readiness checks."""

    return {"status": "ok"}
