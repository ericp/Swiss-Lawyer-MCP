"""Configuration helpers for ingestion, retrieval, and generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_project_env() -> None:
    """Load the repository-root .env file when python-dotenv is installed."""

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


def collection_name_for_embedding(
    *,
    base_name: str,
    provider: str,
    model: str,
) -> str:
    """Return a model-specific Chroma collection name."""

    return "__".join(
        [
            _sanitize_collection_part(base_name),
            _sanitize_collection_part(provider),
            _sanitize_collection_part(model),
        ]
    )


def _sanitize_collection_part(value: str) -> str:
    sanitized = "".join(character if character.isalnum() else "_" for character in value.lower())
    sanitized = "_".join(part for part in sanitized.split("_") if part)
    return sanitized or "default"


def _ai_mode() -> str:
    return os.getenv("AI_MODE", "local").strip().lower()


def _embedding_provider() -> str:
    return os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()


def _generation_provider() -> str:
    return os.getenv("GENERATION_PROVIDER", "ollama").strip().lower()


def _planner_provider() -> str:
    return os.getenv("PLANNER_PROVIDER", _generation_provider()).strip().lower()


def _embedding_model() -> str:
    return os.getenv(
        "EMBEDDING_MODEL",
        os.getenv("OPENAI_EMBEDDING_MODEL", "nomic-embed-text"),
    )


def _collection_name() -> str:
    explicit = os.getenv("CHROMA_COLLECTION")
    if explicit:
        return explicit
    return collection_name_for_embedding(
        base_name=os.getenv("CHROMA_COLLECTION_BASE", "swiss_lawyer"),
        provider=_embedding_provider(),
        model=_embedding_model(),
    )


@dataclass(frozen=True)
class IngestionSettings:
    """Runtime settings for the Phase 1 ingestion pipeline."""

    pdf_root: Path = Path("data/pdfs")
    chroma_path: Path = Path("data/chromadb")
    collection_name: str = "swiss_lawyer__ollama__nomic_embed_text"
    ai_mode: str = "local"
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 180.0
    chunk_size_words: int = 600
    chunk_overlap_words: int = 100


def load_ingestion_settings() -> IngestionSettings:
    """Load ingestion settings from environment variables."""

    load_project_env()
    return IngestionSettings(
        pdf_root=Path(os.getenv("PDF_ROOT", "data/pdfs")),
        chroma_path=Path(os.getenv("CHROMA_PATH", "data/chromadb")),
        collection_name=_collection_name(),
        ai_mode=_ai_mode(),
        embedding_provider=_embedding_provider(),
        embedding_model=_embedding_model(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
        chunk_size_words=int(os.getenv("CHUNK_SIZE_WORDS", "600")),
        chunk_overlap_words=int(os.getenv("CHUNK_OVERLAP_WORDS", "100")),
    )


@dataclass(frozen=True)
class RetrievalSettings:
    """Runtime settings for the Phase 2 and Phase 3 retrieval pipeline."""

    chroma_path: Path = Path("data/chromadb")
    collection_name: str = "swiss_lawyer__ollama__nomic_embed_text"
    ai_mode: str = "local"
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 180.0
    top_k: int = 10
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_provider: str = "disabled"
    rerank_top_k: int = 5


def load_retrieval_settings() -> RetrievalSettings:
    """Load retrieval settings from environment variables."""

    load_project_env()
    return RetrievalSettings(
        chroma_path=Path(os.getenv("CHROMA_PATH", "data/chromadb")),
        collection_name=_collection_name(),
        ai_mode=_ai_mode(),
        embedding_provider=_embedding_provider(),
        embedding_model=_embedding_model(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
        top_k=int(os.getenv("RETRIEVAL_TOP_K", "10")),
        rerank_model=os.getenv(
            "RERANK_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2",
        ),
        reranker_provider=os.getenv("RERANKER_PROVIDER", "disabled").strip().lower(),
        rerank_top_k=int(os.getenv("RERANK_TOP_K", "5")),
    )


@dataclass(frozen=True)
class GenerationSettings:
    """Runtime settings for Phase 5 generation and Phase 6 planning."""

    ai_mode: str = "local"
    generation_provider: str = "ollama"
    planner_provider: str = "ollama"
    openai_api_key: str | None = None
    model: str = "llama3.2"
    planner_model: str = "llama3.2"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 180.0


def load_generation_settings() -> GenerationSettings:
    """Load generation settings from environment variables."""

    load_project_env()
    return GenerationSettings(
        ai_mode=_ai_mode(),
        generation_provider=_generation_provider(),
        planner_provider=_planner_provider(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("GENERATION_MODEL", os.getenv("OPENAI_GENERATION_MODEL", "llama3.2")),
        planner_model=os.getenv("PLANNER_MODEL", os.getenv("OPENAI_PLANNER_MODEL", "llama3.2")),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
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

    load_project_env()
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
    collection_name: str = "swiss_lawyer__ollama__nomic_embed_text"
    ai_mode: str = "local"
    embedding_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    openai_api_key: str | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_timeout_seconds: float = 180.0
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

    load_project_env()
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
        collection_name=_collection_name(),
        ai_mode=_ai_mode(),
        embedding_provider=_embedding_provider(),
        embedding_model=_embedding_model(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180")),
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
