from __future__ import annotations

import backend.utils.config as config
from backend.utils.config import (
    collection_name_for_embedding,
)


def test_model_specific_collection_name_is_sanitized() -> None:
    assert (
        collection_name_for_embedding(
            base_name="Swiss Lawyer",
            provider="ollama",
            model="nomic-embed-text:latest",
        )
        == "swiss_lawyer__ollama__nomic_embed_text_latest"
    )


def test_local_mode_defaults_select_ollama(monkeypatch) -> None:
    monkeypatch.setattr(config, "load_project_env", lambda: None)
    for name in [
        "AI_MODE",
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "GENERATION_PROVIDER",
        "GENERATION_MODEL",
        "PLANNER_PROVIDER",
        "PLANNER_MODEL",
        "CHROMA_COLLECTION",
        "OPENAI_API_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)

    ingestion = config.load_ingestion_settings()
    retrieval = config.load_retrieval_settings()
    generation = config.load_generation_settings()

    assert ingestion.ai_mode == "local"
    assert ingestion.embedding_provider == "ollama"
    assert ingestion.embedding_model == "nomic-embed-text"
    assert ingestion.collection_name == "swiss_lawyer__ollama__nomic_embed_text"
    assert retrieval.reranker_provider == "disabled"
    assert generation.generation_provider == "ollama"
    assert generation.model == "llama3.2"
