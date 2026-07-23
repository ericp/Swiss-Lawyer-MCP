"""Internal service-token authentication for MCP-to-FastAPI calls."""

from __future__ import annotations

import hmac
import os

from fastapi import Header, HTTPException


def require_internal_service_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    expected = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "configuration_error", "message": "Internal service token is not configured."}},
        )
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=403,
            detail={"error": {"code": "internal_auth_failed", "message": "Internal service authentication failed."}},
        )
