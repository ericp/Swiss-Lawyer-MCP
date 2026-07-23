"""Identity abstraction for MCP requests."""

from __future__ import annotations

from typing import Protocol


class RequestIdentityProvider(Protocol):
    """Return the backend external user key for the current MCP call."""

    def get_external_user_key(self) -> str:
        """Return the external user key to pass to Phase 8."""
