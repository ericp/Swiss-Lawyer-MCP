"""Async client for the private FastAPI backend used by MCP."""

from __future__ import annotations

import uuid
from typing import Any

import httpx
from pydantic import ValidationError

from backend.api.schemas import (
    MemoryDeletionResponse,
    ProcedureDetailResponse,
    ProcedureListResponse,
    ProcedurePatchRequest,
    ProcedureQueryRequest,
    ProcedureQueryResponse,
)
from backend.mcp.errors import BackendTimeoutError, BackendUnavailableError, InvalidBackendResponseError, MCPError
from backend.mcp.schemas import ConsultSwissProcedureInput, GetMyProceduresInput, UpdateMyProcedureInput
from backend.mcp.settings import MCPSettings


class SwissLawyerBackendClient:
    """Call the existing FastAPI application without duplicating workflow logic."""

    def __init__(
        self,
        *,
        settings: MCPSettings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.backend_base_url,
            timeout=settings.backend_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def consult(
        self,
        *,
        external_user_key: str,
        payload: ConsultSwissProcedureInput,
        correlation_id: str | None = None,
    ) -> ProcedureQueryResponse:
        body = payload.model_dump(exclude_none=True)
        body["external_user_key"] = external_user_key
        response = await self._request(
            "POST",
            "/internal/mcp/procedures/query",
            json=body,
            correlation_id=correlation_id,
            retry_safe=False,
        )
        return _validate_response(ProcedureQueryResponse, response)

    async def get_procedures(
        self,
        *,
        external_user_key: str,
        payload: GetMyProceduresInput,
        correlation_id: str | None = None,
    ) -> ProcedureListResponse | ProcedureDetailResponse:
        params = payload.model_dump(exclude_none=True)
        procedure_id = params.pop("procedure_id", None)
        params["external_user_key"] = external_user_key
        path = f"/internal/mcp/procedures/{procedure_id}" if procedure_id else "/internal/mcp/procedures"
        response = await self._request(
            "GET",
            path,
            params=params,
            correlation_id=correlation_id,
            retry_safe=True,
        )
        model = ProcedureDetailResponse if procedure_id else ProcedureListResponse
        return _validate_response(model, response)

    async def update_procedure(
        self,
        *,
        external_user_key: str,
        payload: UpdateMyProcedureInput,
        correlation_id: str | None = None,
    ) -> ProcedureDetailResponse:
        body = payload.model_dump(exclude_none=True)
        procedure_id = body.pop("procedure_id")
        body["external_user_key"] = external_user_key
        response = await self._request(
            "PATCH",
            f"/internal/mcp/procedures/{procedure_id}",
            json=body,
            correlation_id=correlation_id,
            retry_safe=False,
        )
        return _validate_response(ProcedureDetailResponse, response)

    async def delete_memory(
        self,
        *,
        external_user_key: str,
        correlation_id: str | None = None,
    ) -> MemoryDeletionResponse:
        response = await self._request(
            "DELETE",
            "/internal/mcp/memory",
            params={"external_user_key": external_user_key},
            correlation_id=correlation_id,
            retry_safe=False,
        )
        return _validate_response(MemoryDeletionResponse, response)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        correlation_id: str | None,
        retry_safe: bool,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = kwargs.pop("headers", {})
        headers.update(self._headers(correlation_id))
        attempts = 2 if retry_safe else 1
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                response = await self._client.request(method, path, headers=headers, **kwargs)
                return _response_payload(response)
            except httpx.TimeoutException as error:
                last_error = error
                if not retry_safe:
                    break
            except httpx.HTTPError as error:
                last_error = error
                break
        if isinstance(last_error, httpx.TimeoutException):
            raise BackendTimeoutError() from last_error
        raise BackendUnavailableError() from last_error

    def _headers(self, correlation_id: str | None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._settings.internal_service_token}",
            "X-Correlation-ID": correlation_id or str(uuid.uuid4()),
        }


def _response_payload(response: httpx.Response) -> dict[str, Any]:
    if response.status_code in {401, 403}:
        raise MCPError("procedure_access_error", "The requested procedure is not available.", status_code=403)
    if response.status_code == 404:
        raise MCPError("procedure_not_found", "The requested procedure was not found.", status_code=404)
    if response.status_code >= 500:
        raise BackendUnavailableError()
    if response.status_code >= 400:
        raise MCPError("invalid_request", "The backend rejected the request.", status_code=400)
    payload = response.json()
    if not isinstance(payload, dict):
        raise InvalidBackendResponseError()
    return payload


def _validate_response(model: type, payload: dict[str, Any]) -> Any:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise InvalidBackendResponseError() from error
