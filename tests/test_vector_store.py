from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.ingestion.vector_store import ChromaChunkStore
from backend.models.chunk import Chunk, ChunkMetadata


def test_chroma_store_inserts_chunks_with_documents_embeddings_and_metadata(
    tmp_path: Path,
) -> None:
    collection = MagicMock()
    client = MagicMock()
    client.get_or_create_collection.return_value = collection
    chunk = Chunk(
        id="federal:sample.pdf:p1:c1:abc123",
        text="Swiss permit information",
        metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
    )

    with patch("backend.ingestion.vector_store.chromadb.PersistentClient") as client_cls:
        client_cls.return_value = client
        store = ChromaChunkStore(path=tmp_path / "chromadb", collection_name="swiss_procedures")
        store.add_chunks([chunk], [[0.1, 0.2, 0.3]])

    client_cls.assert_called_once_with(path=str(tmp_path / "chromadb"))
    client.get_or_create_collection.assert_called_once_with(name="swiss_procedures")
    collection.add.assert_called_once_with(
        ids=["federal:sample.pdf:p1:c1:abc123"],
        documents=["Swiss permit information"],
        embeddings=[[0.1, 0.2, 0.3]],
        metadatas=[{"source": "sample.pdf", "region": "federal", "page": 1}],
    )


def test_chroma_store_rejects_embedding_count_mismatch(tmp_path: Path) -> None:
    with patch("backend.ingestion.vector_store.chromadb.PersistentClient") as client_cls:
        client_cls.return_value.get_or_create_collection.return_value = MagicMock()
        store = ChromaChunkStore(path=tmp_path / "chromadb", collection_name="swiss_procedures")

    chunk = Chunk(
        id="id",
        text="text",
        metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
    )

    try:
        store.add_chunks([chunk], [])
    except ValueError as error:
        assert "same length" in str(error)
    else:
        raise AssertionError("Expected ValueError")
