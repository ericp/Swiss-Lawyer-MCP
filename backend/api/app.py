"""FastAPI application for the Swiss Lawyer MCP backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes.health import router as health_router
from backend.api.routes.procedures import router as procedures_router
from backend.utils.config import load_api_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_api_settings()
    logging.basicConfig(level=settings.log_level.upper())
    logger = logging.getLogger(__name__)
    logger.info("Starting Swiss Lawyer MCP API")
    yield
    logger.info("Stopping Swiss Lawyer MCP API")


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="Swiss Lawyer MCP API",
        version="0.8.0",
        description=(
            "Clarification-first Swiss procedure workflow API backed by "
            "retrieval, grounded generation, planning, and SQLite memory."
        ),
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(procedures_router)
    return app


app = create_app()
