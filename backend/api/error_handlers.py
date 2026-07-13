"""Centralized API error handling."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.orchestration.procedure_orchestrator import (
    OrchestrationError,
    ProcedureNotFoundError,
    ProcedureOwnershipError,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register structured exception handlers without exposing internals."""

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _error_response(
            status_code=422,
            code="validation_error",
            message="The request payload is invalid.",
            details={"errors": exc.errors()},
        )

    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(
        request: Request,
        exc: UserNotFoundError,
    ) -> JSONResponse:
        return _error_response(404, "user_not_found", str(exc))

    @app.exception_handler(ProcedureNotFoundError)
    async def procedure_not_found_handler(
        request: Request,
        exc: ProcedureNotFoundError,
    ) -> JSONResponse:
        return _error_response(404, "procedure_not_found", str(exc))

    @app.exception_handler(ProcedureOwnershipError)
    async def ownership_error_handler(
        request: Request,
        exc: ProcedureOwnershipError,
    ) -> JSONResponse:
        return _error_response(403, "procedure_ownership_mismatch", str(exc))

    @app.exception_handler(OrchestrationError)
    async def orchestration_error_handler(
        request: Request,
        exc: OrchestrationError,
    ) -> JSONResponse:
        return _error_response(400, "orchestration_error", str(exc))

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        logger.exception("Database error while handling %s", request.url.path)
        return _error_response(
            503,
            "database_error",
            "The memory database is temporarily unavailable.",
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unexpected error while handling %s", request.url.path)
        return _error_response(
            500,
            "internal_error",
            "An unexpected internal error occurred.",
        )


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if details is not None:
        payload["error"]["details"] = details
    return JSONResponse(status_code=status_code, content=payload)
