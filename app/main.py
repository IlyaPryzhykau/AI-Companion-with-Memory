"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    app = FastAPI(
        title="AI Companion API",
        version="0.1.0",
        description="Backend API for AI Companion with Memory.",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = settings
    app.include_router(api_router)
    return app


app = create_app()
