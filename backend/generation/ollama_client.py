"""Small Ollama chat client compatible with existing chat-completions callers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import httpx


class OllamaChatError(RuntimeError):
    """Raised when Ollama chat generation fails."""


class OllamaChatClient:
    """Expose a minimal OpenAI-like chat.completions.create interface."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float = 180.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise ValueError("OLLAMA_BASE_URL is required for Ollama chat")
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self.chat = _OllamaChat(self)

    def _create(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
        **_: Any,
    ) -> Any:
        if not model:
            raise ValueError("Ollama model is required")
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if response_format == {"type": "json_object"}:
            payload["format"] = "json"

        try:
            response = self._client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OllamaChatError(_ollama_chat_error(exc.response, model)) from exc
        except httpx.HTTPError as exc:
            raise OllamaChatError(f"Ollama is unavailable at {self._base_url}: {exc}") from exc

        response_payload = response.json()
        if "error" in response_payload:
            raise OllamaChatError(
                f"Ollama chat request failed for model {model}: {response_payload['error']}"
            )
        content = response_payload.get("message", {}).get("content")
        if not isinstance(content, str):
            raise OllamaChatError("Ollama chat response did not contain message.content")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


class _OllamaChat:
    def __init__(self, parent: OllamaChatClient) -> None:
        self.completions = _OllamaCompletions(parent)


class _OllamaCompletions:
    def __init__(self, parent: OllamaChatClient) -> None:
        self._parent = parent

    def create(self, **kwargs: Any) -> Any:
        return self._parent._create(**kwargs)


def _ollama_chat_error(response: httpx.Response, model: str) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"Ollama chat request failed for model {model}: HTTP {response.status_code}"
    error = payload.get("error")
    if error:
        return f"Ollama chat request failed for model {model}: {error}"
    return f"Ollama chat request failed for model {model}: HTTP {response.status_code}"
