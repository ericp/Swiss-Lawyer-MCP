"""Safe error categories for MCP responses."""

from __future__ import annotations


class MCPError(Exception):
    """Base MCP-safe error."""

    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class BackendUnavailableError(MCPError):
    def __init__(self) -> None:
        super().__init__("backend_unavailable", "The Swiss Lawyer backend is unavailable.", status_code=503)


class BackendTimeoutError(MCPError):
    def __init__(self) -> None:
        super().__init__("backend_timeout", "The Swiss Lawyer backend timed out.", status_code=504)


class InvalidBackendResponseError(MCPError):
    def __init__(self) -> None:
        super().__init__("invalid_backend_response", "The backend returned an invalid response.", status_code=502)


class RateLimitExceededError(MCPError):
    def __init__(self) -> None:
        super().__init__("rate_limit_exceeded", "Too many local MCP requests. Please wait and try again.", status_code=429)
