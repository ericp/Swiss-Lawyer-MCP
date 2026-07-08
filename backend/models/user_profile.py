"""Known user information used by clarification and future memory."""

from __future__ import annotations

from pydantic import BaseModel


class UserProfile(BaseModel):
    """Optional user facts known before retrieval and answer generation."""

    nationality: str | None = None
    current_country: str | None = None
    intended_canton: str | None = None
    canton_of_residence: str | None = None
    swiss_residence_start_date: str | None = None
    profession: str | None = None
    employment_status: str | None = None
    marital_status: str | None = None
    education: str | None = None
    children: str | None = None
    criminal_record: str | None = None
    residence_permit: str | None = None
    driving_licence_country: str | None = None
    sponsor_nationality: str | None = None
    sponsor_permit: str | None = None
    relationship: str | None = None
    age: int | None = None
