"""Runtime settings for the local MCP adapter."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class MCPSettings:
    server_name: str = "Swiss Lawyer"
    server_version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8001
    path: str = "/mcp"
    auth_mode: str = "single_user"
    single_user_key: str = ""
    public_base_url: str = ""
    backend_base_url: str = "http://127.0.0.1:8000"
    internal_service_token: str = ""
    backend_timeout_seconds: float = 90.0
    environment: str = "development"
    log_level: str = "INFO"
    detailed_payload_logging: bool = False
    max_question_length: int = 10_000
    max_profile_fields: int = 50
    max_profile_value_length: int = 5_000
    max_progress_note_length: int = 5_000
    max_request_bytes: int = 256_000
    rate_limit_requests_per_minute: int = 30
    concurrency_limit: int = 8

    def validate_startup(self) -> None:
        if self.auth_mode != "single_user":
            raise ValueError("MCP_AUTH_MODE must be single_user")
        if not self.single_user_key.strip():
            raise ValueError("MCP_SINGLE_USER_KEY must not be empty")
        if not self.internal_service_token.strip():
            raise ValueError("INTERNAL_SERVICE_TOKEN must not be empty")
        parsed = urlparse(self.backend_base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("SWISS_LAWYER_API_BASE_URL must be a valid HTTP(S) URL")
        if not self.path.startswith("/"):
            raise ValueError("MCP_PATH must start with /")
        if not 1 <= self.port <= 65535:
            raise ValueError("MCP_PORT must be between 1 and 65535")
        if self.max_question_length < 1:
            raise ValueError("MCP_MAX_QUESTION_LENGTH must be positive")


def load_mcp_settings() -> MCPSettings:
    return MCPSettings(
        server_name=os.getenv("MCP_SERVER_NAME", "Swiss Lawyer"),
        server_version=os.getenv("MCP_SERVER_VERSION", "1.0.0"),
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8001")),
        path=os.getenv("MCP_PATH", "/mcp"),
        auth_mode=os.getenv("MCP_AUTH_MODE", "single_user"),
        single_user_key=os.getenv("MCP_SINGLE_USER_KEY", ""),
        public_base_url=os.getenv("MCP_PUBLIC_BASE_URL", ""),
        backend_base_url=os.getenv("SWISS_LAWYER_API_BASE_URL", "http://127.0.0.1:8000"),
        internal_service_token=os.getenv("INTERNAL_SERVICE_TOKEN", ""),
        backend_timeout_seconds=float(os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "90")),
        environment=os.getenv("ENVIRONMENT", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        detailed_payload_logging=_env_bool("MCP_DETAILED_PAYLOAD_LOGGING", False),
        max_question_length=int(os.getenv("MCP_MAX_QUESTION_LENGTH", "10000")),
        max_profile_fields=int(os.getenv("MCP_MAX_PROFILE_FIELDS", "50")),
        max_profile_value_length=int(os.getenv("MCP_MAX_PROFILE_VALUE_LENGTH", "5000")),
        max_progress_note_length=int(os.getenv("MCP_MAX_PROGRESS_NOTE_LENGTH", "5000")),
        max_request_bytes=int(os.getenv("MCP_MAX_REQUEST_BYTES", "256000")),
        rate_limit_requests_per_minute=int(os.getenv("MCP_RATE_LIMIT_REQUESTS_PER_MINUTE", "30")),
        concurrency_limit=int(os.getenv("MCP_CONCURRENCY_LIMIT", "8")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
