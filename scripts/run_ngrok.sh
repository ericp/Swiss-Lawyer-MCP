#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf 'run_ngrok: %s\n' "$1" >&2
  exit 1
}

command -v ngrok >/dev/null 2>&1 || fail "ngrok is not installed. On macOS, run: brew install ngrok"

python - <<'PY' || fail "Local MCP is not reachable on port 8001. Start Docker first with: docker compose up --build"
import socket
import urllib.request

with socket.create_connection(("127.0.0.1", 8001), timeout=5):
    pass

with urllib.request.urlopen("http://127.0.0.1:8001/healthz", timeout=5) as response:
    if response.status >= 400:
        raise SystemExit(1)
PY

printf 'Starting ngrok for local MCP at http://127.0.0.1:8001/mcp\n'
printf 'ChatGPT MCP URL will be the HTTPS forwarding URL with /mcp appended.\n'
printf 'Warning: the ngrok URL is public while this process is running. Do not share it.\n'

if [[ -n "${NGROK_DOMAIN:-}" ]]; then
  exec ngrok http --domain "$NGROK_DOMAIN" 8001
fi

exec ngrok http 8001
