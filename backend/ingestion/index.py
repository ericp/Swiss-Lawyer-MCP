"""CLI entrypoint for the Phase 1 PDF ingestion pipeline."""

from __future__ import annotations

import logging

from backend.ingestion.chunking import chunk_pages
from backend.ingestion.discovery import discover_pdfs
from backend.ingestion.embeddings import OpenAIEmbedder
from backend.ingestion.extraction import extract_pages
from backend.ingestion.vector_store import ChromaChunkStore
from backend.utils.config import load_ingestion_settings

logger = logging.getLogger(__name__)


def run() -> None:
    """Run PDF discovery, extraction, chunking, embedding, and storage."""

    settings = load_ingestion_settings()

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

    logger.info(
        "Generating embeddings with model %s",
        settings.embedding_model,
    )
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    embeddings = embedder.embed_texts([chunk.text for chunk in chunks])
    logger.info("Generated %d embedding(s)", len(embeddings))

    logger.info(
        "Writing chunks to ChromaDB collection %s at %s",
        settings.collection_name,
        settings.chroma_path,
    )
    store = ChromaChunkStore(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
    )
    store.add_chunks(chunks, embeddings)
    logger.info("Ingestion complete")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    run()


if __name__ == "__main__":
    main()
