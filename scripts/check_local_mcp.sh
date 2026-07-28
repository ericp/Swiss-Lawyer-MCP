#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="check_local_mcp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local_dev_common.sh
source "${SCRIPT_DIR}/local_dev_common.sh"
cd "${REPO_ROOT}"

info "[1/7] Checking Docker and Compose services..."
check_docker_engine
docker compose config --services | grep -Fxq "api" || fail "Compose does not define service 'api'. Run: docker compose config"
docker compose config --services | grep -Fxq "mcp" || fail "Compose does not define service 'mcp'. Run: docker compose config"

api_state="$(docker compose ps --format json api 2>/dev/null | python3 -c 'import json,sys; data=sys.stdin.read().strip(); print(json.loads(data).get("State", "") if data else "")' 2>/dev/null || true)"
mcp_state="$(docker compose ps --format json mcp 2>/dev/null | python3 -c 'import json,sys; data=sys.stdin.read().strip(); print(json.loads(data).get("State", "") if data else "")' 2>/dev/null || true)"
[[ "${api_state}" == "running" ]] || fail "API container is not running. Try: docker compose up -d api; then docker compose logs --tail=200 api"
[[ "${mcp_state}" == "running" ]] || fail "MCP container is not running. Try: docker compose up -d mcp; then docker compose logs --tail=200 mcp"

info "[2/7] Checking FastAPI health inside the API container..."
docker compose exec -T api python - <<'PY' || fail "FastAPI health failed. Troubleshoot with: docker compose logs --tail=200 api"
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)
print("FastAPI health check passed")
PY

info "[3/7] Checking MCP health on localhost..."
python3 - <<'PY' || fail "MCP health failed. Troubleshoot with: docker compose logs --tail=200 mcp"
import socket
import urllib.request

with socket.create_connection(("127.0.0.1", 8001), timeout=5):
    pass
with urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)
print("MCP health check passed")
PY

info "[4/7] Checking Ollama on the Mac..."
check_ollama_reachable
ensure_ollama_models

info "[5/7] Checking API container access to host Ollama..."
docker compose exec -T api python - <<'PY' || fail "API cannot reach Ollama through host.docker.internal. Try: curl http://127.0.0.1:11434/api/tags and docker compose logs --tail=200 api"
import json
import urllib.request

required = {"nomic-embed-text", "llama3.2"}
with urllib.request.urlopen("http://host.docker.internal:11434/api/tags", timeout=5) as response:
    payload = json.loads(response.read().decode("utf-8"))
installed = set()
for model in payload.get("models", []):
    name = model.get("name", "")
    installed.add(name)
    installed.add(name.split(":")[0])
missing = required - installed
if missing:
    print("Missing Ollama model(s) visible from container: " + ", ".join(sorted(missing)))
    raise SystemExit(1)
print("API container can reach Ollama and required models")
PY

info "[6/7] Checking MCP Streamable HTTP endpoint..."
python3 - <<'PY' || fail "MCP protocol check failed. Troubleshoot with: docker compose logs --tail=200 mcp"
import json
import urllib.request

url = "http://127.0.0.1:8001/mcp"

def post(payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read().decode("utf-8")

status, body = post({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
if status != 200:
    raise SystemExit(1)
status, body = post({"jsonrpc": "2.0", "method": "notifications/initialized"})
if status not in {200, 202, 204} or body:
    raise SystemExit(1)
status, body = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
payload = json.loads(body)
tools = [tool["name"] for tool in payload["result"]["tools"]]
expected = [
    "consult_swiss_procedure",
    "get_my_procedures",
    "update_my_procedure",
    "delete_my_swiss_lawyer_data",
]
if tools != expected:
    raise SystemExit(f"Unexpected tools: {tools}")
print("MCP endpoint check passed: http://127.0.0.1:8001/mcp")
PY

info "[7/7] Local stack is healthy."
info "MCP Inspector URL: http://127.0.0.1:8001/mcp"
