#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="start_local"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local_dev_common.sh
source "${SCRIPT_DIR}/local_dev_common.sh"
cd "${REPO_ROOT}"

build_flag=false
if [[ "${1:-}" == "--build" ]]; then
  build_flag=true
  shift
fi
if [[ "$#" -gt 0 ]]; then
  cat >&2 <<'EOF'
Usage: ./scripts/start_local.sh [--build]

Starts the local API and MCP services without synchronizing sources,
resetting ChromaDB, deleting memory, or overwriting .env.
EOF
  exit 2
fi

info "[1/7] Checking Docker..."
check_docker_engine

info "[2/7] Checking Ollama..."
check_ollama_reachable
ensure_ollama_models

info "[3/7] Checking local configuration and index..."
[[ -f ".env" ]] || fail ".env is missing. Run ./scripts/bootstrap_local.sh first."
validate_env_file
require_index_data_exists

info "[4/7] Starting Docker services..."
if [[ "${build_flag}" == "true" ]]; then
  docker compose up -d --build
else
  docker compose up -d
fi

info "[5/7] Waiting for API readiness..."
if ! wait_for_compose_health api 90 2; then
  docker compose ps
  docker compose logs --tail=200 api
  fail "API service did not become healthy."
fi

info "[6/7] Waiting for MCP readiness..."
if ! wait_for_compose_health mcp 60 2; then
  docker compose ps
  docker compose logs --tail=200 mcp
  fail "MCP service did not become healthy."
fi

info "[7/7] Running complete local health check..."
./scripts/check_local_mcp.sh

cat <<'EOF'

Swiss Lawyer is running.
Local MCP endpoint: http://127.0.0.1:8001/mcp
EOF
