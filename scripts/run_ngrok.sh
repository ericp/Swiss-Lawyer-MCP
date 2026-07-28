#!/usr/bin/env bash
set -euo pipefail

SCRIPT_NAME="run_ngrok"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local_dev_common.sh
source "${SCRIPT_DIR}/local_dev_common.sh"
cd "${REPO_ROOT}"

require_command ngrok "On macOS, run: brew install ngrok, then configure your ngrok account outside this repository."

python3 - <<'PY' || fail "Local MCP is not reachable on port 8001. Start it first with: ./scripts/start_local.sh"
import socket
import urllib.request

with socket.create_connection(("127.0.0.1", 8001), timeout=5):
    pass

with urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)
PY

printf 'Starting ngrok for local MCP at http://127.0.0.1:8001/mcp\n'
printf 'ChatGPT MCP URL: https://<ngrok-domain>/mcp\n'
printf 'Only MCP port 8001 is exposed. FastAPI 8000 and Ollama 11434 are not exposed by this script.\n'
printf 'Warning: the ngrok URL is public while this process is running. Do not share it.\n'

if [[ -n "${NGROK_DOMAIN:-}" ]]; then
  exec ngrok http --domain "$NGROK_DOMAIN" 8001
fi

exec ngrok http 8001
