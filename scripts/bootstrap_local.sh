#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="bootstrap_local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local_dev_common.sh
source "${SCRIPT_DIR}/local_dev_common.sh"
cd "${REPO_ROOT}"

info "[1/12] Checking prerequisites..."
require_command python3 "Install Python 3 with Homebrew or the official Python installer."
require_command curl "Install curl with Homebrew or your platform's package manager."
require_command docker "Install Docker Desktop, open it, and wait until it finishes starting."
require_command ollama "Install Ollama.app from https://ollama.com/download or use your platform's official installer."
docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable. Install or update Docker Desktop."

info "[2/12] Checking Docker..."
check_docker_engine

info "[3/12] Checking Ollama and required local models..."
check_ollama_reachable
ensure_ollama_models

info "[4/12] Creating and validating .env..."
ensure_env_file

info "[5/12] Creating persistent local directories..."
create_persistent_directories

info "[6/12] Reviewing source registry viability..."
source_registry_summary

info "[7/12] Building Docker images..."
docker compose down --remove-orphans
docker compose build

info "[8/12] Starting API service and running migrations..."
docker compose up -d api
if ! wait_for_compose_health api 90 2; then
  docker compose ps
  docker compose logs --tail=200 api
  fail "API service did not become healthy."
fi
docker compose exec -T api alembic upgrade head
docker compose exec -T api python -m backend.synchronizer.cli validate

info "[9/12] Synchronizing official source registry..."
sync_output="$(docker compose exec -T api python -m backend.synchronizer.cli sync --all 2>&1)"
printf '%s\n' "${sync_output}"
sync_status="$(printf '%s' "${sync_output}" | python3 -c 'import json,sys; text=sys.stdin.read(); start=text.find("{"); print(json.loads(text[start:]).get("status", "unknown") if start >= 0 else "unknown")' 2>/dev/null || true)"
failed_count="$(printf '%s' "${sync_output}" | python3 -c 'import json,sys; text=sys.stdin.read(); start=text.find("{"); print(json.loads(text[start:]).get("failed_count", 0) if start >= 0 else 0)' 2>/dev/null || echo 0)"
if [[ "${sync_status}" == "failed" ]]; then
  fail "Synchronization failed. Check docker compose logs --tail=200 api"
fi
if [[ "${failed_count}" != "0" ]]; then
  info "Warning: synchronization completed with ${failed_count} failed source(s). Existing valid local copies were preserved."
fi

info "[10/12] Building the local Ollama-backed ChromaDB index..."
index_output="$(docker compose exec -T api python -m backend.ingestion.index --reset 2>&1)"
printf '%s\n' "${index_output}"
printf '%s\n' "${index_output}" | grep -q "Embedding provider=ollama model=nomic-embed-text" || fail "Ingestion did not use the required local Ollama embedding provider."
stored_count="$(printf '%s\n' "${index_output}" | awk '/Generated [0-9]+ embedding/ {for (i=1; i<NF; i++) if ($i == "Generated" && $(i+1) ~ /^[0-9]+$/) print $(i+1)}' | tail -1)"
if [[ -z "${stored_count}" || "${stored_count}" == "0" ]]; then
  fail "No embeddings were generated. Check docker compose logs --tail=200 api"
fi

info "[11/12] Starting MCP service..."
docker compose up -d mcp
if ! wait_for_compose_health mcp 60 2; then
  docker compose logs --tail=200 mcp
  fail "MCP service did not become healthy."
fi

info "[12/12] Running complete local health check..."
chmod +x scripts/*.sh
./scripts/check_local_mcp.sh

cat <<'EOF'

Swiss Lawyer is ready.

Local MCP endpoint:
http://127.0.0.1:8001/mcp

To expose it temporarily through ngrok:
./scripts/run_ngrok.sh

To start it next time:
./scripts/start_local.sh

To stop it:
./scripts/stop_local.sh
EOF
