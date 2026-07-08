"""Word-based chunking for extracted PDF pages."""

from __future__ import annotations

import hashlib

from backend.models.chunk import Chunk, ChunkMetadata
from backend.models.document import ExtractedPage


def chunk_pages(
    pages: list[ExtractedPage],
    *,
    chunk_size_words: int = 600,
    overlap_words: int = 100,
) -> list[Chunk]:
    """Split extracted pages into overlapping word chunks."""

    if chunk_size_words <= 0:
        raise ValueError("chunk_size_words must be greater than zero")
    if overlap_words < 0:
        raise ValueError("overlap_words must be zero or greater")
    if overlap_words >= chunk_size_words:
        raise ValueError("overlap_words must be smaller than chunk_size_words")

    chunks: list[Chunk] = []
    for page in pages:
        words = page.text.split()
        if not words:
            continue

        step = chunk_size_words - overlap_words
        chunk_number = 0
        for start in range(0, len(words), step):
            chunk_words = words[start : start + chunk_size_words]
            if not chunk_words:
                continue

            chunk_number += 1
            text = " ".join(chunk_words)
            chunks.append(
                Chunk(
                    id=_chunk_id(page.source, page.region, page.page, chunk_number, text),
                    text=text,
                    metadata=ChunkMetadata(
                        source=page.source,
                        region=page.region,
                        page=page.page,
                    ),
                )
            )

            if start + chunk_size_words >= len(words):
                break

    return chunks


def _chunk_id(source: str, region: str, page: int, chunk_number: int, text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    safe_source = source.replace("/", "_")
    return f"{region}:{safe_source}:p{page}:c{chunk_number}:{digest}"
