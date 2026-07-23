"""Local single-user MCP Streamable HTTP server."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.mcp.backend_client import SwissLawyerBackendClient
from backend.mcp.context import MCPToolContext
from backend.mcp.errors import MCPError
from backend.mcp.identity.single_user import SingleUserIdentityProvider, identity_hash_prefix
from backend.mcp.rate_limit import InMemoryRateLimiter
from backend.mcp.schemas import (
    ConsultSwissProcedureInput,
    DeleteMySwissLawyerDataInput,
    GetMyProceduresInput,
    MCPToolResult,
    UpdateMyProcedureInput,
)
from backend.mcp.settings import MCPSettings, load_mcp_settings
from backend.mcp.tools.consult import consult_swiss_procedure
from backend.mcp.tools.privacy import delete_my_swiss_lawyer_data
from backend.mcp.tools.procedures import get_my_procedures
from backend.mcp.tools.progress import update_my_procedure

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except Exception:  # pragma: no cover - depends on optional package installation
    FastMCP = None  # type: ignore


logger = logging.getLogger(__name__)

CONSULT_TOOL = "consult_swiss_procedure"
PROCEDURES_TOOL = "get_my_procedures"
PROGRESS_TOOL = "update_my_procedure"
DELETE_TOOL = "delete_my_swiss_lawyer_data"
TOOL_NAMES = [CONSULT_TOOL, PROCEDURES_TOOL, PROGRESS_TOOL, DELETE_TOOL]

SERVER_INSTRUCTIONS = (
    "Use consult_swiss_procedure for new Swiss administrative questions, clarification answers and follow-ups. "
    "When clarification is required, present the questions to the user before calling it again. Use get_my_procedures "
    "to review or resume saved procedures. Update progress or delete data only after an explicit user request. "
    "This deployment uses one fixed local user identity managed by the server."
)


def create_app(
    *,
    settings: MCPSettings | None = None,
    backend_client: SwissLawyerBackendClient | None = None,
    identity_provider: SingleUserIdentityProvider | None = None,
    rate_limiter: InMemoryRateLimiter | None = None,
) -> FastAPI:
    """Create the local MCP HTTP app."""

    settings = settings or load_mcp_settings()
    settings.validate_startup()
    logging.basicConfig(level=settings.log_level.upper())
    backend = backend_client or SwissLawyerBackendClient(settings=settings)
    identity = identity_provider or SingleUserIdentityProvider(settings.single_user_key)
    limiter = rate_limiter or InMemoryRateLimiter()
    semaphore = asyncio.Semaphore(settings.concurrency_limit)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Starting MCP server user_hash=%s", identity.safe_hash_prefix())
        yield
        await backend.aclose()
        logger.info("Stopping MCP server")

    app = FastAPI(title=f"{settings.server_name} MCP", version=settings.server_version, lifespan=lifespan)
    app.state.mcp_settings = settings
    app.state.backend_client = backend
    app.state.identity_provider = identity
    app.state.rate_limiter = limiter
    app.state.semaphore = semaphore
    app.state.fastmcp_available = FastMCP is not None

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"status": "ok", "mcp_sdk_available": FastMCP is not None}

    @app.post(settings.path)
    async def mcp_endpoint(request: Request) -> JSONResponse:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_bytes:
            return _jsonrpc_error(None, "invalid_request", "Request body is too large.", status_code=413)
        try:
            payload = await request.json()
        except Exception:
            return _jsonrpc_error(None, "invalid_request", "Request body must be valid JSON.", status_code=400)
        request_id = payload.get("id")
        method = payload.get("method")
        if method == "initialize":
            return _jsonrpc_result(request_id, _initialize_result(settings))
        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": _tool_definitions()})
        if method == "tools/call":
            return await _handle_tool_call(request, payload, request_id)
        return _jsonrpc_error(request_id, "invalid_request", "Unsupported MCP method.", status_code=400)

    return app


async def _handle_tool_call(request: Request, payload: dict[str, Any], request_id: Any) -> JSONResponse:
    settings: MCPSettings = request.app.state.mcp_settings
    identity: SingleUserIdentityProvider = request.app.state.identity_provider
    limiter: InMemoryRateLimiter = request.app.state.rate_limiter
    semaphore: asyncio.Semaphore = request.app.state.semaphore
    params = payload.get("params", {})
    tool_name = params.get("name")
    if tool_name not in TOOL_NAMES:
        return _jsonrpc_error(request_id, "invalid_request", "Unknown tool.", status_code=400)
    correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
    started = time.perf_counter()
    result_status = "failed"
    try:
        limiter.check(key=identity.get_external_user_key(), limit=settings.rate_limit_requests_per_minute)
        async with semaphore:
            result = await _call_tool(
                tool_name=tool_name,
                arguments=params.get("arguments") or {},
                context=MCPToolContext(
                    identity_provider=identity,
                    backend_client=request.app.state.backend_client,
                    correlation_id=correlation_id,
                ),
            )
        result_status = result.state or result.message or "completed"
        return _jsonrpc_result(request_id, _tool_result_payload(result))
    except ValidationError as error:
        return _jsonrpc_error(
            request_id,
            "invalid_request",
            "Tool arguments are invalid.",
            details=jsonable_encoder(error.errors()),
            status_code=400,
        )
    except MCPError as error:
        result_status = error.code
        return _jsonrpc_error(request_id, error.code, error.message, status_code=error.status_code)
    except Exception:
        result_status = "internal_error"
        logger.exception("Unexpected MCP tool failure correlation_id=%s tool=%s", correlation_id, tool_name)
        return _jsonrpc_error(request_id, "internal_error", "An internal MCP error occurred.", status_code=500)
    finally:
        logger.info(
            "mcp_tool_call correlation_id=%s tool=%s result=%s user_hash=%s latency_ms=%.2f",
            correlation_id,
            tool_name,
            result_status,
            identity_hash_prefix(identity.get_external_user_key()),
            (time.perf_counter() - started) * 1000,
        )


async def _call_tool(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    context: MCPToolContext,
) -> MCPToolResult:
    if tool_name == CONSULT_TOOL:
        return await consult_swiss_procedure(
            context=context,
            payload=ConsultSwissProcedureInput.model_validate(arguments),
        )
    if tool_name == PROCEDURES_TOOL:
        return await get_my_procedures(
            context=context,
            payload=GetMyProceduresInput.model_validate(arguments),
        )
    if tool_name == PROGRESS_TOOL:
        return await update_my_procedure(
            context=context,
            payload=UpdateMyProcedureInput.model_validate(arguments),
        )
    if tool_name == DELETE_TOOL:
        return await delete_my_swiss_lawyer_data(
            context=context,
            payload=DeleteMySwissLawyerDataInput.model_validate(arguments),
        )
    raise MCPError("invalid_request", "Unknown tool.")


def _initialize_result(settings: MCPSettings) -> dict[str, Any]:
    return {
        "protocolVersion": "2025-06-18",
        "serverInfo": {"name": settings.server_name, "version": settings.server_version},
        "instructions": SERVER_INSTRUCTIONS[:512],
        "capabilities": {"tools": {"listChanged": False}},
    }


def _tool_definitions() -> list[dict[str, Any]]:
    return [
        _tool_definition(
            CONSULT_TOOL,
            "Use this when the user asks for guidance about a Swiss administrative procedure, answers clarification questions, or wants to continue an existing procedure. It may return clarification questions, a grounded answer, or an actionable procedure plan.",
            ConsultSwissProcedureInput,
            {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
        ),
        _tool_definition(
            PROCEDURES_TOOL,
            "Use this when the user asks to see, review, resume, or check the status of their saved Swiss procedures.",
            GetMyProceduresInput,
            {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
        ),
        _tool_definition(
            PROGRESS_TOOL,
            "Use this only when the user explicitly wants to mark progress, change the current step, add a progress note, or update the status of a saved procedure.",
            UpdateMyProcedureInput,
            {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
        ),
        _tool_definition(
            DELETE_TOOL,
            "Use this only when the user explicitly asks to permanently delete all locally stored Swiss Lawyer profile facts, saved procedures and interaction summaries.",
            DeleteMySwissLawyerDataInput,
            {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": True, "openWorldHint": False},
        ),
    ]


def _tool_definition(name: str, description: str, model: type[BaseException] | type[Any], annotations: dict[str, bool]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": model.model_json_schema(),
        "outputSchema": MCPToolResult.model_json_schema(),
        "annotations": annotations,
    }


def _tool_result_payload(result: MCPToolResult) -> dict[str, Any]:
    structured = result.model_dump(exclude_none=True)
    return {
        "content": [{"type": "text", "text": structured.get("message") or structured.get("state") or "Tool completed."}],
        "structuredContent": structured,
    }


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _jsonrpc_error(
    request_id: Any,
    code: str,
    message: str,
    *,
    details: Any | None = None,
    status_code: int,
) -> JSONResponse:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "error": error}, status_code=status_code)


def main() -> None:
    settings = load_mcp_settings()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
