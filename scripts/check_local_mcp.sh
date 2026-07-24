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

docker compose exec -T api python - <<'PY' || fail "FastAPI health is not reachable inside the API container. Check: docker compose logs api"
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)

print("api service health check passed")
PY

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

python - <<'PY' || fail "Ollama is not ready. Run: ollama serve; ollama pull nomic-embed-text; ollama pull llama3.2"
import json
import os
import urllib.request

base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
required = {"nomic-embed-text", "llama3.2"}

with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as response:
    payload = json.loads(response.read().decode("utf-8"))

installed = set()
for model in payload.get("models", []):
    name = model.get("name", "")
    installed.add(name)
    installed.add(name.split(":")[0])

missing = sorted(required - installed)
if missing:
    print("Missing Ollama model(s): " + ", ".join(missing))
    for model in missing:
        print(f"Fix: ollama pull {model}")
    raise SystemExit(1)

print("ollama health check passed")
PY
