"""Nationality and resolved-case models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NationalityCategory(str, Enum):
    """Swiss immigration nationality categories."""

    SWISS = "swiss"
    EU_EFTA = "eu_efta"
    UK = "uk"
    THIRD_COUNTRY = "third_country"
    SPECIAL_OR_UNKNOWN = "special_or_unknown"


class Citizenship(BaseModel):
    """One normalized citizenship."""

    country_name: str = Field(min_length=1)
    country_code: str = Field(min_length=2, max_length=2)
    alpha3: str = Field(min_length=3, max_length=3)
    nationality_category: NationalityCategory


class ResolvedCase(BaseModel):
    """Normalized user case used for routing, retrieval and safeguards."""

    citizenships: list[Citizenship] = Field(default_factory=list)
    primary_country_code: str | None = None
    nationality_category: NationalityCategory = NationalityCategory.SPECIAL_OR_UNKNOWN
    current_country: str | None = None
    current_country_code: str | None = None
    destination_canton: str | None = None
    procedure_intent: str | None = None
    employment_status: str | None = None
    has_job_offer: bool | None = None
    planned_duration: str | None = None
    current_permit: str | None = None
    special_status: str | None = None
    unresolved_fields: list[str] = Field(default_factory=list)

    @property
    def applicable_nationality_categories(self) -> set[str]:
        """Return source applicability categories for this case."""

        if self.nationality_category is NationalityCategory.SPECIAL_OR_UNKNOWN:
            return {"all", "unknown", "special"}
        category = self.nationality_category.value
        return {"all", category}
