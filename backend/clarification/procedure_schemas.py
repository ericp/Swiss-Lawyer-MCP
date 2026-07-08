"""Deterministic procedure schemas for clarification."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProcedureSchema(BaseModel):
    """Clarification schema for one supported procedure."""

    intent: str = Field(min_length=1)
    required_fields: list[str]
    optional_fields: list[str] = Field(default_factory=list)
    field_descriptions: dict[str, str]
    questions: dict[str, str]
    intent_keywords: list[str] = Field(default_factory=list)


PROCEDURE_SCHEMAS: dict[str, ProcedureSchema] = {
    "immigration": ProcedureSchema(
        intent="immigration",
        required_fields=[
            "nationality",
            "intended_canton",
            "purpose_of_stay",
            "employment_status",
        ],
        optional_fields=[
            "age",
            "education",
            "profession",
            "marital_status",
            "children",
            "criminal_record",
            "current_country",
            "intended_city",
        ],
        field_descriptions={
            "nationality": "Citizenship of the person moving to Switzerland.",
            "intended_canton": "Swiss canton or city where the person plans to live.",
            "purpose_of_stay": "Main reason for moving, such as work, study, family, or no gainful activity.",
            "employment_status": "Whether the person will be employed, self-employed, studying, joining family, or not working.",
        },
        questions={
            "nationality": "What is your nationality?",
            "intended_canton": "Which Swiss canton or city are you planning to move to?",
            "purpose_of_stay": "What is your main purpose for moving to Switzerland?",
            "employment_status": "Will you be employed, self-employed, studying, joining family, or moving without work?",
        },
        intent_keywords=[
            "immigrate",
            "immigration",
            "move to switzerland",
            "relocate",
            "live in switzerland",
            "moving to switzerland",
        ],
    ),
    "residence_permit": ProcedureSchema(
        intent="residence_permit",
        required_fields=[
            "nationality",
            "current_country",
            "intended_canton",
            "purpose_of_stay",
            "employment_status",
        ],
        optional_fields=[
            "current_permit",
            "profession",
            "education",
            "marital_status",
            "children",
            "intended_city",
        ],
        field_descriptions={
            "nationality": "Citizenship of the applicant.",
            "current_country": "Country where the applicant currently resides.",
            "intended_canton": "Swiss canton where the applicant plans to reside.",
            "purpose_of_stay": "Reason for residence in Switzerland.",
            "employment_status": "Planned work or non-work status in Switzerland.",
        },
        questions={
            "nationality": "What is your nationality?",
            "current_country": "Which country do you currently live in?",
            "intended_canton": "Which Swiss canton do you plan to live in?",
            "purpose_of_stay": "What is your main purpose for staying in Switzerland?",
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
    "work_permit": ProcedureSchema(
        intent="work_permit",
        required_fields=[
            "nationality",
            "intended_canton",
            "profession",
            "employment_status",
        ],
        optional_fields=[
            "education",
            "current_country",
            "current_permit",
            "purpose_of_stay",
            "intended_city",
        ],
        field_descriptions={
            "nationality": "Citizenship of the worker.",
            "intended_canton": "Swiss canton where the work would take place.",
            "profession": "Occupation or job role.",
            "employment_status": "Employment arrangement, such as employed or self-employed.",
        },
        questions={
            "nationality": "What is your nationality?",
            "intended_canton": "In which Swiss canton would you work?",
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
    "family_reunification": ProcedureSchema(
        intent="family_reunification",
        required_fields=[
            "spouse_nationality",
            "sponsor_permit",
            "relationship",
        ],
        optional_fields=[
            "nationality",
            "intended_canton",
            "children",
            "marital_status",
            "current_permit",
        ],
        field_descriptions={
            "spouse_nationality": "Nationality of the Swiss-based sponsor or spouse.",
            "sponsor_permit": "Swiss permit or status held by the sponsor.",
            "relationship": "Family relationship between applicant and sponsor.",
        },
        questions={
            "spouse_nationality": "What is the nationality of your spouse or Swiss-based sponsor?",
            "sponsor_permit": "What Swiss permit or status does your sponsor have?",
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
    "municipality_registration": ProcedureSchema(
        intent="municipality_registration",
        required_fields=[
            "intended_canton",
            "current_country",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "nationality",
            "current_permit",
            "intended_city",
        ],
        field_descriptions={
            "intended_canton": "Swiss canton or municipality where the person will register.",
            "current_country": "Country the person is moving from.",
            "swiss_residence_start_date": "Date Swiss residence begins or began.",
        },
        questions={
            "intended_canton": "In which Swiss canton or municipality will you register?",
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
    "driving_licence_exchange": ProcedureSchema(
        intent="driving_licence_exchange",
        required_fields=[
            "driving_licence_country",
            "intended_canton",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "nationality",
            "current_permit",
            "intended_city",
        ],
        field_descriptions={
            "driving_licence_country": "Country that issued the foreign driving licence.",
            "intended_canton": "Swiss canton of residence responsible for the exchange procedure.",
            "swiss_residence_start_date": "Date Swiss residence began.",
        },
        questions={
            "driving_licence_country": "Which country issued your driving licence?",
            "intended_canton": "What is your Swiss canton of residence?",
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
    "citizenship": ProcedureSchema(
        intent="citizenship",
        required_fields=[
            "nationality",
            "intended_canton",
            "current_permit",
            "swiss_residence_start_date",
        ],
        optional_fields=[
            "age",
            "marital_status",
            "children",
            "criminal_record",
            "education",
            "intended_city",
        ],
        field_descriptions={
            "nationality": "Current nationality of the applicant.",
            "intended_canton": "Canton of residence, because naturalization has cantonal and communal components.",
            "current_permit": "Current Swiss residence permit or status.",
            "swiss_residence_start_date": "Date Swiss residence began.",
        },
        questions={
            "nationality": "What is your current nationality?",
            "intended_canton": "What is your Swiss canton of residence?",
            "current_permit": "What Swiss residence permit do you currently hold?",
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
