"""PDF and webpage processing for synchronization."""

from __future__ import annotations

import json
from datetime import timezone
from pathlib import Path
from typing import Protocol

import fitz

from backend.ingestion.chunking import chunk_pages
from backend.models.chunk import Chunk
from backend.models.document import ExtractedPage, PdfDocument
from backend.synchronizer.hashing import sha256_bytes
from backend.synchronizer.html_extraction import extract_webpage
from backend.synchronizer.identifiers import document_id_for_source, synchronized_chunk_id
from backend.synchronizer.models import NormalizedWebDocument
from backend.synchronizer.source_registry import SourceDefinition
from backend.memory.models import utc_now


class DocumentValidationError(Exception):
    """A downloaded document failed validation."""


class EmbedderProtocol(Protocol):
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for texts."""


def validate_pdf_file(path: Path, *, content_type: str | None = None) -> None:
    """Validate PDF signature and PyMuPDF readability."""

    if content_type and "pdf" not in content_type.lower():
        raise DocumentValidationError("Response content type is not PDF")
    with path.open("rb") as file:
        if file.read(5) != b"%PDF-":
            raise DocumentValidationError("File does not have a PDF signature")
    try:
        with fitz.open(path) as document:
            if document.page_count < 1:
                raise DocumentValidationError("PDF contains no pages")
    except Exception as error:
        raise DocumentValidationError("PDF could not be opened") from error


def extract_pdf_pages(path: Path, *, source: SourceDefinition) -> list[ExtractedPage]:
    """Extract pages from a PDF with source metadata."""

    pages: list[ExtractedPage] = []
    with fitz.open(path) as document:
        for index, page in enumerate(document, start=1):
            pages.append(
                ExtractedPage(
                    source=source.local_filename,
                    region=source.region,
                    page=index,
                    text=page.get_text("text"),
                )
            )
    return pages


def chunks_for_pdf(
    path: Path,
    *,
    source: SourceDefinition,
    canonical_url: str,
    content_sha256: str,
    chunk_size_words: int,
    overlap_words: int,
) -> tuple[str, list[Chunk]]:
    """Create provenance-rich chunks for a validated PDF."""

    document_id = document_id_for_source(source.id, canonical_url)
    pages = extract_pdf_pages(path, source=source)
    chunks = chunk_pages(
        pages,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words,
    )
    synchronized_at = utc_now().isoformat()
    enriched: list[Chunk] = []
    for position, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata.model_copy(
            update={
                "document_id": document_id,
                "source_id": source.id,
                "source": source.local_filename,
                "official_url": canonical_url,
                "authority": source.authority,
                "language": source.language,
                "procedure_types": ",".join(source.procedure_types),
                "content_sha256": content_sha256,
                "synchronized_at": synchronized_at,
                "source_type": source.source_type,
            }
        )
        enriched.append(
            Chunk(
                id=synchronized_chunk_id(
                    document_id=document_id,
                    location=f"p{chunk.metadata.page}",
                    position=position,
                    text=chunk.text,
                ),
                text=chunk.text,
                metadata=metadata,
            )
        )
    return document_id, enriched


def process_webpage(
    html: bytes,
    *,
    source: SourceDefinition,
    canonical_url: str,
    documents_root: Path,
    chunk_size_words: int,
    overlap_words: int,
) -> tuple[str, str, list[Chunk], Path]:
    """Normalize, save, and chunk an official webpage."""

    text = html.decode("utf-8", errors="replace")
    extracted = extract_webpage(text)
    if not extracted.content:
        raise DocumentValidationError("Webpage contains no extractable official content")

    document_id = document_id_for_source(source.id, canonical_url)
    retrieved_at = utc_now()
    normalized = NormalizedWebDocument(
        document_id=document_id,
        source_id=source.id,
        title=extracted.title or source.title,
        official_url=canonical_url,
        region=source.region,
        authority=source.authority,
        language=source.language,
        retrieved_at=retrieved_at,
        content_sha256=extracted.content_sha256,
        content=extracted.content,
        sections=extracted.sections,
        metadata=source.metadata,
    )
    output_dir = documents_root / source.region
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source.id}.json"
    output_path.write_text(
        json.dumps(normalized.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    pages = [
        ExtractedPage(
            source=source.local_filename,
            region=source.region,
            page=index,
            text=section,
        )
        for index, section in enumerate(extracted.sections, start=1)
    ]
    base_chunks = chunk_pages(
        pages,
        chunk_size_words=chunk_size_words,
        overlap_words=overlap_words,
    )
    synchronized_at = retrieved_at.astimezone(timezone.utc).isoformat()
    chunks: list[Chunk] = []
    for position, chunk in enumerate(base_chunks, start=1):
        metadata = chunk.metadata.model_copy(
            update={
                "document_id": document_id,
                "source_id": source.id,
                "source": source.local_filename,
                "official_url": canonical_url,
                "authority": source.authority,
                "language": source.language,
                "procedure_types": ",".join(source.procedure_types),
                "section": chunk.metadata.page,
                "content_sha256": extracted.content_sha256,
                "synchronized_at": synchronized_at,
                "source_type": source.source_type,
            }
        )
        chunks.append(
            Chunk(
                id=synchronized_chunk_id(
                    document_id=document_id,
                    location=f"s{chunk.metadata.page}",
                    position=position,
                    text=chunk.text,
                ),
                text=chunk.text,
                metadata=metadata,
            )
        )
    return document_id, extracted.content_sha256, chunks, output_path


def content_hash_for_local_file(path: Path) -> str:
    """Return a content hash for local seed documents."""

    return sha256_bytes(path.read_bytes())
