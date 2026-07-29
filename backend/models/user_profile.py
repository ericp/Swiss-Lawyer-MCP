"""Known user information used by clarification and future memory."""

from __future__ import annotations

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Optional user facts known before retrieval and answer generation."""

    nationality: str | None = None
    citizenships: list[str] | None = None
    country_code: str | None = None
    nationality_category: str | None = None
    eu_efta_citizen: bool | None = None
    third_country_national: bool | None = None
    is_swiss: bool | None = None
    is_uk_national: bool | None = None
    immigration_regime: str | None = None
    current_country: str | None = None
    current_country_code: str | None = None
    age: int | None = None
    education: str | None = None
    profession: str | None = None
    employment_status: str | None = None
    intended_canton: str | None = None
    intended_city: str | None = None
    purpose_of_stay: str | None = None
    marital_status: str | None = None
    children: str | None = None
    criminal_record: str | None = None
    current_permit: str | None = None
    spouse_nationality: str | None = None
    sponsor_permit: str | None = None
    relationship: str | None = None
    driving_licence_country: str | None = None
    swiss_residence_start_date: str | None = None
    planned_duration: str | None = None
