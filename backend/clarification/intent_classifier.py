"""Rule-based intent classification for Swiss procedure questions."""

from __future__ import annotations

from backend.clarification.procedure_schemas import list_procedure_schemas
from backend.models.clarification import DetectedIntent

DEFAULT_INTENT = "Immigration"


class IntentClassifier:
    """Classify a user question into a supported procedure intent."""

    def classify(self, question: str) -> DetectedIntent:
        """Classify intent using procedure schema keywords."""

        normalized_question = question.lower()
        best_intent = DEFAULT_INTENT
        best_matches: list[str] = []

        for schema in list_procedure_schemas():
            matches = [
                keyword
                for keyword in schema.intent_keywords
                if keyword in normalized_question
            ]
            if len(matches) > len(best_matches):
                best_intent = schema.intent
                best_matches = matches

        if best_matches:
            confidence = min(1.0, 0.45 + (0.15 * len(best_matches)))
        else:
            confidence = 0.25

        return DetectedIntent(
            intent=best_intent,
            confidence=confidence,
            matched_keywords=best_matches,
        )
