"""Configurable procedure schemas for clarification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProcedureSchema(BaseModel):
    """Clarification schema for one supported procedure."""

    intent: str = Field(min_length=1)
    required_fields: list[str]
    optional_fields: list[str] = Field(default_factory=list)
    clarification_questions: dict[str, str]
    intent_keywords: list[str] = Field(default_factory=list)


PROCEDURE_SCHEMAS: dict[str, ProcedureSchema] = {
    "Immigration": ProcedureSchema(
        intent="Immigration",
        required_fields=[
            "nationality",
            "intended_canton",
            "employment_status",
        ],
        optional_fields=[
            "age",
            "education",
            "marital_status",
            "children",
            "criminal_record",
            "profession",
            "current_country",
        ],
        clarification_questions={
            "nationality": "What is your nationality?",
            "intended_canton": "Which canton do you intend to move to?",
            "employment_status": "Will you be employed in Switzerland?",
        },
        intent_keywords=[
            "immigrate",
            "immigration",
            "move to switzerland",
            "relocate",
            "live in switzerland",
        ],
    ),
    "Residence Permit": ProcedureSchema(
        intent="Residence Permit",
        required_fields=[
            "nationality",
            "current_country",
            "intended_canton",
            "employment_status",
        ],
        optional_fields=[
            "residence_permit",
            "profession",
            "education",
            "marital_status",
            "children",
        ],
        clarification_questions={
            "nationality": "What is your nationality?",
            "current_country": "Which country do you currently live in?",
            "intended_canton": "Which canton do you plan to live in?",
            "employment_status": "What will your employment status be in Switzerland?",
        },
        intent_keywords=[
            "residence permit",
            "resident permit",
            "permit b",
            "b permit",
            "c permit",
            "stay permit",
        ],
    ),
    "Work Permit": ProcedureSchema(
        intent="Work Permit",
        required_fields=[
            "nationality",
            "intended_canton",
            "profession",
            "employment_status",
        ],
        optional_fields=[
            "education",
            "current_country",
            "residence_permit",
        ],
        clarification_questions={
            "nationality": "What is your nationality?",
            "intended_canton": "In which canton would you work?",
            "profession": "What is your profession or job role?",
            "employment_status": "Will you be employed, self-employed, or seeking work?",
        },
        intent_keywords=[
            "work permit",
            "work in switzerland",
            "employed",
            "employment",
            "job in switzerland",
            "swiss company",
        ],
    ),
    "Family Reunification": ProcedureSchema(
        intent="Family Reunification",
        required_fields=[
            "sponsor_nationality",
            "sponsor_permit",
            "relationship",
        ],
        optional_fields=[
            "nationality",
            "intended_canton",
            "children",
            "marital_status",
        ],
        clarification_questions={
            "sponsor_nationality": "What is the sponsor's nationality?",
            "sponsor_permit": "What Swiss permit or status does the sponsor have?",
            "relationship": "What is your relationship to the sponsor?",
        },
        intent_keywords=[
            "family reunification",
            "bring my spouse",
            "bring my wife",
            "bring my husband",
            "join my spouse",
            "join my family",
            "family reunion",
        ],
    ),
    "Municipality Registration": ProcedureSchema(
        intent="Municipality Registration",
        required_fields=[
            "intended_canton",
            "current_country",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "nationality",
            "residence_permit",
        ],
        clarification_questions={
            "intended_canton": "In which canton or municipality will you register?",
            "current_country": "Which country are you moving from?",
            "swiss_residence_start_date": "When will your Swiss residence start?",
        },
        intent_keywords=[
            "register",
            "registration",
            "municipality",
            "commune",
            "gemeinde",
            "arrival",
            "moving address",
        ],
    ),
    "Driving Licence Exchange": ProcedureSchema(
        intent="Driving Licence Exchange",
        required_fields=[
            "driving_licence_country",
            "canton_of_residence",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "nationality",
            "residence_permit",
        ],
        clarification_questions={
            "driving_licence_country": "Which country issued your driving licence?",
            "canton_of_residence": "What is your canton of residence in Switzerland?",
            "swiss_residence_start_date": "When did your Swiss residence start?",
        },
        intent_keywords=[
            "driving licence",
            "driver licence",
            "driving license",
            "driver license",
            "licence exchange",
            "license exchange",
            "exchange my licence",
            "exchange my license",
        ],
    ),
    "Citizenship / Naturalization": ProcedureSchema(
        intent="Citizenship / Naturalization",
        required_fields=[
            "nationality",
            "canton_of_residence",
            "residence_permit",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "age",
            "marital_status",
            "children",
            "criminal_record",
            "education",
        ],
        clarification_questions={
            "nationality": "What is your current nationality?",
            "canton_of_residence": "What is your canton of residence?",
            "residence_permit": "What Swiss residence permit do you currently hold?",
            "swiss_residence_start_date": "When did your Swiss residence start?",
        },
        intent_keywords=[
            "citizenship",
            "naturalization",
            "naturalisation",
            "become swiss",
            "swiss passport",
        ],
    ),
}


def get_procedure_schema(intent: str) -> ProcedureSchema | None:
    """Return the schema for a detected intent, if supported."""

    return PROCEDURE_SCHEMAS.get(intent)


def list_procedure_schemas() -> list[ProcedureSchema]:
    """Return supported procedure schemas."""

    return list(PROCEDURE_SCHEMAS.values())
