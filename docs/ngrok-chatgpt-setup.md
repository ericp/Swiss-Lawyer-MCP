# ngrok and ChatGPT Developer Mode Setup

This guide connects ChatGPT to the local Swiss Lawyer MCP server through ngrok.

## 1. Install Local Tools

Install Docker Desktop for macOS and make sure it is running.

Install ngrok:

```bash
brew install ngrok
```

Create or use an ngrok account, then configure the authtoken locally:

```bash
ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
```

Do not store the authtoken in this repository.

## 2. Configure Swiss Lawyer

Create a local `.env`:

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"
MCP_SINGLE_USER_KEY="YOUR_PRIVATE_LOCAL_USER_KEY"
INTERNAL_SERVICE_TOKEN="YOUR_LONG_RANDOM_INTERNAL_TOKEN"
```

Leave:

```bash
MCP_AUTH_MODE=single_user
SWISS_LAWYER_API_BASE_URL=http://api:8000
```

## 3. Start Docker

Terminal 1:

```bash
docker compose up --build
```

Verify locally in Terminal 2:

```bash
./scripts/check_local_mcp.sh
```

The local MCP URL is:

```text
http://127.0.0.1:8001/mcp
```

## 4. Test with MCP Inspector

Use MCP Inspector against:

```text
http://127.0.0.1:8001/mcp
```

Confirm:

- server initialization works
- server instructions are shown
- exactly four tools are listed
- no OAuth token is required
- `consult_swiss_procedure` can return clarification questions
- procedure listing/update/delete tools are visible

## 5. Start ngrok

Terminal 3:

```bash
./scripts/run_ngrok.sh
```

If using a reserved ngrok domain:

```bash
export NGROK_DOMAIN="your-domain.ngrok-free.app"
./scripts/run_ngrok.sh
```

Copy the HTTPS forwarding URL, for example:

```text
https://example.ngrok-free.app
```

Append `/mcp`:

```text
https://example.ngrok-free.app/mcp
```

This URL is public while ngrok is running. Do not share it.

## 6. Connect from ChatGPT

Exact UI wording may change. The intended flow is:

1. Open ChatGPT web.
2. Open Settings.
3. Enable Developer Mode under Security and login.
4. Open the app/plugin management area.
5. Create a developer-mode app.
6. Enter the ngrok MCP URL ending in `/mcp`.
7. Select **No Authentication**.
8. Scan or refresh tools.
9. Verify exactly four tools appear:
   - `consult_swiss_procedure`
   - `get_my_procedures`
   - `update_my_procedure`
   - `delete_my_swiss_lawyer_data`
10. Start a conversation.
11. Enable Developer Mode and select Swiss Lawyer.
12. Test:

```text
Use Swiss Lawyer to determine what information you need from me to explain whether a Brazilian citizen can move to Zurich for employment.
```

## 7. Normal Shutdown

When finished:

1. Press Ctrl+C in the ngrok terminal.
2. Optionally stop Docker:

```bash
docker compose down
```

Persistent data remains under `./data`.

## Security Limits

This is a private portfolio deployment:

- Docker runs locally on the developer's Mac.
- ngrok runs locally on the Mac, outside Docker.
- ngrok forwards public HTTPS traffic to localhost port `8001`.
- FastAPI port `8000` is not exposed publicly.
- The MCP uses No Authentication.
- One server-side identity owns all stored memory.
- The endpoint is public while ngrok is active.
- The Mac must remain awake and connected.
- Docker and ngrok must remain running.
- OAuth and permanent hosted infrastructure are required before public multi-user use.
- Azure and Azure DevOps are not required.
