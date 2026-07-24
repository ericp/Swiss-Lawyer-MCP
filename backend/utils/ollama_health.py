"""Ollama readiness checks for local zero-cost execution."""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class OllamaHealth:
    """Summary of Ollama reachability and required local models."""

    reachable: bool
    installed_models: set[str]
    missing_models: list[str]
    error: str | None = None

    @property
    def status(self) -> str:
        if not self.reachable:
            return "unhealthy"
        if self.missing_models:
            return "not_ready"
        return "healthy"


def check_ollama_health(
    *,
    base_url: str,
    required_models: list[str],
    timeout_seconds: float = 5.0,
) -> OllamaHealth:
    """Check Ollama /api/tags and whether required models are installed."""

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return OllamaHealth(
            reachable=False,
            installed_models=set(),
            missing_models=sorted(set(required_models)),
            error=str(exc),
        )

    installed = {
        model.get("name", "").split(":")[0]
        for model in payload.get("models", [])
        if isinstance(model, dict)
    }
    installed.update(
        model.get("name", "")
        for model in payload.get("models", [])
        if isinstance(model, dict)
    )
    missing = [
        model
        for model in sorted(set(required_models))
        if model and model not in installed
    ]
    return OllamaHealth(
        reachable=True,
        installed_models=installed,
        missing_models=missing,
    )
