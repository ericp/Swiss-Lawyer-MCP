from types import SimpleNamespace
from unittest.mock import MagicMock

from backend.models.chunk import ChunkMetadata
from backend.models.clarification import DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.planner import WorkflowStatus
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile
from backend.planners.prompts import load_workflow_planner_system_prompt
from backend.planners.workflow_planner import NOT_SPECIFIED, WorkflowPlanner


def _generated_answer(
    *,
    insufficient_context: bool = False,
    answer: str = "You can start the procedure using the retrieved official context.",
) -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=answer,
        explanation="Grounded explanation.",
        procedure_steps=["Prepare documents", "Submit application"],
        important_notes=["This is procedural guidance only."],
        cited_sources=[CitedSource(source="driving.pdf", page=1, region="zh")],
        confidence="Medium",
        insufficient_context=insufficient_context,
    )


def _chunk() -> RerankedChunk:
    return RerankedChunk(
        chunk_id="chunk-1",
        text="Official driving licence exchange context.",
        metadata=ChunkMetadata(source="driving.pdf", page=1, region="zh"),
        retrieval_source="vector",
        retrieval_score=0.7,
        rerank_score=2.0,
    )


def _planner_response(content: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_load_workflow_planner_prompt_contains_safeguards() -> None:
    prompt = load_workflow_planner_system_prompt()

    assert "Use only the provided grounded answer and cited evidence" in prompt
    assert "Do not invent steps" in prompt
    assert NOT_SPECIFIED in prompt


def test_workflow_planner_parses_openai_output() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _planner_response(
        """
        {
          "title": "Foreign driving licence exchange in Zurich",
          "summary": "A workflow based on retrieved context.",
          "status": "ready_to_start",
          "steps": [
            {
              "step_number": 1,
              "title": "Confirm residence date",
              "description": "Confirm when Swiss residence started.",
              "responsible_party": "User",
              "required_documents": ["Proof of residence"],
              "estimated_time": "Not specified in retrieved sources.",
              "source_reference": {"source": "driving.pdf", "page": 1, "region": "zh"}
            }
          ],
          "required_documents": ["Proof of residence"],
          "estimated_timelines": ["Not specified in retrieved sources."],
          "potential_blockers": ["Missing residence start date"],
          "next_recommended_action": "Confirm the residence start date.",
          "source_references": [{"source": "driving.pdf", "page": 1, "region": "zh"}],
          "missing_information": []
        }
        """
    )
    planner = WorkflowPlanner(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="planner system",
    )

    plan = planner.create_plan(
        user_question="How do I exchange my licence?",
        detected_intent=DetectedIntent(intent="driving_licence_exchange", confidence=0.9),
        user_profile=UserProfile(driving_licence_country="Italy"),
        generated_answer=_generated_answer(),
        reranked_chunks=[_chunk()],
    )

    assert plan.title == "Foreign driving licence exchange in Zurich"
    assert plan.status is WorkflowStatus.READY_TO_START
    assert plan.steps[0].title == "Confirm residence date"
    assert plan.source_references[0].source == "driving.pdf"
    client.chat.completions.create.assert_called_once()


def test_insufficient_context_returns_needs_more_information_without_openai_call() -> None:
    client = MagicMock()
    planner = WorkflowPlanner(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="planner system",
    )

    plan = planner.create_plan(
        user_question="How do I exchange my licence?",
        detected_intent=DetectedIntent(intent="driving_licence_exchange", confidence=0.9),
        user_profile=UserProfile(),
        generated_answer=_generated_answer(insufficient_context=True),
        reranked_chunks=[],
    )

    assert plan.status is WorkflowStatus.NEEDS_MORE_INFORMATION
    assert plan.required_documents == [NOT_SPECIFIED]
    assert plan.estimated_timelines == [NOT_SPECIFIED]
    assert plan.missing_information == ["Additional official information is required."]
    client.chat.completions.create.assert_not_called()


def test_workflow_planner_applies_not_specified_fallbacks() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _planner_response(
        """
        {
          "title": "Procedure",
          "summary": "Summary",
          "status": "ready_to_start",
          "steps": [],
          "required_documents": [],
          "estimated_timelines": [],
          "potential_blockers": [],
          "next_recommended_action": "Start with official confirmation.",
          "source_references": [],
          "missing_information": []
        }
        """
    )
    planner = WorkflowPlanner(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="planner system",
    )

    plan = planner.create_plan(
        user_question="Question",
        detected_intent=DetectedIntent(intent="immigration", confidence=0.9),
        user_profile=UserProfile(),
        generated_answer=_generated_answer(),
        reranked_chunks=[_chunk()],
    )

    assert plan.required_documents == [NOT_SPECIFIED]
    assert plan.estimated_timelines == [NOT_SPECIFIED]
    assert plan.potential_blockers == [NOT_SPECIFIED]
    assert plan.source_references[0].source == "driving.pdf"


def test_workflow_planner_status_logic_needs_more_information_and_blocked() -> None:
    client = MagicMock()
    client.chat.completions.create.return_value = _planner_response(
        """
        {
          "title": "Procedure",
          "summary": "Summary",
          "status": "ready_to_start",
          "steps": [],
          "required_documents": ["Document"],
          "estimated_timelines": ["Timeline"],
          "potential_blockers": ["Blocker"],
          "next_recommended_action": "Confirm missing information.",
          "source_references": [],
          "missing_information": ["Residence start date"]
        }
        """
    )
    planner = WorkflowPlanner(
        api_key=None,
        model="test-model",
        client=client,
        system_prompt="planner system",
    )

    plan = planner.create_plan(
        user_question="Question",
        detected_intent=DetectedIntent(intent="immigration", confidence=0.9),
        user_profile=UserProfile(),
        generated_answer=_generated_answer(),
        reranked_chunks=[_chunk()],
    )

    assert plan.status is WorkflowStatus.NEEDS_MORE_INFORMATION

    client.chat.completions.create.return_value = _planner_response(
        """
        {
          "title": "Procedure",
          "summary": "Summary",
          "status": "ready_to_start",
          "steps": [],
          "required_documents": ["Document"],
          "estimated_timelines": ["Timeline"],
          "potential_blockers": ["Blocker"],
          "next_recommended_action": "Check eligibility.",
          "source_references": [],
          "missing_information": []
        }
        """
    )

    blocked_plan = planner.create_plan(
        user_question="Question",
        detected_intent=DetectedIntent(intent="immigration", confidence=0.9),
        user_profile=UserProfile(),
        generated_answer=_generated_answer(answer="The user may not currently qualify."),
        reranked_chunks=[_chunk()],
    )

    assert blocked_plan.status is WorkflowStatus.BLOCKED
