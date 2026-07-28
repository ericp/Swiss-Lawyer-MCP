#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

fail() {
  printf '%s: %s\n' "${SCRIPT_NAME:-local-dev}" "$1" >&2
  exit 1
}

info() {
  printf '%s\n' "$1"
}

require_command() {
  local command_name="$1"
  local install_hint="$2"
  command -v "${command_name}" >/dev/null 2>&1 || fail "${command_name} is not installed. ${install_hint}"
}

check_docker_engine() {
  require_command docker "Install Docker Desktop, open it, and wait until it finishes starting."
  docker compose version >/dev/null 2>&1 || fail "Docker Compose is unavailable. Install or update Docker Desktop."
  docker info >/dev/null 2>&1 || fail "Docker is installed but the engine is not running. Open Docker Desktop and wait until it finishes starting."
}

check_ollama_reachable() {
  require_command ollama "Install Ollama.app from https://ollama.com/download or use your platform's official installer."
  require_command curl "Install curl with Homebrew or your platform's package manager."
  curl -fsS "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1 || fail "Ollama is not reachable at http://127.0.0.1:11434. On macOS, open /Applications/Ollama.app. On Linux, start your Ollama service or run ollama serve. Do not expose Ollama publicly."
}

ollama_model_installed() {
  local model="$1"
  ollama list | awk 'NR > 1 {print $1}' | sed 's/:.*//' | grep -Fxq "${model}"
}

ensure_ollama_models() {
  local model
  for model in nomic-embed-text llama3.2; do
    if ollama_model_installed "${model}"; then
      info "Ollama model already installed: ${model}"
    else
      info "Pulling missing Ollama model: ${model}"
      ollama pull "${model}"
    fi
  done
}

safe_env_value() {
  local key="$1"
  local file="${2:-.env}"
  python3 - "$file" "$key" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
if not path.exists():
    raise SystemExit(0)
for line in path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    name, value = stripped.split("=", 1)
    if name.strip() == key:
        print(value.strip().strip('"').strip("'"))
        break
PY
}

generate_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32
}

ensure_env_file() {
  require_command python3 "Install Python 3 using Homebrew or the official Python installer."
  if [[ ! -f ".env.example" ]]; then
    fail ".env.example is missing."
  fi
  if [[ -f ".env" ]]; then
    info ".env already exists; preserving it."
  else
    cp ".env.example" ".env"
    local single_user_key
    local internal_token
    single_user_key="$(generate_secret)"
    internal_token="$(generate_secret)"
    if [[ "${single_user_key}" == "${internal_token}" ]]; then
      internal_token="$(generate_secret)"
    fi
    python3 - ".env" "${single_user_key}" "${internal_token}" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
single_user_key = sys.argv[2]
internal_token = sys.argv[3]
lines = path.read_text(encoding="utf-8").splitlines()
replacements = {
    "MCP_SINGLE_USER_KEY": single_user_key,
    "INTERNAL_SERVICE_TOKEN": internal_token,
}
updated = []
seen = set()
for line in lines:
    if "=" not in line or line.lstrip().startswith("#"):
        updated.append(line)
        continue
    name, _ = line.split("=", 1)
    if name in replacements:
        updated.append(f"{name}={replacements[name]}")
        seen.add(name)
    else:
        updated.append(line)
for name, value in replacements.items():
    if name not in seen:
        updated.append(f"{name}={value}")
path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
    info ".env created with generated local secrets."
  fi
  validate_env_file
}

validate_env_file() {
  local required_pairs=(
    "AI_MODE=local"
    "EMBEDDING_PROVIDER=ollama"
    "EMBEDDING_MODEL=nomic-embed-text"
    "GENERATION_PROVIDER=ollama"
    "GENERATION_MODEL=llama3.2"
    "PLANNER_PROVIDER=ollama"
    "PLANNER_MODEL=llama3.2"
    "RERANKER_PROVIDER=disabled"
    "OLLAMA_BASE_URL=http://127.0.0.1:11434"
    "MCP_AUTH_MODE=single_user"
  )
  local pair key expected actual
  for pair in "${required_pairs[@]}"; do
    key="${pair%%=*}"
    expected="${pair#*=}"
    actual="$(safe_env_value "${key}")"
    if [[ "${actual}" != "${expected}" ]]; then
      fail ".env must set ${key}=${expected} for local mode. Current value: ${actual:-<missing>}"
    fi
  done

  python3 - ".env" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
placeholder = re.compile(r"(replace-me|your-key|changeme|placeholder|replace-with|change-this)", re.I)
required = ["MCP_SINGLE_USER_KEY", "INTERNAL_SERVICE_TOKEN"]
values = {}
for line in path.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        continue
    name, value = stripped.split("=", 1)
    values[name.strip()] = value.strip().strip('"').strip("'")
bad = []
for name in required:
    value = values.get(name, "")
    if not value:
        bad.append(f"{name} is empty")
    elif placeholder.search(value):
        bad.append(f"{name} contains an unsafe placeholder")
if values.get("MCP_SINGLE_USER_KEY") and values.get("MCP_SINGLE_USER_KEY") == values.get("INTERNAL_SERVICE_TOKEN"):
    bad.append("MCP_SINGLE_USER_KEY and INTERNAL_SERVICE_TOKEN must be different")
if bad:
    for item in bad:
        print(item, file=sys.stderr)
    raise SystemExit(1)
PY
}

create_persistent_directories() {
  mkdir -p \
    data/pdfs \
    data/pdfs/metadata \
    data/chromadb \
    data/sqlite \
    data/documents \
    data/tmp/synchronizer \
    evaluation/artifacts \
    evaluation/reports
}

source_registry_summary() {
  python3 - "data/pdfs/metadata/sources.yaml" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print("Source registry missing: data/pdfs/metadata/sources.yaml", file=sys.stderr)
    raise SystemExit(1)

sources = []
current = None
for raw in path.read_text(encoding="utf-8").splitlines():
    if re.match(r"^\s*-\s+id:", raw):
        if current:
            sources.append(current)
        current = {"id": raw.split(":", 1)[1].strip().strip('"')}
        continue
    if current is None:
        continue
    match = re.match(r"^\s+([a-zA-Z_]+):\s*(.*)$", raw)
    if match:
        key, value = match.groups()
        current[key] = value.strip().strip('"')
if current:
    sources.append(current)

enabled = [source for source in sources if source.get("enabled", "").lower() == "true"]
enabled_remote = [
    source for source in enabled
    if source.get("source_type") in {"pdf", "webpage", "landing_page"}
    and source.get("url", "").startswith("https://")
]
local_only = [source for source in sources if source.get("source_type") == "local_only"]
lacking_real_urls = [
    source for source in sources
    if not source.get("url", "").startswith("https://")
]
missing_local = []
for source in local_only:
    local_url = source.get("url", "")
    if local_url.startswith("local://"):
        local_path = Path(local_url.removeprefix("local://"))
        if not local_path.exists():
            missing_local.append(f"{source.get('id')}: {local_path}")

print("Source registry summary:")
print(f"- total sources: {len(sources)}")
print(f"- enabled sources: {len(enabled)}")
print(f"- enabled remote PDFs: {sum(1 for source in enabled_remote if source.get('source_type') == 'pdf')}")
print(f"- enabled webpages: {sum(1 for source in enabled_remote if source.get('source_type') == 'webpage')}")
print(f"- enabled landing pages: {sum(1 for source in enabled_remote if source.get('source_type') == 'landing_page')}")
print(f"- local-only sources: {len(local_only)}")
print(f"- entries lacking verified HTTPS URLs: {len(lacking_real_urls)}")
if enabled_remote:
    print("- auto-downloadable source IDs: " + ", ".join(source["id"] for source in enabled_remote))
else:
    print("- auto-downloadable source IDs: none")
if local_only:
    print("- local-only source IDs: " + ", ".join(source["id"] for source in local_only))
if missing_local:
    print("Missing local-only seed files:", file=sys.stderr)
    for item in missing_local:
        print(f"- {item}", file=sys.stderr)
    raise SystemExit(2)
if not enabled_remote:
    print("Warning: no enabled remote official sources are currently configured. Synchronization will record manually seeded local sources only.")
PY
}

wait_for_compose_health() {
  local service="$1"
  local attempts="${2:-60}"
  local delay_seconds="${3:-2}"
  local status
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    status="$(docker compose ps --format json "${service}" 2>/dev/null | python3 -c 'import json,sys; data=sys.stdin.read().strip(); print((json.loads(data).get("Health") or json.loads(data).get("State") or "").lower() if data else "")' 2>/dev/null || true)"
    if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
      return 0
    fi
    sleep "${delay_seconds}"
  done
  return 1
}

require_index_data_exists() {
  if [[ ! -f "data/chromadb/chroma.sqlite3" ]]; then
    fail "ChromaDB index is missing. Run ./scripts/bootstrap_local.sh first."
  fi
}
