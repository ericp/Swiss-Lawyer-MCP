"""Embedding providers for ingestion, retrieval, synchronization, and evaluation."""

from __future__ import annotations

import os
from typing import Protocol

import httpx

from backend.utils.config import load_project_env


class Embedder(Protocol):
    """Common embedding interface used by production and evaluation flows."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed text inputs in request order."""


class EmbeddingConfigurationError(RuntimeError):
    """Raised when embedding provider settings are invalid."""


class OpenAIProviderDisabledError(EmbeddingConfigurationError):
    """Raised when OpenAI is requested while local mode is active."""


class OllamaEmbeddingError(RuntimeError):
    """Raised when Ollama cannot produce embeddings."""


class OpenAIEmbedder:
    """Generate embeddings with the configured OpenAI embedding model."""

    def __init__(self, *, api_key: str | None, model: str) -> None:
        load_project_env()
        if os.getenv("AI_MODE", "").strip().lower() == "local":
            raise OpenAIProviderDisabledError("OpenAI provider was requested while AI_MODE=local.")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to generate embeddings")
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed text inputs in request order."""

        if not texts:
            return []

        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class OllamaEmbedder:
    """Generate embeddings through a locally running Ollama server."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 180.0,
        batch_size: int = 64,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise EmbeddingConfigurationError("OLLAMA_BASE_URL is required for Ollama embeddings")
        if not model:
            raise EmbeddingConfigurationError("EMBEDDING_MODEL is required for Ollama embeddings")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._batch_size = batch_size
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @property
    def model(self) -> str:
        """Return the configured Ollama embedding model name."""

        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed text inputs in request order using Ollama /api/embed."""

        if not texts:
            return []

        embeddings: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = texts[start : start + self._batch_size]
            embeddings.extend(self._embed_batch(batch))

        if len(embeddings) != len(texts):
            raise OllamaEmbeddingError(
                f"Ollama returned {len(embeddings)} embedding(s) for {len(texts)} input(s)"
            )
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            message = _ollama_error_message(exc.response)
            raise OllamaEmbeddingError(
                f"Ollama embedding request failed for model {self._model}: {message}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaEmbeddingError(
                f"Ollama is unavailable at {self._base_url}: {exc}"
            ) from exc

        payload = response.json()
        if "error" in payload:
            raise OllamaEmbeddingError(
                f"Ollama embedding request failed for model {self._model}: {payload['error']}"
            )

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise OllamaEmbeddingError("Ollama embedding response did not contain embeddings")
        if len(embeddings) != len(texts):
            raise OllamaEmbeddingError(
                f"Ollama returned {len(embeddings)} embedding(s) for {len(texts)} input(s)"
            )
        return embeddings


def create_embedder(
    *,
    provider: str,
    ai_mode: str,
    model: str,
    openai_api_key: str | None = None,
    ollama_base_url: str = "http://127.0.0.1:11434",
    ollama_timeout_seconds: float = 180.0,
) -> Embedder:
    """Create the configured embedding provider."""

    provider = provider.strip().lower()
    ai_mode = ai_mode.strip().lower()
    if ai_mode == "local" and provider == "openai":
        raise OpenAIProviderDisabledError("OpenAI provider was requested while AI_MODE=local.")
    if provider == "ollama":
        return OllamaEmbedder(
            base_url=ollama_base_url,
            model=model,
            timeout_seconds=ollama_timeout_seconds,
        )
    if provider == "openai":
        return OpenAIEmbedder(api_key=openai_api_key, model=model)
    raise EmbeddingConfigurationError(f"Unknown embedding provider: {provider}")


def _ollama_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}"
    error = payload.get("error")
    if error:
        return str(error)
    return f"HTTP {response.status_code}"
