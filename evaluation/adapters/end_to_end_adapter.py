"""Evaluation adapter for the Phase 8 procedure orchestrator."""

from __future__ import annotations

from typing import Any

from backend.orchestration.models import ProcedureQueryRequest
from evaluation.adapters.common import normalize, timed
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class EndToEndEvaluationAdapter:
    """Run an isolated end-to-end procedure query."""

    def __init__(self, *, orchestrator: Any | None = None) -> None:
        self._orchestrator = orchestrator

    def evaluate(self, case: EvaluationCase) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        if self._orchestrator is None:
            return EvaluationCaseResult(
                case_id=case.id,
                question=case.question,
                execution_status=EvaluationStatus.SKIPPED,
                error="No isolated orchestrator was provided.",
                timings=timings,
            )
        with timed("end_to_end", timings):
            response = self._orchestrator.handle_query(
                ProcedureQueryRequest(
                    question=case.question,
                    profile_updates=case.user_profile,
                    confirmed_profile_fields=list(case.user_profile),
                    retrieval_top_k=None,
                    rerank_top_k=None,
                )
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            detected_intent=response.intent,
            clarification_result={
                "needs_clarification": response.needs_clarification,
                "missing_fields": response.missing_fields,
                "questions": normalize(response.clarification_questions),
            },
            generated_answer=normalize(response.answer),
            procedure_plan=normalize(response.plan),
            sources=normalize(response.sources),
            timings=timings,
            intermediate_outputs={"orchestrator_response": normalize(response)},
        )
