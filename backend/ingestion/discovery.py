"""PDF discovery for the ingestion pipeline."""

from __future__ import annotations

from pathlib import Path

from backend.models.document import PdfDocument


def discover_pdfs(pdf_root: Path) -> list[PdfDocument]:
    """Recursively discover PDF files and infer region from parent folder."""

    if not pdf_root.exists():
        return []

    documents: list[PdfDocument] = []
    for path in sorted(pdf_root.rglob("*.pdf")):
        if path.is_file():
            documents.append(
                PdfDocument(
                    path=path,
                    source=path.name,
                    region=path.parent.name,
                )
            )
    return documents
