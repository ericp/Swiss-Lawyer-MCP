"""delete_my_swiss_lawyer_data tool."""

from __future__ import annotations

from backend.mcp.context import MCPToolContext
from backend.mcp.schemas import DeleteMySwissLawyerDataInput, MCPToolResult


async def delete_my_swiss_lawyer_data(
    *,
    context: MCPToolContext,
    payload: DeleteMySwissLawyerDataInput,
) -> MCPToolResult:
    response = await context.backend_client.delete_memory(
        external_user_key=context.identity_provider.get_external_user_key(),
        correlation_id=context.correlation_id,
    )
    return MCPToolResult(
        deleted=response.deleted,
        message=(
            "Local Swiss Lawyer memory deleted. Official documents, ChromaDB knowledge, "
            "synchronization metadata and evaluation artifacts were not deleted."
        ),
    )
