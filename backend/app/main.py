"""FastAPI application factory."""

from fastapi import FastAPI

from app.api.routers import health
from app.common.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    configure_logging()

    app = FastAPI(
        title="Recommendator",
        description="Stock recommendation system for US and Finnish markets.",
        version="0.1.0",
    )

    app.include_router(health.router)

    return app


app = create_app()
