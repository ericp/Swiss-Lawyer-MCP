"""CLI smoke test for Phase 4 clarification."""

from __future__ import annotations

import argparse
import json

from pydantic import ValidationError

from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.models.user_profile import UserProfile


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Classify intent and decide whether clarification is required."
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="Can I move to Switzerland as a Brazilian citizen?",
    )
    parser.add_argument(
        "--profile-json",
        default='{"nationality": "Brazil"}',
        help="Known user profile as JSON.",
    )
    args = parser.parse_args()

    try:
        profile = UserProfile.model_validate(json.loads(args.profile_json))
    except (json.JSONDecodeError, ValidationError) as error:
        raise SystemExit(f"Invalid --profile-json: {error}") from error

    classifier = IntentClassifier()
    engine = ClarificationEngine()
    detected_intent = classifier.classify(args.question)
    result = engine.evaluate(
        user_question=args.question,
        detected_intent=detected_intent,
        user_profile=profile,
    )

    print(f"Question: {args.question}")
    print(f"Intent: {result.intent.intent}")
    print(f"Confidence: {result.intent.confidence:.2f}")
    print(f"Needs clarification: {result.needs_clarification}")
    print(f"Known fields: {result.known_fields}")

    if result.clarification_questions:
        print("Questions:")
        for question in result.clarification_questions:
            print(f"- {question.question}")
    else:
        print("Questions: none")


if __name__ == "__main__":
    main()
