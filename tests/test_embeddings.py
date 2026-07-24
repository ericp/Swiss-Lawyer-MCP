from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.ingestion.embeddings import (
    OllamaEmbedder,
    OllamaEmbeddingError,
    OpenAIEmbedder,
    OpenAIProviderDisabledError,
    create_embedder,
)


def test_openai_embedder_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    with pytest.raises(ValueError):
        OpenAIEmbedder(api_key=None, model="text-embedding-3-small")


def test_openai_embedder_returns_embeddings_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODE", raising=False)
    response = MagicMock()
    response.data = [
        MagicMock(embedding=[0.1, 0.2]),
        MagicMock(embedding=[0.3, 0.4]),
    ]
    client = MagicMock()
    client.embeddings.create.return_value = response

    with patch("openai.OpenAI") as openai_cls:
        openai_cls.return_value = client
        embedder = OpenAIEmbedder(api_key="test-key", model="text-embedding-3-small")
        embeddings = embedder.embed_texts(["first", "second"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["first", "second"],
    )


def test_local_mode_rejects_openai_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODE", "local")

    with pytest.raises(OpenAIProviderDisabledError):
        OpenAIEmbedder(api_key="test-key", model="text-embedding-3-small")


def test_create_embedder_selects_ollama_in_local_mode() -> None:
    embedder = create_embedder(
        provider="ollama",
        ai_mode="local",
        model="nomic-embed-text",
        ollama_base_url="http://localhost:11434",
    )

    assert isinstance(embedder, OllamaEmbedder)


def test_ollama_embedder_success_preserves_order() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/embed"
        return httpx.Response(
            200,
            json={"embeddings": [[0.1, 0.2], [0.3, 0.4]]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = OllamaEmbedder(
        base_url="http://ollama.test",
        model="nomic-embed-text",
        client=client,
    )

    assert embedder.embed_texts(["first", "second"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_ollama_embedder_batches_in_order() -> None:
    calls: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json_from_request(request)
        calls.append(payload["input"])
        start = len(calls) * 10
        return httpx.Response(
            200,
            json={"embeddings": [[start + index] for index, _ in enumerate(payload["input"])]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = OllamaEmbedder(
        base_url="http://ollama.test",
        model="nomic-embed-text",
        batch_size=2,
        client=client,
    )

    assert embedder.embed_texts(["a", "b", "c"]) == [[10], [11], [20]]
    assert calls == [["a", "b"], ["c"]]


def test_ollama_embedder_rejects_count_mismatch() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"embeddings": [[0.1]]})
        )
    )
    embedder = OllamaEmbedder(
        base_url="http://ollama.test",
        model="nomic-embed-text",
        client=client,
    )

    with pytest.raises(OllamaEmbeddingError, match="returned 1 embedding"):
        embedder.embed_texts(["first", "second"])


def test_ollama_embedder_reports_model_missing() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(404, json={"error": "model not found"})
        )
    )
    embedder = OllamaEmbedder(
        base_url="http://ollama.test",
        model="missing-model",
        client=client,
    )

    with pytest.raises(OllamaEmbeddingError, match="model not found"):
        embedder.embed_texts(["hello"])


def test_ollama_embedder_reports_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    embedder = OllamaEmbedder(
        base_url="http://ollama.test",
        model="nomic-embed-text",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(OllamaEmbeddingError, match="unavailable"):
        embedder.embed_texts(["hello"])


def json_from_request(request: httpx.Request) -> dict[str, object]:
    import json

    return json.loads(request.content.decode("utf-8"))
