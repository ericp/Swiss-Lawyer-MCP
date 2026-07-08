"""PDF text extraction using PyMuPDF."""

from __future__ import annotations

import fitz

from backend.models.document import ExtractedPage, PdfDocument


def extract_pages(document: PdfDocument) -> list[ExtractedPage]:
    """Extract text from each page of a PDF while preserving page metadata."""

    pages: list[ExtractedPage] = []
    with fitz.open(document.path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            pages.append(
                ExtractedPage(
                    source=document.source,
                    region=document.region,
                    page=page_index,
                    text=page.get_text("text").strip(),
                )
            )
    return pages
