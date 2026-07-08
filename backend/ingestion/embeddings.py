"""OpenAI embedding client wrapper."""

from __future__ import annotations

from openai import OpenAI


class OpenAIEmbedder:
    """Generate embeddings with the configured OpenAI embedding model."""

    def __init__(self, *, api_key: str | None, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to generate embeddings")
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
