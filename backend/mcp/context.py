"""Shared context for MCP tool handlers."""

from __future__ import annotations

from dataclasses import dataclass

from backend.mcp.backend_client import SwissLawyerBackendClient
from backend.mcp.identity.base import RequestIdentityProvider


@dataclass(frozen=True)
class MCPToolContext:
    identity_provider: RequestIdentityProvider
    backend_client: SwissLawyerBackendClient
    correlation_id: str
