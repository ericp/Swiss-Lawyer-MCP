"""consult_swiss_procedure tool."""

from __future__ import annotations

from backend.mcp.context import MCPToolContext
from backend.mcp.schemas import ConsultSwissProcedureInput, MCPToolResult


async def consult_swiss_procedure(
    *,
    context: MCPToolContext,
    payload: ConsultSwissProcedureInput,
) -> MCPToolResult:
    response = await context.backend_client.consult(
        external_user_key=context.identity_provider.get_external_user_key(),
        payload=payload,
        correlation_id=context.correlation_id,
    )
    return MCPToolResult.model_validate(
        {
            "state": response.state.value,
            "procedure_id": response.procedure_id,
            "intent": response.intent,
            "needs_clarification": response.needs_clarification,
            "clarification_questions": [question.model_dump() for question in response.clarification_questions],
            "missing_fields": response.missing_fields,
            "answer": response.answer.model_dump() if response.answer else None,
            "plan": response.plan.model_dump() if response.plan else None,
            "sources": [source.model_dump() for source in response.sources],
            "confidence": response.confidence,
            "insufficient_context": response.insufficient_context,
            "saved_profile_fields": response.saved_profile_fields,
            "workflow_status": response.workflow_status.value if response.workflow_status else None,
            "disclaimer": response.disclaimer,
            "message": _message_for_state(response.state.value),
        }
    )


def _message_for_state(state: str) -> str:
    if state == "clarification_required":
        return "Clarification is required before continuing."
    if state == "insufficient_context":
        return "Retrieved official context is insufficient for a complete answer."
    if state == "answered":
        return "Grounded answer and procedure state returned."
    return "Procedure query completed."
