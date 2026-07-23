"""Phase 11 local single-user MCP tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

from backend.api import dependencies
from backend.api.app import create_app as create_api_app
from backend.mcp.backend_client import SwissLawyerBackendClient
from backend.mcp.errors import BackendTimeoutError, BackendUnavailableError, InvalidBackendResponseError
from backend.mcp.identity.single_user import SingleUserIdentityProvider
from backend.mcp.schemas import ConsultSwissProcedureInput, MCPToolResult
from backend.mcp.server import SERVER_INSTRUCTIONS, create_app
from backend.mcp.settings import MCPSettings
from backend.models.generation import CitedSource
from backend.models.planner import ProcedurePlan, ProcedureStep, WorkflowStatus


def _settings(**updates: Any) -> MCPSettings:
    payload = {
        "single_user_key": "swiss-lawyer-local-user",
        "internal_service_token": "internal-token",
        **updates,
    }
    return MCPSettings(**payload)


def _call_tool(client: TestClient, name: str, arguments: dict[str, Any]) -> httpx.Response:
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
    )


def _plan() -> dict[str, Any]:
    source = CitedSource(source="official.pdf", page=1, region="ZH")
    return ProcedurePlan(
        title="Move to Zurich",
        summary="A procedure summary.",
        status=WorkflowStatus.IN_PROGRESS,
        steps=[
            ProcedureStep(
                step_number=1,
                title="Confirm details",
                description="Confirm the required details.",
                responsible_party="User",
                required_documents=[],
                estimated_time="Not specified in retrieved sources.",
                source_reference=source,
            )
        ],
        required_documents=[],
        estimated_timelines=["Not specified in retrieved sources."],
        potential_blockers=[],
        next_recommended_action="Answer clarification questions.",
        source_references=[source],
        missing_information=[],
    ).model_dump()


class FakeBackendClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    async def consult(self, *, external_user_key: str, payload: Any, correlation_id: str | None = None) -> Any:
        self.calls.append(("consult", external_user_key, payload))
        if "clarify" in payload.question:
            return type(
                "Response",
                (),
                {
                    "state": type("State", (), {"value": "clarification_required"})(),
                    "procedure_id": "p1",
                    "intent": "immigration",
                    "needs_clarification": True,
                    "clarification_questions": [type("Question", (), {"model_dump": lambda self: {"field": "purpose_of_stay", "question": "What is your purpose of stay?"}})()],
                    "missing_fields": ["purpose_of_stay"],
                    "answer": None,
                    "plan": None,
                    "sources": [],
                    "confidence": None,
                    "insufficient_context": False,
                    "saved_profile_fields": [],
                    "workflow_status": None,
                    "disclaimer": "info only",
                },
            )()
        return type(
            "Response",
            (),
            {
                "state": type("State", (), {"value": "answered"})(),
                "procedure_id": "p1",
                "intent": "immigration",
                "needs_clarification": False,
                "clarification_questions": [],
                "missing_fields": [],
                "answer": type("Answer", (), {"model_dump": lambda self: {"answer": "Grounded answer."}})(),
                "plan": type("Plan", (), {"model_dump": lambda self: _plan()})(),
                "sources": [],
                "confidence": "Medium",
                "insufficient_context": False,
                "saved_profile_fields": ["nationality"],
                "workflow_status": WorkflowStatus.IN_PROGRESS,
                "disclaimer": "info only",
            },
        )()

    async def get_procedures(self, *, external_user_key: str, payload: Any, correlation_id: str | None = None) -> Any:
        self.calls.append(("get", external_user_key, payload))
        detail = type(
            "Detail",
            (),
            {
                "procedure_id": payload.procedure_id or "p1",
                "intent": "immigration",
                "title": "Move to Zurich",
                "status": WorkflowStatus.IN_PROGRESS,
                "summary": "A summary.",
                "plan": type("Plan", (), {"model_dump": lambda self: _plan()})(),
                "current_step": 1,
                "recent_interaction_summaries": ["Created procedure plan."],
            },
        )()
        if payload.procedure_id:
            return detail
        return type("ListResponse", (), {"procedures": [detail]})()

    async def update_procedure(self, *, external_user_key: str, payload: Any, correlation_id: str | None = None) -> Any:
        self.calls.append(("update", external_user_key, payload))
        return type(
            "Detail",
            (),
            {
                "procedure_id": payload.procedure_id,
                "intent": "immigration",
                "status": payload.status or WorkflowStatus.IN_PROGRESS,
                "plan": type("Plan", (), {"model_dump": lambda self: _plan()})(),
                "current_step": payload.current_step,
                "recent_interaction_summaries": ["Progress updated."],
            },
        )()

    async def delete_memory(self, *, external_user_key: str, correlation_id: str | None = None) -> Any:
        self.calls.append(("delete", external_user_key, None))
        return type("DeleteResponse", (), {"deleted": True})()

    async def aclose(self) -> None:
        return None


def test_mcp_initializes_and_lists_four_tools() -> None:
    client = TestClient(create_app(settings=_settings(), backend_client=FakeBackendClient()))  # type: ignore[arg-type]
    initialized = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    listed = client.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})

    assert initialized.status_code == 200
    assert SERVER_INSTRUCTIONS[:120] in initialized.json()["result"]["instructions"]
    tools = listed.json()["result"]["tools"]
    assert [tool["name"] for tool in tools] == [
        "consult_swiss_procedure",
        "get_my_procedures",
        "update_my_procedure",
        "delete_my_swiss_lawyer_data",
    ]
    serialized = json.dumps(tools)
    assert "user_id" not in serialized
    assert "external_user_key" not in serialized
    assert next(tool for tool in tools if tool["name"] == "delete_my_swiss_lawyer_data")["annotations"]["destructiveHint"] is True


def test_identity_provider_and_startup_validation() -> None:
    provider = SingleUserIdentityProvider("local-user")
    assert provider.get_external_user_key() == "local-user"
    assert provider.safe_hash_prefix() == hashlib.sha256(b"local-user").hexdigest()[:12]
    _settings().validate_startup()
    with pytest.raises(ValueError):
        _settings(single_user_key="").validate_startup()
    with pytest.raises(ValueError):
        _settings(auth_mode="oauth").validate_startup()


def test_tool_validation_and_no_identity_arguments() -> None:
    with pytest.raises(Exception):
        ConsultSwissProcedureInput.model_validate({"question": "Can I move?", "user_id": "u1"})
    with pytest.raises(Exception):
        ConsultSwissProcedureInput.model_validate({"question": ""})
    with pytest.raises(Exception):
        ConsultSwissProcedureInput.model_validate({"question": "x" * 10_001})


def test_consult_clarification_answer_and_fixed_identity_not_returned_or_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.mcp import server as mcp_server

    logged: list[tuple[Any, ...]] = []
    monkeypatch.setattr(mcp_server.logger, "info", lambda *args, **kwargs: logged.append(args))
    backend = FakeBackendClient()
    client = TestClient(create_app(settings=_settings(single_user_key="private-user-key"), backend_client=backend))  # type: ignore[arg-type]

    clarification = _call_tool(client, "consult_swiss_procedure", {"question": "clarify my move"})
    answer = _call_tool(
        client,
        "consult_swiss_procedure",
        {"question": "Can I move?", "procedure_id": "p1", "profile_updates": {"nationality": "Brazil"}, "confirmed_profile_fields": ["nationality"]},
    )

    assert clarification.json()["result"]["structuredContent"]["needs_clarification"] is True
    assert answer.json()["result"]["structuredContent"]["state"] == "answered"
    assert backend.calls[0][1] == "private-user-key"
    assert "private-user-key" not in json.dumps(answer.json())
    assert "private-user-key" not in json.dumps(logged)
    assert hashlib.sha256(b"private-user-key").hexdigest()[:12] in json.dumps(logged)


def test_procedure_list_detail_update_and_delete_tools() -> None:
    backend = FakeBackendClient()
    client = TestClient(create_app(settings=_settings(), backend_client=backend))  # type: ignore[arg-type]

    listed = _call_tool(client, "get_my_procedures", {"active_only": True, "limit": 5})
    detail = _call_tool(client, "get_my_procedures", {"procedure_id": "p1"})
    updated = _call_tool(client, "update_my_procedure", {"procedure_id": "p1", "status": "in_progress", "current_step": 1, "progress_note": "Started."})
    deleted = _call_tool(client, "delete_my_swiss_lawyer_data", {"confirmation": True})
    invalid_delete = _call_tool(client, "delete_my_swiss_lawyer_data", {"confirmation": False})
    invalid_update = _call_tool(client, "update_my_procedure", {"procedure_id": "p1", "plan": {"title": "nope"}})

    assert listed.json()["result"]["structuredContent"]["procedures"][0]["procedure_id"] == "p1"
    assert detail.json()["result"]["structuredContent"]["procedure_id"] == "p1"
    assert updated.json()["result"]["structuredContent"]["workflow_status"] == "in_progress"
    assert deleted.json()["result"]["structuredContent"]["deleted"] is True
    assert invalid_delete.status_code == 400
    assert invalid_update.status_code == 400
    MCPToolResult.model_validate(updated.json()["result"]["structuredContent"])


def test_backend_client_headers_errors_and_validation() -> None:
    captured: dict[str, str] = {}

    async def ok_handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["correlation"] = request.headers["X-Correlation-ID"]
        return httpx.Response(200, json={"procedures": []})

    async def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timeout")

    async def unavailable_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async def malformed_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": []})

    async def run() -> None:
        from backend.mcp.schemas import GetMyProceduresInput

        settings = _settings(backend_base_url="https://backend.example.com")
        client = SwissLawyerBackendClient(settings=settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(ok_handler), base_url="https://backend.example.com"))
        await client.get_procedures(external_user_key="fixed", payload=GetMyProceduresInput(), correlation_id="cid")
        assert captured == {"authorization": "Bearer internal-token", "correlation": "cid"}

        timeout_client = SwissLawyerBackendClient(settings=settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler), base_url="https://backend.example.com"))
        with pytest.raises(BackendTimeoutError):
            await timeout_client.get_procedures(external_user_key="fixed", payload=GetMyProceduresInput())

        unavailable_client = SwissLawyerBackendClient(settings=settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(unavailable_handler), base_url="https://backend.example.com"))
        with pytest.raises(BackendUnavailableError):
            await unavailable_client.get_procedures(external_user_key="fixed", payload=GetMyProceduresInput())

        malformed_client = SwissLawyerBackendClient(settings=settings, http_client=httpx.AsyncClient(transport=httpx.MockTransport(malformed_handler), base_url="https://backend.example.com"))
        with pytest.raises(InvalidBackendResponseError):
            await malformed_client.get_procedures(external_user_key="fixed", payload=GetMyProceduresInput())

    asyncio.run(run())


def test_internal_fastapi_routes_require_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-token")
    app = create_api_app()
    client = TestClient(app, raise_server_exceptions=False)

    missing = client.get("/internal/mcp/procedures", params={"external_user_key": "fixed"})
    invalid = client.get("/internal/mcp/procedures", params={"external_user_key": "fixed"}, headers={"Authorization": "Bearer wrong"})

    assert missing.status_code == 403
    assert invalid.status_code == 403


def test_internal_fastapi_accepts_valid_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "internal-token")
    app = create_api_app()

    class User:
        id = "u1"

    class FakeMemoryService:
        def get_or_create_user(self, *, external_user_key: str) -> User:
            assert external_user_key == "fixed"
            return User()

        def list_procedures(self, **kwargs: Any) -> list[Any]:
            return []

    app.dependency_overrides[dependencies.get_memory_service] = lambda: FakeMemoryService()
    response = TestClient(app, raise_server_exceptions=False).get(
        "/internal/mcp/procedures",
        params={"external_user_key": "fixed"},
        headers={"Authorization": "Bearer internal-token"},
    )
    assert response.status_code == 200
    assert response.json()["procedures"] == []


def test_docker_compose_and_scripts() -> None:
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    services = compose["services"]
    assert set(services) == {"api", "mcp"}
    assert services["mcp"]["environment"]["SWISS_LAWYER_API_BASE_URL"] == "http://api:8000"
    assert services["mcp"]["ports"] == ["127.0.0.1:8001:8001"]
    assert "ports" not in services["api"]
    assert "./data:/app/data" in services["api"]["volumes"]
    assert "./data:/app/data" in services["mcp"]["volumes"]
    assert "healthcheck" in services["api"]
    assert "healthcheck" in services["mcp"]
    assert Path("scripts/run_ngrok.sh").read_text().count("ngrok http") >= 1
    assert "8001" in Path("scripts/run_ngrok.sh").read_text()
    assert "authtoken" not in Path("scripts/run_ngrok.sh").read_text().lower()
