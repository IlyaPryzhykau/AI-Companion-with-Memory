"""Observability metrics endpoints."""

from fastapi import APIRouter

from app.services.observability import get_metrics_snapshot

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Operational metrics snapshot")
def metrics_snapshot() -> dict[str, object]:
    """Return in-process operational metrics for dashboards/debugging."""

    return get_metrics_snapshot()
