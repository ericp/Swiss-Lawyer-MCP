"""update_my_procedure tool."""

from __future__ import annotations

from backend.mcp.context import MCPToolContext
from backend.mcp.schemas import MCPToolResult, UpdateMyProcedureInput


async def update_my_procedure(
    *,
    context: MCPToolContext,
    payload: UpdateMyProcedureInput,
) -> MCPToolResult:
    response = await context.backend_client.update_procedure(
        external_user_key=context.identity_provider.get_external_user_key(),
        payload=payload,
        correlation_id=context.correlation_id,
    )
    return MCPToolResult(
        procedure_id=response.procedure_id,
        intent=response.intent,
        plan=response.plan.model_dump(),
        workflow_status=response.status.value,
        current_step=response.current_step,
        recent_interaction_summaries=response.recent_interaction_summaries,
        message="Procedure progress updated.",
    )
