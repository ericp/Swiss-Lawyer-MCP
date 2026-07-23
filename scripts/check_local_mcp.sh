#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'check_local_mcp: %s\n' "$1" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker CLI is not installed. Install Docker Desktop and try again."
docker info >/dev/null 2>&1 || fail "Docker is not running. Start Docker Desktop and try again."

docker compose ps api >/dev/null 2>&1 || fail "Compose service 'api' is not available. Run docker compose up --build."
docker compose ps mcp >/dev/null 2>&1 || fail "Compose service 'mcp' is not available. Run docker compose up --build."

api_status="$(docker compose ps --format json api 2>/dev/null | tr '\n' ' ')"
mcp_status="$(docker compose ps --format json mcp 2>/dev/null | tr '\n' ' ')"
printf 'api service: %s\n' "${api_status:-unknown}"
printf 'mcp service: %s\n' "${mcp_status:-unknown}"

python - <<'PY' || fail "Local MCP endpoint is not reachable on http://127.0.0.1:8001/mcp."
import socket
import urllib.request

with socket.create_connection(("127.0.0.1", 8001), timeout=5):
    pass

with urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)

print("local MCP health check passed")
print("MCP Inspector URL: http://127.0.0.1:8001/mcp")
PY
