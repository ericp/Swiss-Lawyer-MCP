"""CLI smoke test for Phase 6 workflow planning."""

from __future__ import annotations

from backend.models.chunk import ChunkMetadata
from backend.models.clarification import DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.planner import ProcedurePlan
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile
from backend.planners.workflow_planner import WorkflowPlanner
from backend.utils.config import load_generation_settings


def main() -> None:
    settings = load_generation_settings()
    question = "How do I exchange my foreign driving licence in Zurich?"
    generated_answer = _example_generated_answer()
    reranked_chunks = _example_reranked_chunks()

    planner = WorkflowPlanner(
        api_key=settings.openai_api_key,
        model=settings.planner_model,
    )
    plan = planner.create_plan(
        user_question=question,
        detected_intent=DetectedIntent(
            intent="driving_licence_exchange",
            confidence=0.9,
            matched_keywords=["driving licence"],
        ),
        user_profile=UserProfile(
            driving_licence_country="Italy",
            intended_canton="Zurich",
        ),
        generated_answer=generated_answer,
        reranked_chunks=reranked_chunks,
    )
    _print_plan(plan)


def _example_generated_answer() -> GeneratedAnswer:
    return GeneratedAnswer(
        answer="You may need to exchange your foreign driving licence after becoming resident in Zurich, based on the retrieved context.",
        explanation="The retrieved context indicates that foreign driving licence exchange depends on the issuing country and Swiss residence details.",
        procedure_steps=[
            "Confirm when Swiss residence started.",
            "Check whether the licence issuing country requires additional checks.",
            "Prepare the documents specified by the responsible cantonal authority.",
        ],
        important_notes=[
            "Exact deadlines must be taken only from retrieved official sources.",
            "This is procedural guidance only and not legal advice.",
        ],
        cited_sources=[
            CitedSource(
                source="driving_licence_exchange_zh.pdf",
                page=1,
                region="zh",
            )
        ],
        confidence="Medium",
        insufficient_context=False,
    )


def _example_reranked_chunks() -> list[RerankedChunk]:
    return [
        RerankedChunk(
            chunk_id="zh:driving_licence_exchange_zh.pdf:p1:c1:example",
            text="Foreign driving licence exchange information for Zurich residents.",
            metadata=ChunkMetadata(
                source="driving_licence_exchange_zh.pdf",
                region="zh",
                page=1,
            ),
            retrieval_source="vector+bm25",
            retrieval_score=0.8,
            rerank_score=2.4,
        )
    ]


def _print_plan(plan: ProcedurePlan) -> None:
    print(f"Title: {plan.title}")
    print(f"Status: {plan.status.value}")
    print(f"Summary: {plan.summary}")

    print("\nSteps")
    for step in plan.steps:
        print(f"{step.step_number}. {step.title}")
        print(f"   {step.description}")
        print(f"   Responsible party: {step.responsible_party}")
        print(f"   Estimated time: {step.estimated_time}")

    print("\nRequired documents")
    for document in plan.required_documents:
        print(f"- {document}")

    print("\nTimelines")
    for timeline in plan.estimated_timelines:
        print(f"- {timeline}")

    print("\nPotential blockers")
    for blocker in plan.potential_blockers:
        print(f"- {blocker}")

    print(f"\nNext action: {plan.next_recommended_action}")


if __name__ == "__main__":
    main()
