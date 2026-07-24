from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.ingestion import index
from backend.models.chunk import Chunk, ChunkMetadata
from backend.models.document import ExtractedPage, PdfDocument
from backend.utils.config import IngestionSettings


def test_run_orchestrates_ingestion_pipeline(tmp_path: Path) -> None:
    settings = IngestionSettings(
        pdf_root=tmp_path / "pdfs",
        chroma_path=tmp_path / "chromadb",
        collection_name="swiss_procedures",
        embedding_model="text-embedding-3-small",
        openai_api_key="test-key",
    )
    document = PdfDocument(
        path=tmp_path / "pdfs" / "federal" / "sample.pdf",
        source="sample.pdf",
        region="federal",
    )
    page = ExtractedPage(source="sample.pdf", region="federal", page=1, text="hello world")
    chunk = Chunk(
        id="chunk-id",
        text="hello world",
        metadata=ChunkMetadata(source="sample.pdf", region="federal", page=1),
    )
    embedder = MagicMock()
    embedder.embed_texts.return_value = [[0.1, 0.2]]
    store = MagicMock()

    with (
        patch.object(index, "load_ingestion_settings", return_value=settings),
        patch.object(index, "discover_pdfs", return_value=[document]) as discover,
        patch.object(index, "extract_pages", return_value=[page]) as extract,
        patch.object(index, "chunk_pages", return_value=[chunk]) as chunk_pages,
        patch.object(index, "create_embedder", return_value=embedder) as embedder_factory,
        patch.object(index, "ChromaChunkStore", return_value=store) as store_cls,
    ):
        index.run()

    discover.assert_called_once_with(settings.pdf_root)
    extract.assert_called_once_with(document)
    chunk_pages.assert_called_once_with(
        [page],
        chunk_size_words=settings.chunk_size_words,
        overlap_words=settings.chunk_overlap_words,
    )
    embedder_factory.assert_called_once_with(
        provider=settings.embedding_provider,
        ai_mode=settings.ai_mode,
        model="text-embedding-3-small",
        openai_api_key="test-key",
        ollama_base_url=settings.ollama_base_url,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
    )
    embedder.embed_texts.assert_called_once_with(["hello world"])
    store_cls.assert_called_once_with(
        path=settings.chroma_path,
        collection_name="swiss_procedures",
    )
    store.add_chunks.assert_called_once_with([chunk], [[0.1, 0.2]])


def test_run_reset_only_resets_target_collection(tmp_path: Path) -> None:
    settings = IngestionSettings(
        pdf_root=tmp_path / "pdfs",
        chroma_path=tmp_path / "chromadb",
        collection_name="swiss_lawyer__ollama__nomic_embed_text",
    )
    store = MagicMock()

    with (
        patch.object(index, "load_ingestion_settings", return_value=settings),
        patch.object(index, "discover_pdfs", return_value=[]),
        patch.object(index, "ChromaChunkStore", return_value=store) as store_cls,
    ):
        index.run(reset=True)

    store_cls.assert_called_once_with(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
    )
    store.reset_collection.assert_called_once_with()
    store.add_chunks.assert_not_called()
