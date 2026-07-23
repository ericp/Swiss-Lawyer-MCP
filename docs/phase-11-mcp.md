# Phase 11: Local Single-User MCP Integration

Phase 11 exposes the existing Swiss Lawyer backend to ChatGPT as a remote MCP server for a private portfolio demonstration.

This phase does not add OAuth, Azure, Azure DevOps, a frontend, source synchronization controls, evaluation controls, or public multi-user hosting.

## Architecture

```text
Eric in ChatGPT
↓
ChatGPT Developer Mode app
Authentication: No Authentication
↓
Public ngrok HTTPS endpoint
↓
ngrok agent on Eric's Mac
↓
http://127.0.0.1:8001/mcp
↓
Docker Compose
├── MCP container
│   ├── Four MCP tools
│   ├── Fixed single-user identity
│   └── Internal service authentication
├── FastAPI container
│   └── ProcedureOrchestrator
└── ./data mounted as persistent local storage
```

The MCP tool handlers do not implement retrieval, reranking, generation, planning, clarification, or memory directly. They adapt ChatGPT tool calls into the existing Phase 8 FastAPI API.

## Security Model

This is a private, single-user local setup.

```bash
MCP_AUTH_MODE=single_user
MCP_SINGLE_USER_KEY=replace-with-a-private-local-key
```

Every tool call uses `MCP_SINGLE_USER_KEY` as the backend `external_user_key`. Tool inputs never accept `user_id`, `external_user_key`, account identifiers, authentication data, retrieval limits, model names, or prompt configuration.

The ngrok URL is public while ngrok is running. ngrok provides transport from the internet to localhost; it does not authenticate Swiss Lawyer users. Do not share the URL, do not leave ngrok running unnecessarily, and do not use this architecture for public multi-user access.

## Internal Service Token

MCP-to-FastAPI calls use:

```text
Authorization: Bearer <INTERNAL_SERVICE_TOKEN>
```

This token authenticates the MCP service to the internal FastAPI service. It does not identify the Swiss Lawyer user. FastAPI validates it with constant-time comparison on the dedicated `/internal/mcp/*` route group.

## Tools

The MCP server exposes exactly four tools:

| Tool | Purpose |
| --- | --- |
| `consult_swiss_procedure` | New questions, clarification answers, follow-ups, and continuing procedures |
| `get_my_procedures` | List, read, review, or resume saved procedures |
| `update_my_procedure` | Explicit progress/status/current-step/progress-note updates |
| `delete_my_swiss_lawyer_data` | Confirmed deletion of local user memory |

No tools are exposed for retrieval internals, reranking, planning internals, synchronization, evaluation, health checks, or user administration.

## Docker

Start locally:

```bash
cp .env.example .env
docker compose up --build
```

MCP is exposed only to the Mac:

```text
http://127.0.0.1:8001/mcp
```

FastAPI is private on the Docker network and reachable by MCP at:

```text
http://api:8000
```

Persistent data lives under:

```text
./data
```

`docker compose down` stops containers without deleting bind-mounted data. Avoid destructive volume-removal commands unless you intentionally want to remove state.

## Local Testing

```bash
./scripts/check_local_mcp.sh
```

Use MCP Inspector against:

```text
http://127.0.0.1:8001/mcp
```

Verify initialization, instructions, the four tool schemas, clarification response, procedure creation/listing, progress update, and confirmed deletion behavior.

## Future OAuth Migration

Before this becomes public or multi-user, add a real user-authentication layer. A future OAuth version should keep the same tool schemas and replace only the identity provider implementation.
