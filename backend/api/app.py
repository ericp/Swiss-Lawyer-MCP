"""FastAPI application for the Swiss Lawyer MCP backend."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI

from backend.api.error_handlers import register_exception_handlers
from backend.api.routes.internal_mcp import router as internal_mcp_router
from backend.api.routes.admin_synchronization import router as sync_admin_router
from backend.api.routes.health import router as health_router
from backend.api.routes.procedures import router as procedures_router
from backend.utils.config import load_api_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_api_settings()
    logging.basicConfig(level=settings.log_level.upper())
    logger = logging.getLogger(__name__)
    _validate_startup_configuration()
    logger.info("Starting Swiss Lawyer MCP API")
    yield
    logger.info("Stopping Swiss Lawyer MCP API")


def _validate_startup_configuration() -> None:
    if not os.getenv("INTERNAL_SERVICE_TOKEN", "").strip():
        raise RuntimeError("INTERNAL_SERVICE_TOKEN must be configured")
    sqlite_url = os.getenv("SQLITE_DATABASE_URL", "sqlite:///data/sqlite/memory.db")
    if sqlite_url.startswith("sqlite:///"):
        sqlite_parent = Path(sqlite_url.removeprefix("sqlite:///")).parent
        if not sqlite_parent.exists() or not os.access(sqlite_parent, os.W_OK):
            raise RuntimeError("SQLite storage directory is not writable")
    chroma_path = Path(os.getenv("CHROMA_PATH", "data/chromadb"))
    if not chroma_path.exists():
        raise RuntimeError("ChromaDB storage path is not available")


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
    app.include_router(internal_mcp_router)
    if load_api_settings().enable_sync_admin_endpoints:
        app.include_router(sync_admin_router)
    return app


app = create_app()
