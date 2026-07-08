from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.embeddings import OpenAIEmbedder


def test_openai_embedder_requires_api_key() -> None:
    with pytest.raises(ValueError):
        OpenAIEmbedder(api_key=None, model="text-embedding-3-small")


def test_openai_embedder_returns_embeddings_in_order() -> None:
    response = MagicMock()
    response.data = [
        MagicMock(embedding=[0.1, 0.2]),
        MagicMock(embedding=[0.3, 0.4]),
    ]
    client = MagicMock()
    client.embeddings.create.return_value = response

    with patch("backend.ingestion.embeddings.OpenAI") as openai_cls:
        openai_cls.return_value = client
        embedder = OpenAIEmbedder(api_key="test-key", model="text-embedding-3-small")
        embeddings = embedder.embed_texts(["first", "second"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    client.embeddings.create.assert_called_once_with(
        model="text-embedding-3-small",
        input=["first", "second"],
    )
