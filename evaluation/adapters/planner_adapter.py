"""Evaluation adapter for procedure planning."""

from __future__ import annotations

from typing import Any

from backend.models.clarification import DetectedIntent
from backend.models.user_profile import UserProfile
from evaluation.adapters.common import normalize, timed
from evaluation.config import ExecutionMode
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class PlannerEvaluationAdapter:
    """Run planner or return offline precomputed plans."""

    def __init__(
        self,
        *,
        workflow_planner: Any | None = None,
        execution_mode: ExecutionMode = ExecutionMode.OFFLINE,
    ) -> None:
        self._workflow_planner = workflow_planner
        self._execution_mode = execution_mode

    def evaluate(
        self,
        case: EvaluationCase,
        *,
        generated_answer: Any | None = None,
        detected_intent: DetectedIntent | None = None,
        reranked_chunks: list[Any] | None = None,
    ) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        if self._execution_mode is ExecutionMode.OFFLINE:
            return EvaluationCaseResult(
                case_id=case.id,
                question=case.question,
                execution_status=EvaluationStatus.PASSED,
                procedure_plan=case.offline_outputs.get("procedure_plan"),
                timings=timings,
                intermediate_outputs={"planner_mode": "offline"},
            )
        with timed("planner", timings):
            plan = self._workflow_planner.create_plan(
                user_question=case.question,
                detected_intent=detected_intent
                or DetectedIntent(intent=case.expected_intent or "immigration", confidence=0.0),
                user_profile=UserProfile.model_validate(case.user_profile),
                generated_answer=generated_answer,
                reranked_chunks=reranked_chunks or [],
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            procedure_plan=normalize(plan),
            timings=timings,
        )
