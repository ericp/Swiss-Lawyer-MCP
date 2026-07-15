"""Evaluation adapter for intent classification and clarification."""

from __future__ import annotations

from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.models.user_profile import UserProfile
from evaluation.adapters.common import normalize, timed
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class ClarificationEvaluationAdapter:
    """Run production intent classification and clarification for a case."""

    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier | None = None,
        clarification_engine: ClarificationEngine | None = None,
    ) -> None:
        self._intent_classifier = intent_classifier or IntentClassifier()
        self._clarification_engine = clarification_engine or ClarificationEngine()

    def evaluate(self, case: EvaluationCase) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        with timed("clarification", timings):
            profile = UserProfile.model_validate(case.user_profile)
            detected_intent = self._intent_classifier.classify(case.question)
            clarification_result = self._clarification_engine.evaluate(
                user_question=case.question,
                detected_intent=detected_intent,
                user_profile=profile,
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            detected_intent=normalize(detected_intent),
            clarification_result=normalize(clarification_result),
            timings=timings,
            intermediate_outputs={
                "known_profile": profile.model_dump(mode="json", exclude_none=True),
                "missing_fields": clarification_result.missing_fields,
                "clarification_questions": [
                    question.question
                    for question in clarification_result.clarification_questions
                ],
            },
        )
