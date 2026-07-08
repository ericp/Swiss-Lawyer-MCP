"""Pydantic models for discovered PDFs and extracted pages."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class PdfDocument(BaseModel):
    """A PDF discovered below the configured PDF root."""

    path: Path
    source: str = Field(min_length=1)
    region: str = Field(min_length=1)


class ExtractedPage(BaseModel):
    """Text extracted from one PDF page."""

    source: str = Field(min_length=1)
    region: str = Field(min_length=1)
    page: int = Field(ge=1)
    text: str
