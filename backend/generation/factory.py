"""Provider factories for grounded generation and workflow planning."""

from __future__ import annotations

from backend.generation.answer_generator import GroundedAnswerGenerator
from backend.generation.ollama_client import OllamaChatClient
from backend.planners.workflow_planner import WorkflowPlanner
from backend.utils.config import GenerationSettings


class GenerationConfigurationError(RuntimeError):
    """Raised when generation provider settings are invalid."""


class OpenAIProviderDisabledError(GenerationConfigurationError):
    """Raised when OpenAI is requested while local mode is active."""


def create_answer_generator(settings: GenerationSettings) -> GroundedAnswerGenerator:
    """Create the configured grounded answer generator."""

    provider = settings.generation_provider.strip().lower()
    _guard_openai(provider=provider, ai_mode=settings.ai_mode)
    if provider == "ollama":
        return GroundedAnswerGenerator(
            api_key=None,
            model=settings.model,
            client=OllamaChatClient(
                base_url=settings.ollama_base_url,
                timeout_seconds=settings.ollama_timeout_seconds,
            ),
        )
    if provider == "openai":
        return GroundedAnswerGenerator(
            api_key=settings.openai_api_key,
            model=settings.model,
        )
    raise GenerationConfigurationError(f"Unknown generation provider: {provider}")


def create_workflow_planner(settings: GenerationSettings) -> WorkflowPlanner:
    """Create the configured workflow planner."""

    provider = settings.planner_provider.strip().lower()
    _guard_openai(provider=provider, ai_mode=settings.ai_mode)
    if provider == "ollama":
        return WorkflowPlanner(
            api_key=None,
            model=settings.planner_model,
            client=OllamaChatClient(
                base_url=settings.ollama_base_url,
                timeout_seconds=settings.ollama_timeout_seconds,
            ),
        )
    if provider == "openai":
        return WorkflowPlanner(
            api_key=settings.openai_api_key,
            model=settings.planner_model,
        )
    raise GenerationConfigurationError(f"Unknown planner provider: {provider}")


def _guard_openai(*, provider: str, ai_mode: str) -> None:
    if ai_mode.strip().lower() == "local" and provider == "openai":
        raise OpenAIProviderDisabledError("OpenAI provider was requested while AI_MODE=local.")
