from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.generation.answer_generator import (
    INSUFFICIENT_CONTEXT_MESSAGE,
    GroundedAnswerGenerator,
)
from backend.generation.confidence import estimate_confidence
from backend.models.chunk import ChunkMetadata
from backend.models.clarification import DetectedIntent
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile


def _chunk(
    chunk_id: str,
    *,
    source: str = "work.pdf",
    page: int = 1,
    rerank_score: float = 2.5,
) -> RerankedChunk:
    return RerankedChunk(
        chunk_id=chunk_id,
        text=f"Official context for {chunk_id}",
        metadata=ChunkMetadata(source=source, region="federal", page=page),
        retrieval_source="vector+bm25",
        retrieval_score=0.8,
        rerank_score=rerank_score,
    )


def test_empty_context_returns_insufficient_context_without_openai_call() -> None:
    client = MagicMock()
    generator = GroundedAnswerGenerator(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="system",
    )

    answer = generator.generate(
        user_question="Can I work?",
        detected_intent=DetectedIntent(intent="work_permit", confidence=0.8),
        user_profile=UserProfile(nationality="Brazil"),
        reranked_chunks=[],
    )

    assert answer.insufficient_context is True
    assert answer.answer == INSUFFICIENT_CONTEXT_MESSAGE
    assert answer.confidence == "Low"
    assert answer.cited_sources == []
    client.chat.completions.create.assert_not_called()


def test_generator_parses_openai_json_and_enforces_required_citations() -> None:
    client = MagicMock()
    response_content = """
    {
      "answer": "A Brazilian citizen may need authorization before working.",
      "explanation": "The supplied context discusses work authorization.",
      "procedure_steps": ["Check permit route", "Contact the competent authority"],
      "important_notes": ["This is procedural guidance only."],
      "cited_sources": [],
      "insufficient_context": false
    }
    """
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_content))]
    )
    chunks = [
        _chunk("chunk-1", source="work.pdf", page=1, rerank_score=2.4),
        _chunk("chunk-2", source="permit.pdf", page=3, rerank_score=2.2),
        _chunk("chunk-3", source="permit.pdf", page=4, rerank_score=2.1),
    ]
    generator = GroundedAnswerGenerator(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="system prompt",
    )

    answer = generator.generate(
        user_question="Can a Brazilian citizen work in Switzerland?",
        detected_intent=DetectedIntent(intent="work_permit", confidence=0.8),
        user_profile=UserProfile(
            nationality="Brazil",
            employment_status="Swiss job offer",
            purpose_of_stay="work",
            intended_canton="Zurich",
        ),
        reranked_chunks=chunks,
    )

    assert answer.insufficient_context is False
    assert answer.confidence == "High"
    assert [source.source for source in answer.cited_sources] == [
        "work.pdf",
        "permit.pdf",
        "permit.pdf",
    ]
    client.chat.completions.create.assert_called_once()
    call_kwargs = client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert "Official retrieved context" in call_kwargs["messages"][1]["content"]


def test_generator_filters_invented_sources_and_enforces_insufficient_message() -> None:
    client = MagicMock()
    response_content = """
    {
      "answer": "Speculative answer that should be replaced.",
      "explanation": "Speculative explanation that should be replaced.",
      "procedure_steps": ["Invented step"],
      "important_notes": ["More official information is needed."],
      "cited_sources": [
        {"source": "invented.pdf", "page": 99, "region": "federal"}
      ],
      "insufficient_context": true
    }
    """
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=response_content))]
    )
    generator = GroundedAnswerGenerator(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="system prompt",
    )

    answer = generator.generate(
        user_question="Can I work?",
        detected_intent=DetectedIntent(intent="work_permit", confidence=0.8),
        user_profile=UserProfile(nationality="Brazil"),
        reranked_chunks=[_chunk("chunk-1", source="work.pdf", page=1)],
    )

    assert answer.insufficient_context is True
    assert answer.answer == INSUFFICIENT_CONTEXT_MESSAGE
    assert answer.explanation == INSUFFICIENT_CONTEXT_MESSAGE
    assert answer.procedure_steps == []
    assert [source.source for source in answer.cited_sources] == ["work.pdf"]


def test_estimate_confidence_uses_retrieval_quality_signals() -> None:
    assert estimate_confidence([]) == "Low"
    assert estimate_confidence([_chunk("chunk-1", rerank_score=0.3)]) == "Low"
    assert (
        estimate_confidence(
            [_chunk("chunk-1", rerank_score=0.8), _chunk("chunk-2", rerank_score=0.7)]
        )
        == "Medium"
    )
    assert (
        estimate_confidence(
            [
                _chunk("chunk-1", source="a.pdf", rerank_score=2.1),
                _chunk("chunk-2", source="b.pdf", rerank_score=2.2),
                _chunk("chunk-3", source="b.pdf", rerank_score=2.4),
            ]
        )
        == "High"
    )
