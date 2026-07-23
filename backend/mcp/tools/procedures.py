"""get_my_procedures tool."""

from __future__ import annotations

from backend.api.schemas import ProcedureDetailResponse
from backend.mcp.context import MCPToolContext
from backend.mcp.schemas import GetMyProceduresInput, MCPToolResult


async def get_my_procedures(
    *,
    context: MCPToolContext,
    payload: GetMyProceduresInput,
) -> MCPToolResult:
    response = await context.backend_client.get_procedures(
        external_user_key=context.identity_provider.get_external_user_key(),
        payload=payload,
        correlation_id=context.correlation_id,
    )
    if hasattr(response, "procedures"):
        return MCPToolResult(
            procedures=[_detail_to_dict(procedure) for procedure in response.procedures],
            message="Procedures loaded.",
        )
    if hasattr(response, "procedure_id"):
        detail = _detail_to_dict(response)
        return MCPToolResult(
            procedure_id=response.procedure_id,
            intent=response.intent,
            plan=detail["plan"],
            workflow_status=response.status.value,
            current_step=response.current_step,
            recent_interaction_summaries=response.recent_interaction_summaries,
            message="Procedure loaded.",
        )
    return MCPToolResult(message="Procedures loaded.")


def _detail_to_dict(procedure: ProcedureDetailResponse) -> dict[str, object]:
    return {
        "procedure_id": procedure.procedure_id,
        "intent": procedure.intent,
        "title": procedure.title,
        "status": procedure.status.value,
        "summary": procedure.summary,
        "plan": procedure.plan.model_dump(),
        "current_step": procedure.current_step,
        "recent_interaction_summaries": procedure.recent_interaction_summaries,
    }
