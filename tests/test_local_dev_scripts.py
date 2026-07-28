from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copytree(REPO_ROOT / "scripts", repo / "scripts")
    shutil.copy2(REPO_ROOT / ".env.example", repo / ".env.example")
    registry = repo / "data" / "pdfs" / "metadata"
    registry.mkdir(parents=True)
    (repo / "data" / "pdfs" / "federal").mkdir(parents=True)
    (repo / "data" / "pdfs" / "federal" / "sample.pdf").write_text("seed", encoding="utf-8")
    (registry / "sources.yaml").write_text(
        """
version: 1
sources:
  - id: seed_sample
    enabled: false
    region: federal
    authority: Swiss Confederation
    procedure_types:
      - immigration
    source_type: local_only
    url: local://data/pdfs/federal/sample.pdf
    language: unknown
    local_filename: sample.pdf
    discovery_enabled: false
""".lstrip(),
        encoding="utf-8",
    )
    return repo


def _make_fake_bin(tmp_path: Path, *, docker: bool = True, ollama: bool = True, curl: bool = True) -> Path:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    real_python = shutil.which("python3") or shutil.which("python")
    assert real_python is not None
    _write_executable(
        fake_bin / "python3",
        f"""#!/usr/bin/env bash
if [[ "${{1:-}}" == "-" ]]; then
  tmp="$(mktemp)"
  cat > "$tmp"
  if grep -Eq '127\\.0\\.0\\.1:8001|127\\.0\\.0\\.1:8000|host\\.docker\\.internal:11434' "$tmp"; then
    rm -f "$tmp"
    exit 0
  fi
  "{real_python}" "$tmp" "${{@:2}}"
  status="$?"
  rm -f "$tmp"
  exit "$status"
fi
exec "{real_python}" "$@"
""",
    )
    if docker:
        _write_executable(
            fake_bin / "docker",
            """#!/usr/bin/env bash
echo "docker $*" >> "${FAKE_LOG}"
if [[ "${DOCKER_INFO_FAIL:-}" == "1" && "$1" == "info" ]]; then exit 1; fi
if [[ "$1" == "info" ]]; then exit 0; fi
if [[ "$1" != "compose" ]]; then exit 0; fi
shift
case "${1:-}" in
  version) echo "Docker Compose version v2.0.0"; exit 0 ;;
  config)
    if [[ "${2:-}" == "--services" ]]; then printf "api\\nmcp\\n"; else echo "services: {}"; fi
    exit 0
    ;;
  ps)
    if [[ "$*" == *"--format json api"* || "$*" == *"--format"* && "$*" == *"api"* ]]; then
      echo '{"Service":"api","State":"running","Health":"healthy"}'
    elif [[ "$*" == *"--format json mcp"* || "$*" == *"--format"* && "$*" == *"mcp"* ]]; then
      echo '{"Service":"mcp","State":"running","Health":"healthy"}'
    else
      echo "api running"
      echo "mcp running"
    fi
    exit 0
    ;;
  down|build|up|logs) exit 0 ;;
  exec)
    if [[ "$*" == *"backend.synchronizer.cli validate"* ]]; then echo '{"valid": true, "source_count": 1}'; exit 0; fi
    if [[ "$*" == *"backend.synchronizer.cli sync --all"* ]]; then echo '{"run_id":"r1","requested_scope":"all","status":"completed","checked_count":1,"unchanged_count":0,"updated_count":1,"failed_count":0,"discovered_candidate_count":0,"events":["seed_sample: manually seeded"]}'; exit 0; fi
    if [[ "$*" == *"backend.ingestion.index --reset"* ]]; then
      echo "INFO __main__ - Embedding provider=ollama model=nomic-embed-text collection=swiss_lawyer__ollama__nomic_embed_text"
      echo "INFO __main__ - Generated 3 embedding(s)"
      exit 0
    fi
    cat >/dev/null || true
    exit 0
    ;;
esac
exit 0
""",
        )
    if ollama:
        _write_executable(
            fake_bin / "ollama",
            """#!/usr/bin/env bash
echo "ollama $*" >> "${FAKE_LOG}"
if [[ "$1" == "list" ]]; then
  echo "NAME ID SIZE MODIFIED"
  if [[ "${OLLAMA_MODELS:-}" == *"nomic-embed-text"* ]]; then echo "nomic-embed-text:latest abc 1 GB now"; fi
  if [[ "${OLLAMA_MODELS:-}" == *"llama3.2"* ]]; then echo "llama3.2:latest def 1 GB now"; fi
  exit 0
fi
if [[ "$1" == "pull" ]]; then exit 0; fi
exit 0
""",
        )
    if curl:
        _write_executable(
            fake_bin / "curl",
            """#!/usr/bin/env bash
echo "curl $*" >> "${FAKE_LOG}"
if [[ "${CURL_FAIL:-}" == "1" ]]; then exit 7; fi
echo '{"models":[{"name":"nomic-embed-text:latest"},{"name":"llama3.2:latest"}]}'
""",
        )
    return fake_bin


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def _run(script: Path, *, cwd: Path, fake_bin: Path, log: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin{os.pathsep}/usr/sbin{os.pathsep}/sbin",
        "FAKE_LOG": str(log),
        "OLLAMA_MODELS": "nomic-embed-text llama3.2",
    }
    if env:
        run_env.update(env)
    return subprocess.run(
        [str(script)],
        cwd=cwd,
        env=run_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )


def test_bootstrap_works_when_invoked_outside_repo_root(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    log = tmp_path / "calls.log"
    fake_bin = _make_fake_bin(tmp_path)

    result = _run(repo / "scripts" / "bootstrap_local.sh", cwd=outside, fake_bin=fake_bin, log=log)

    assert result.returncode == 0, result.stderr + result.stdout
    assert (repo / ".env").exists()
    env_text = (repo / ".env").read_text(encoding="utf-8")
    values = dict(line.split("=", 1) for line in env_text.splitlines() if "=" in line and not line.startswith("#"))
    assert values["MCP_SINGLE_USER_KEY"]
    assert values["INTERNAL_SERVICE_TOKEN"]
    assert values["MCP_SINGLE_USER_KEY"] != values["INTERNAL_SERVICE_TOKEN"]
    calls = log.read_text(encoding="utf-8")
    assert "docker compose up -d api" in calls
    assert "backend.synchronizer.cli sync --all" in calls
    assert "backend.ingestion.index --reset" in calls
    assert calls.index("docker compose up -d api") < calls.index("backend.synchronizer.cli sync --all")
    assert calls.index("backend.ingestion.index --reset") < calls.index("docker compose up -d mcp")
    assert "Swiss Lawyer is ready." in result.stdout
    assert values["MCP_SINGLE_USER_KEY"] not in result.stdout
    assert values["INTERNAL_SERVICE_TOKEN"] not in result.stdout


def test_bootstrap_fails_when_docker_missing(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path, docker=False)
    result = _run(repo / "scripts" / "bootstrap_local.sh", cwd=tmp_path, fake_bin=fake_bin, log=tmp_path / "calls.log")

    assert result.returncode != 0
    assert "Docker Desktop" in result.stderr


def test_bootstrap_fails_when_docker_engine_stopped(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    result = _run(
        repo / "scripts" / "bootstrap_local.sh",
        cwd=tmp_path,
        fake_bin=fake_bin,
        log=tmp_path / "calls.log",
        env={"DOCKER_INFO_FAIL": "1"},
    )

    assert result.returncode != 0
    assert "engine is not running" in result.stderr


def test_bootstrap_fails_when_ollama_missing(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path, ollama=False)
    result = _run(repo / "scripts" / "bootstrap_local.sh", cwd=tmp_path, fake_bin=fake_bin, log=tmp_path / "calls.log")

    assert result.returncode != 0
    assert "Ollama.app" in result.stderr


def test_bootstrap_fails_when_ollama_not_running(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    result = _run(
        repo / "scripts" / "bootstrap_local.sh",
        cwd=tmp_path,
        fake_bin=fake_bin,
        log=tmp_path / "calls.log",
        env={"CURL_FAIL": "1"},
    )

    assert result.returncode != 0
    assert "Ollama is not reachable" in result.stderr


def test_missing_ollama_models_are_pulled_and_existing_are_not(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    log = tmp_path / "calls.log"

    result = _run(
        repo / "scripts" / "bootstrap_local.sh",
        cwd=tmp_path,
        fake_bin=fake_bin,
        log=log,
        env={"OLLAMA_MODELS": "nomic-embed-text"},
    )

    assert result.returncode == 0, result.stderr + result.stdout
    calls = log.read_text(encoding="utf-8")
    assert "ollama pull llama3.2" in calls
    assert "ollama pull nomic-embed-text" not in calls


def test_existing_env_is_not_overwritten_and_placeholders_are_rejected(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    env_path = repo / ".env"
    env_path.write_text(
        (repo / ".env.example")
        .read_text(encoding="utf-8")
        .replace("replace-with-a-random-local-key", "changeme")
        .replace("replace-with-a-different-random-token", "secret-token"),
        encoding="utf-8",
    )

    result = _run(repo / "scripts" / "bootstrap_local.sh", cwd=tmp_path, fake_bin=fake_bin, log=tmp_path / "calls.log")

    assert result.returncode != 0
    assert "MCP_SINGLE_USER_KEY contains an unsafe placeholder" in result.stderr
    assert "changeme" in env_path.read_text(encoding="utf-8")


def test_start_local_does_not_sync_or_reset_and_build_flag_builds(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    log = tmp_path / "calls.log"
    shutil.copy2(repo / ".env.example", repo / ".env")
    env_text = (repo / ".env").read_text(encoding="utf-8")
    env_text = env_text.replace("replace-with-a-random-local-key", "local-secret-key")
    env_text = env_text.replace("replace-with-a-different-random-token", "different-local-token")
    (repo / ".env").write_text(env_text, encoding="utf-8")
    (repo / "data" / "chromadb").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "chromadb" / "chroma.sqlite3").write_text("db", encoding="utf-8")

    result = _run(repo / "scripts" / "start_local.sh", cwd=tmp_path, fake_bin=fake_bin, log=log)
    build_result = subprocess.run(
        [str(repo / "scripts" / "start_local.sh"), "--build"],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{fake_bin}{os.pathsep}/usr/bin{os.pathsep}/bin{os.pathsep}/usr/sbin{os.pathsep}/sbin", "FAKE_LOG": str(log), "OLLAMA_MODELS": "nomic-embed-text llama3.2"},
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert build_result.returncode == 0, build_result.stderr + build_result.stdout
    calls = log.read_text(encoding="utf-8")
    assert "backend.synchronizer.cli sync --all" not in calls
    assert "backend.ingestion.index --reset" not in calls
    assert "docker compose up -d --build" in calls


def test_stop_local_preserves_volumes(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    fake_bin = _make_fake_bin(tmp_path)
    log = tmp_path / "calls.log"

    result = _run(repo / "scripts" / "stop_local.sh", cwd=tmp_path, fake_bin=fake_bin, log=log)

    assert result.returncode == 0, result.stderr + result.stdout
    calls = log.read_text(encoding="utf-8")
    assert "docker compose down" in calls
    assert "-v" not in calls
    assert "--volumes" not in calls
    assert "Local data has been preserved." in result.stdout
