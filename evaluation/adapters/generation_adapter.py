"""Evaluation adapter for grounded answer generation."""

from __future__ import annotations

from typing import Any

from backend.models.clarification import DetectedIntent
from backend.models.user_profile import UserProfile
from evaluation.adapters.common import normalize, timed
from evaluation.config import ExecutionMode
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class GenerationEvaluationAdapter:
    """Run grounded generation or return offline precomputed answers."""

    def __init__(
        self,
        *,
        answer_generator: Any | None = None,
        execution_mode: ExecutionMode = ExecutionMode.OFFLINE,
    ) -> None:
        self._answer_generator = answer_generator
        self._execution_mode = execution_mode

    def evaluate(
        self,
        case: EvaluationCase,
        *,
        detected_intent: DetectedIntent | None = None,
        reranked_chunks: list[Any] | None = None,
    ) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        if self._execution_mode is ExecutionMode.OFFLINE:
            return EvaluationCaseResult(
                case_id=case.id,
                question=case.question,
                execution_status=EvaluationStatus.PASSED,
                generated_answer=case.offline_outputs.get("generated_answer"),
                sources=case.offline_outputs.get("sources", []),
                timings=timings,
                intermediate_outputs={"generation_mode": "offline"},
            )
        with timed("generation", timings):
            answer = self._answer_generator.generate(
                user_question=case.question,
                detected_intent=detected_intent
                or DetectedIntent(intent=case.expected_intent or "immigration", confidence=0.0),
                user_profile=UserProfile.model_validate(case.user_profile),
                reranked_chunks=reranked_chunks or [],
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            generated_answer=normalize(answer),
            sources=normalize(answer.cited_sources),
            timings=timings,
        )
