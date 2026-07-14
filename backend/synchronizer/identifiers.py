"""Stable document and chunk identifiers."""

from __future__ import annotations

import hashlib


def document_id_for_source(source_id: str, canonical_url: str) -> str:
    """Create a stable document id from source id and canonical URL."""

    digest = hashlib.sha256(f"{source_id}|{canonical_url}".encode("utf-8")).hexdigest()[:16]
    return f"doc:{source_id}:{digest}"


def synchronized_chunk_id(
    *,
    document_id: str,
    location: str,
    position: int,
    text: str,
) -> str:
    """Create a stable chunk id containing a content hash."""

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"{document_id}:{location}:c{position}:{digest}"
