from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.procedure_schemas import (
    PROCEDURE_SCHEMAS,
    ProcedureSchema,
)
from backend.models.clarification import DetectedIntent
from backend.models.user_profile import UserProfile


def test_immigration_with_only_nationality_known_asks_schema_required_fields() -> None:
    engine = ClarificationEngine()
    result = engine.evaluate(
        user_question="Can I move to Switzerland as a Brazilian citizen?",
        detected_intent=DetectedIntent(
            intent="immigration",
            confidence=0.8,
            matched_keywords=["move to switzerland"],
        ),
        user_profile=UserProfile(nationality="Brazil"),
    )

    assert result.intent.intent == "immigration"
    assert result.needs_clarification is True
    assert result.known_fields == {"nationality": "Brazil"}
    assert result.missing_fields == [
        "intended_canton",
        "purpose_of_stay",
        "employment_status",
    ]
    assert [question.question for question in result.clarification_questions] == [
        "Which Swiss canton or city are you planning to move to?",
        "What is your main purpose for moving to Switzerland?",
        "Will you be employed, self-employed, studying, joining family, or moving without work?",
    ]


def test_driving_licence_exchange_does_not_ask_family_related_questions() -> None:
    engine = ClarificationEngine()
    result = engine.evaluate(
        user_question="I have an Italian driving licence.",
        detected_intent=DetectedIntent(
            intent="driving_licence_exchange",
            confidence=0.8,
            matched_keywords=["driving licence"],
        ),
        user_profile=UserProfile(driving_licence_country="Italy"),
    )

    assert result.missing_fields == [
        "intended_canton",
        "swiss_residence_start_date",
    ]
    asked_fields = {question.field for question in result.clarification_questions}
    assert "spouse_nationality" not in asked_fields
    assert "sponsor_permit" not in asked_fields
    assert "relationship" not in asked_fields
    assert "children" not in asked_fields
    assert "marital_status" not in asked_fields


def test_family_reunification_asks_sponsor_spouse_relationship_questions() -> None:
    engine = ClarificationEngine()
    result = engine.evaluate(
        user_question="Can I join my spouse in Switzerland?",
        detected_intent=DetectedIntent(
            intent="family_reunification",
            confidence=0.8,
            matched_keywords=["join my spouse"],
        ),
        user_profile=UserProfile(),
    )

    assert result.missing_fields == [
        "spouse_nationality",
        "sponsor_permit",
        "relationship",
    ]
    assert [question.field for question in result.clarification_questions] == [
        "spouse_nationality",
        "sponsor_permit",
        "relationship",
    ]


def test_all_required_fields_known_needs_no_clarification() -> None:
    engine = ClarificationEngine()
    result = engine.evaluate(
        user_question="Can I move to Switzerland?",
        detected_intent=DetectedIntent(intent="immigration", confidence=0.8),
        user_profile=UserProfile(
            nationality="Brazil",
            intended_canton="Zurich",
            purpose_of_stay="work",
            employment_status="employed",
        ),
    )

    assert result.needs_clarification is False
    assert result.missing_fields == []
    assert result.clarification_questions == []


def test_missing_fields_are_derived_from_injected_procedure_schema() -> None:
    schema = ProcedureSchema(
        intent="custom_procedure",
        required_fields=["nationality", "profession"],
        optional_fields=["children"],
        field_descriptions={
            "nationality": "Applicant nationality.",
            "profession": "Applicant profession.",
        },
        questions={
            "nationality": "What is your nationality?",
            "profession": "What is your profession?",
        },
        intent_keywords=[],
    )
    engine = ClarificationEngine(procedure_schemas={"custom_procedure": schema})

    result = engine.evaluate(
        user_question="Custom question",
        detected_intent=DetectedIntent(intent="custom_procedure", confidence=1.0),
        user_profile=UserProfile(nationality="Brazil"),
    )

    assert result.missing_fields == ["profession"]
    assert [question.question for question in result.clarification_questions] == [
        "What is your profession?"
    ]


def test_all_procedure_required_fields_have_questions_and_descriptions() -> None:
    for schema in PROCEDURE_SCHEMAS.values():
        for field in schema.required_fields:
            assert field in schema.questions
            assert field in schema.field_descriptions
