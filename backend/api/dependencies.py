"""FastAPI dependency construction for Phase 8."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from sqlalchemy import Engine, text

from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.generation.answer_generator import GroundedAnswerGenerator
from backend.ingestion.embeddings import OpenAIEmbedder
from backend.location.canton_resolver import CantonResolver
from backend.memory.database import (
    create_memory_engine,
    create_session_factory,
)
from backend.memory.memory_service import MemoryService
from backend.orchestration.procedure_orchestrator import ProcedureOrchestrator
from backend.planners.workflow_planner import WorkflowPlanner
from backend.reranking.reranker import CrossEncoderReranker
from backend.retrieval.bm25 import BM25Retriever
from backend.retrieval.hybrid import HybridRetriever
from backend.retrieval.vector import VectorRetriever
from backend.utils.config import (
    APISettings,
    GenerationSettings,
    RetrievalSettings,
    load_api_settings,
    load_generation_settings,
    load_retrieval_settings,
)


@lru_cache
def get_api_settings() -> APISettings:
    """Return cached API settings."""

    return load_api_settings()


@lru_cache
def get_retrieval_settings() -> RetrievalSettings:
    """Return cached retrieval settings."""

    return load_retrieval_settings()


@lru_cache
def get_generation_settings() -> GenerationSettings:
    """Return cached generation settings."""

    return load_generation_settings()


@lru_cache
def get_memory_engine() -> Engine:
    """Return a reusable SQLAlchemy engine."""

    return create_memory_engine(get_api_settings().sqlite_database_url)


@lru_cache
def get_session_factory() -> Any:
    """Return a reusable SQLAlchemy session factory."""

    return create_session_factory(get_memory_engine())


def get_memory_service() -> MemoryService:
    """Return the memory service for request handlers."""

    return MemoryService(session_factory=get_session_factory())


@lru_cache
def get_intent_classifier() -> IntentClassifier:
    return IntentClassifier()


@lru_cache
def get_clarification_engine() -> ClarificationEngine:
    return ClarificationEngine()


@lru_cache
def get_canton_resolver() -> CantonResolver:
    return CantonResolver()


@lru_cache
def get_hybrid_retriever() -> HybridRetriever:
    settings = get_retrieval_settings()
    embedder = OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )
    vector = VectorRetriever(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
        embedder=embedder,
    )
    bm25 = BM25Retriever(
        path=settings.chroma_path,
        collection_name=settings.collection_name,
    )
    return HybridRetriever(vector_retriever=vector, bm25_retriever=bm25)


@lru_cache
def get_reranker() -> CrossEncoderReranker:
    return CrossEncoderReranker(model_name=get_retrieval_settings().rerank_model)


@lru_cache
def get_answer_generator() -> GroundedAnswerGenerator:
    settings = get_generation_settings()
    return GroundedAnswerGenerator(
        api_key=settings.openai_api_key,
        model=settings.model,
    )


@lru_cache
def get_workflow_planner() -> WorkflowPlanner:
    settings = get_generation_settings()
    return WorkflowPlanner(
        api_key=settings.openai_api_key,
        model=settings.planner_model,
    )


def get_orchestrator() -> ProcedureOrchestrator:
    retrieval_settings = get_retrieval_settings()
    return ProcedureOrchestrator(
        memory_service=get_memory_service(),
        intent_classifier=get_intent_classifier(),
        clarification_engine=get_clarification_engine(),
        hybrid_retriever=get_hybrid_retriever(),
        reranker=get_reranker(),
        answer_generator=get_answer_generator(),
        workflow_planner=get_workflow_planner(),
        canton_resolver=get_canton_resolver(),
        default_retrieval_top_k=retrieval_settings.top_k,
        default_rerank_top_k=retrieval_settings.rerank_top_k,
    )


def check_health_components() -> dict[str, str]:
    """Check runtime dependencies without exposing secret values."""

    components = {
        "application": "healthy",
        "sqlite": "healthy",
        "chromadb": "healthy",
        "openai_configuration": "available",
    }
    try:
        with get_memory_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        components["sqlite"] = "unhealthy"

    try:
        settings = get_retrieval_settings()
        chromadb.PersistentClient(path=str(Path(settings.chroma_path))).heartbeat()
    except Exception:
        components["chromadb"] = "unhealthy"

    if not os.getenv("OPENAI_API_KEY"):
        components["openai_configuration"] = "missing"

    return components
