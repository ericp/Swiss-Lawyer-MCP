"""Configuration helpers for ingestion, retrieval, and generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IngestionSettings:
    """Runtime settings for the Phase 1 ingestion pipeline."""

    pdf_root: Path = Path("data/pdfs")
    chroma_path: Path = Path("data/chromadb")
    collection_name: str = "swiss_procedures"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None
    chunk_size_words: int = 600
    chunk_overlap_words: int = 100


def load_ingestion_settings() -> IngestionSettings:
    """Load ingestion settings from environment variables."""

    return IngestionSettings(
        pdf_root=Path(os.getenv("PDF_ROOT", "data/pdfs")),
        chroma_path=Path(os.getenv("CHROMA_PATH", "data/chromadb")),
        collection_name=os.getenv("CHROMA_COLLECTION", "swiss_procedures"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        chunk_size_words=int(os.getenv("CHUNK_SIZE_WORDS", "600")),
        chunk_overlap_words=int(os.getenv("CHUNK_OVERLAP_WORDS", "100")),
    )


@dataclass(frozen=True)
class RetrievalSettings:
    """Runtime settings for the Phase 2 and Phase 3 retrieval pipeline."""

    chroma_path: Path = Path("data/chromadb")
    collection_name: str = "swiss_procedures"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None
    top_k: int = 10
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_top_k: int = 5


def load_retrieval_settings() -> RetrievalSettings:
    """Load retrieval settings from environment variables."""

    return RetrievalSettings(
        chroma_path=Path(os.getenv("CHROMA_PATH", "data/chromadb")),
        collection_name=os.getenv("CHROMA_COLLECTION", "swiss_procedures"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        top_k=int(os.getenv("RETRIEVAL_TOP_K", "10")),
        rerank_model=os.getenv(
            "RERANK_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        ),
        rerank_top_k=int(os.getenv("RERANK_TOP_K", "5")),
    )


@dataclass(frozen=True)
class GenerationSettings:
    """Runtime settings for Phase 5 generation and Phase 6 planning."""

    openai_api_key: str | None = None
    model: str = "gpt-4o-mini"
    planner_model: str = "gpt-4o-mini"


def load_generation_settings() -> GenerationSettings:
    """Load generation settings from environment variables."""

    return GenerationSettings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("OPENAI_GENERATION_MODEL", "gpt-4o-mini"),
        planner_model=os.getenv("OPENAI_PLANNER_MODEL", "gpt-4o-mini"),
    )


@dataclass(frozen=True)
class APISettings:
    """Runtime settings for the Phase 8 FastAPI application."""

    host: str = "127.0.0.1"
    port: int = 8000
    sqlite_database_url: str = "sqlite:///data/sqlite/memory.db"
    request_timeout_seconds: int = 60
    log_level: str = "INFO"


def load_api_settings() -> APISettings:
    """Load API settings from environment variables."""

    return APISettings(
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
        sqlite_database_url=os.getenv(
            "SQLITE_DATABASE_URL",
            "sqlite:///data/sqlite/memory.db",
        ),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "60")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
