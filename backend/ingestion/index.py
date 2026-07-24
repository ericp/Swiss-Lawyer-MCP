"""CLI entrypoint for the Phase 1 PDF ingestion pipeline."""

from __future__ import annotations

import logging
import argparse

from backend.ingestion.chunking import chunk_pages
from backend.ingestion.discovery import discover_pdfs
from backend.ingestion.embeddings import create_embedder
from backend.ingestion.extraction import extract_pages
from backend.ingestion.vector_store import ChromaChunkStore
from backend.utils.config import load_ingestion_settings

logger = logging.getLogger(__name__)


def run(*, reset: bool = False) -> None:
    """Run PDF discovery, extraction, chunking, embedding, and storage."""

    settings = load_ingestion_settings()
    logger.info(
        "Embedding provider=%s model=%s collection=%s",
        settings.embedding_provider,
        settings.embedding_model,
        settings.collection_name,
    )
    store = ChromaChunkStore(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
    )
    if reset:
        logger.warning("Resetting only ChromaDB collection %s", settings.collection_name)
        store.reset_collection()

    logger.info("Scanning PDFs in %s", settings.pdf_root)
    documents = discover_pdfs(settings.pdf_root)
    logger.info("Discovered %d PDF file(s)", len(documents))

    logger.info("Extracting text page by page")
    pages = []
    for document in documents:
        extracted = extract_pages(document)
        pages.extend(extracted)
        logger.info("Extracted %d page(s) from %s", len(extracted), document.path)
    logger.info("Extracted %d total page(s)", len(pages))

    logger.info(
        "Chunking text into %d-word chunks with %d-word overlap",
        settings.chunk_size_words,
        settings.chunk_overlap_words,
    )
    chunks = chunk_pages(
        pages,
        chunk_size_words=settings.chunk_size_words,
        overlap_words=settings.chunk_overlap_words,
    )
    logger.info("Created %d chunk(s)", len(chunks))

    if not chunks:
        logger.info("No chunks to index; exiting")
        return

    logger.info("Generating embeddings with %s model %s", settings.embedding_provider, settings.embedding_model)
    embedder = create_embedder(
        provider=settings.embedding_provider,
        ai_mode=settings.ai_mode,
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_timeout_seconds=settings.ollama_timeout_seconds,
    )
    embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
    logger.info("Generated %d embedding(s)", len(embeddings))

    logger.info(
        "Writing chunks to ChromaDB collection %s at %s",
        settings.collection_name,
        settings.chroma_path,
    )
    store.add_chunks(chunks, embeddings)
    logger.info("Ingestion complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index official Swiss procedure PDFs")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="delete and recreate only the configured ChromaDB collection before indexing",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    run(reset=args.reset)


if __name__ == "__main__":
    main()
