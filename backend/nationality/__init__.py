"""Nationality normalization, classification and safeguards."""

from backend.models.nationality import Citizenship, NationalityCategory, ResolvedCase
from backend.nationality.resolver import (
    CountryResolution,
    build_resolved_case,
    classify_country,
    extract_current_turn_profile_updates,
    normalize_country,
)

__all__ = [
    "Citizenship",
    "CountryResolution",
    "NationalityCategory",
    "ResolvedCase",
    "build_resolved_case",
    "classify_country",
    "extract_current_turn_profile_updates",
    "normalize_country",
]
