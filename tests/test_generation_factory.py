from __future__ import annotations

import pytest

from backend.generation.factory import (
    OpenAIProviderDisabledError,
    create_answer_generator,
    create_workflow_planner,
)
from backend.generation.ollama_client import OllamaChatClient
from backend.utils.config import GenerationSettings


def test_local_answer_generation_uses_ollama_client() -> None:
    generator = create_answer_generator(
        GenerationSettings(ai_mode="local", generation_provider="ollama")
    )

    assert isinstance(generator._client, OllamaChatClient)


def test_local_planner_uses_ollama_client() -> None:
    planner = create_workflow_planner(
        GenerationSettings(ai_mode="local", planner_provider="ollama")
    )

    assert isinstance(planner._client, OllamaChatClient)


def test_local_mode_rejects_openai_generation_provider() -> None:
    with pytest.raises(OpenAIProviderDisabledError):
        create_answer_generator(
            GenerationSettings(ai_mode="local", generation_provider="openai")
        )


def test_local_mode_rejects_openai_planner_provider() -> None:
    with pytest.raises(OpenAIProviderDisabledError):
        create_workflow_planner(
            GenerationSettings(ai_mode="local", planner_provider="openai")
        )
