"""Clarification engine for missing material procedure information."""

from __future__ import annotations

from backend.clarification.procedure_schemas import ProcedureSchema, get_procedure_schema
from backend.models.clarification import (
    ClarificationQuestion,
    ClarificationResult,
    DetectedIntent,
)
from backend.models.user_profile import UserProfile


class ClarificationEngine:
    """Generate clarification questions for missing required fields."""

    def evaluate(
        self,
        *,
        user_question: str,
        detected_intent: DetectedIntent,
        user_profile: UserProfile,
    ) -> ClarificationResult:
        """Return whether clarification is needed before retrieval."""

        schema = get_procedure_schema(detected_intent.intent)
        if schema is None:
            return ClarificationResult(
                intent=detected_intent,
                needs_clarification=False,
                missing_fields=[],
                clarification_questions=[],
                known_fields=_known_profile_fields(user_profile),
            )

        known_fields = _known_profile_fields(user_profile)
        missing_fields = _missing_required_fields(schema, user_profile)
        questions = [
            ClarificationQuestion(
                field=field,
                question=schema.clarification_questions[field],
            )
            for field in missing_fields
            if field in schema.clarification_questions
        ]

        return ClarificationResult(
            intent=detected_intent,
            needs_clarification=bool(questions),
            missing_fields=missing_fields,
            clarification_questions=questions,
            known_fields=known_fields,
        )


def _missing_required_fields(
    schema: ProcedureSchema,
    user_profile: UserProfile,
) -> list[str]:
    return [
        field
        for field in schema.required_fields
        if _is_missing(getattr(user_profile, field, None))
    ]


def _known_profile_fields(user_profile: UserProfile) -> dict[str, str]:
    return {
        field: str(value)
        for field, value in user_profile.model_dump().items()
        if not _is_missing(value)
    }


def _is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False
