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
    enable_sync_admin_endpoints: bool = False


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
        enable_sync_admin_endpoints=_env_bool("ENABLE_SYNC_ADMIN_ENDPOINTS", False),
    )


@dataclass(frozen=True)
class SynchronizerSettings:
    """Runtime settings for Phase 9 source synchronization."""

    source_registry_path: Path = Path("data/pdfs/metadata/sources.yaml")
    synchronized_pdf_path: Path = Path("data/pdfs")
    synchronized_document_path: Path = Path("data/documents")
    temporary_download_path: Path = Path("data/tmp/synchronizer")
    sqlite_database_url: str = "sqlite:///data/sqlite/memory.db"
    chroma_path: Path = Path("data/chromadb")
    collection_name: str = "swiss_procedures"
    embedding_model: str = "text-embedding-3-small"
    openai_api_key: str | None = None
    http_timeout_seconds: float = 30.0
    max_document_bytes: int = 20_000_000
    retry_count: int = 2
    retry_backoff_seconds: float = 0.25
    user_agent: str = "Swiss Lawyer MCP Synchronizer/0.9"
    retain_unavailable_sources: bool = True
    candidate_discovery_enabled: bool = True
    webpage_min_content_chars: int = 100
    chunk_size_words: int = 600
    chunk_overlap_words: int = 100


def load_synchronizer_settings() -> SynchronizerSettings:
    """Load synchronizer settings from environment variables."""

    return SynchronizerSettings(
        source_registry_path=Path(
            os.getenv("SYNC_SOURCE_REGISTRY_PATH", "data/pdfs/metadata/sources.yaml")
        ),
        synchronized_document_path=Path(
            os.getenv("SYNC_DOCUMENT_PATH", "data/documents")
        ),
        synchronized_pdf_path=Path(os.getenv("SYNC_PDF_PATH", "data/pdfs")),
        temporary_download_path=Path(
            os.getenv("SYNC_TEMP_DOWNLOAD_PATH", "data/tmp/synchronizer")
        ),
        sqlite_database_url=os.getenv(
            "SQLITE_DATABASE_URL",
            "sqlite:///data/sqlite/memory.db",
        ),
        chroma_path=Path(os.getenv("CHROMA_PATH", "data/chromadb")),
        collection_name=os.getenv("CHROMA_COLLECTION", "swiss_procedures"),
        embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        http_timeout_seconds=float(os.getenv("SYNC_HTTP_TIMEOUT_SECONDS", "30")),
        max_document_bytes=int(os.getenv("SYNC_MAX_DOCUMENT_BYTES", "20000000")),
        retry_count=int(os.getenv("SYNC_RETRY_COUNT", "2")),
        retry_backoff_seconds=float(os.getenv("SYNC_RETRY_BACKOFF_SECONDS", "0.25")),
        user_agent=os.getenv(
            "SYNC_USER_AGENT",
            "Swiss Lawyer MCP Synchronizer/0.9",
        ),
        retain_unavailable_sources=_env_bool("SYNC_RETAIN_UNAVAILABLE_SOURCES", True),
        candidate_discovery_enabled=_env_bool("SYNC_CANDIDATE_DISCOVERY_ENABLED", True),
        webpage_min_content_chars=int(os.getenv("SYNC_WEBPAGE_MIN_CONTENT_CHARS", "100")),
        chunk_size_words=int(os.getenv("CHUNK_SIZE_WORDS", "600")),
        chunk_overlap_words=int(os.getenv("CHUNK_OVERLAP_WORDS", "100")),
    )


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
