"""Deterministic country normalization and Swiss nationality-category routing."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

import pycountry

from backend.models.nationality import Citizenship, NationalityCategory, ResolvedCase
from backend.models.user_profile import UserProfile
from backend.location.canton_resolver import CantonResolver

logger = logging.getLogger(__name__)

# Legal/configuration data: review these lists when Swiss immigration treatment changes.
EU_EFTA_COUNTRY_CODES = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IS",
    "IE",
    "IT",
    "LI",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
}

SWITZERLAND = "CH"
UNITED_KINGDOM = "GB"

SPECIAL_STATUS_MARKERS = {
    "stateless": "stateless",
    "refugee": "refugee",
    "asylum seeker": "asylum_seeker",
    "asylum": "asylum_seeker",
    "protected person": "protected_person",
    "diplomatic": "diplomatic_status",
    "diplomat": "diplomatic_status",
}

AMBIGUOUS_COUNTRY_INPUTS = {
    "korea",
    "congo",
    "macedonian",
    "samoan",
    "guinean",
    "american samoan",
}

ALIASES: dict[str, str] = {
    "australian": "AU",
    "spanish": "ES",
    "brazilian": "BR",
    "indian": "IN",
    "chinese": "CN",
    "japanese": "JP",
    "american": "US",
    "united states of america": "US",
    "usa": "US",
    "u s": "US",
    "u s a": "US",
    "british": "GB",
    "uk": "GB",
    "u k": "GB",
    "great britain": "GB",
    "britain": "GB",
    "united kingdom": "GB",
    "swiss": "CH",
    "french": "FR",
    "german": "DE",
    "italian": "IT",
    "portuguese": "PT",
    "dutch": "NL",
    "swedish": "SE",
    "norwegian": "NO",
    "icelandic": "IS",
    "liechtenstein citizen": "LI",
    "liechtensteiner": "LI",
    "cote d ivoire": "CI",
    "cote divoire": "CI",
    "côte d ivoire": "CI",
    "ivory coast": "CI",
    "ivorian": "CI",
    "turkiye": "TR",
    "türkiye": "TR",
    "turkey": "TR",
    "turkish": "TR",
    "czechia": "CZ",
    "czech republic": "CZ",
    "czech": "CZ",
    "south korea": "KR",
    "republic of korea": "KR",
    "korean": "KR",
    "north korea": "KP",
    "democratic people s republic of korea": "KP",
    "north macedonia": "MK",
    "bosnia and herzegovina": "BA",
    "bosnia herzogovina": "BA",
    "bosnian": "BA",
    "albanian": "AL",
    "argentinian": "AR",
    "argentine": "AR",
    "austrian": "AT",
    "belgian": "BE",
    "bulgarian": "BG",
    "canadian": "CA",
    "chilean": "CL",
    "colombian": "CO",
    "croatian": "HR",
    "cypriot": "CY",
    "danish": "DK",
    "estonian": "EE",
    "finnish": "FI",
    "greek": "GR",
    "hungarian": "HU",
    "irish": "IE",
    "latvian": "LV",
    "lithuanian": "LT",
    "luxembourgish": "LU",
    "maltese": "MT",
    "polish": "PL",
    "romanian": "RO",
    "slovak": "SK",
    "slovenian": "SI",
    "mexican": "MX",
    "new zealand": "NZ",
    "new zealander": "NZ",
    "pakistani": "PK",
    "russian": "RU",
    "serbian": "RS",
    "south african": "ZA",
    "thai": "TH",
    "ukrainian": "UA",
    "vietnamese": "VN",
}


@dataclass(frozen=True)
class CountryResolution:
    """Country normalization result."""

    country_name: str | None
    country_code: str | None
    alpha3: str | None
    category: NationalityCategory
    needs_clarification: bool = False
    reason: str | None = None


def normalize_key(value: str) -> str:
    """Normalize user-entered country text without fuzzy guessing."""

    value = value.replace("’", "'").replace("`", "'")
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def classify_country(country_code: str) -> NationalityCategory:
    """Classify an ISO alpha-2 country code into a Swiss immigration category."""

    code = country_code.strip().upper()
    if code == SWITZERLAND:
        return NationalityCategory.SWISS
    if code == UNITED_KINGDOM:
        return NationalityCategory.UK
    if code in EU_EFTA_COUNTRY_CODES:
        return NationalityCategory.EU_EFTA
    return NationalityCategory.THIRD_COUNTRY


def normalize_country(value: str | None) -> CountryResolution:
    """Normalize country names, alpha-2, alpha-3, aliases and common demonyms."""

    if value is None or not value.strip():
        return CountryResolution(None, None, None, NationalityCategory.SPECIAL_OR_UNKNOWN)

    key = normalize_key(value)
    if key in SPECIAL_STATUS_MARKERS:
        return CountryResolution(
            None,
            None,
            None,
            NationalityCategory.SPECIAL_OR_UNKNOWN,
            needs_clarification=True,
            reason=SPECIAL_STATUS_MARKERS[key],
        )
    if key in AMBIGUOUS_COUNTRY_INPUTS:
        return CountryResolution(
            None,
            None,
            None,
            NationalityCategory.SPECIAL_OR_UNKNOWN,
            needs_clarification=True,
            reason="ambiguous_country",
        )

    country = _lookup_country(value, key)
    if country is None:
        return CountryResolution(
            None,
            None,
            None,
            NationalityCategory.SPECIAL_OR_UNKNOWN,
            needs_clarification=True,
            reason="unknown_country",
        )

    category = classify_country(country.alpha_2)
    return CountryResolution(
        country_name=country.name,
        country_code=country.alpha_2,
        alpha3=country.alpha_3,
        category=category,
    )


def extract_current_turn_profile_updates(question: str) -> dict[str, Any]:
    """Extract explicit current-turn residence/citizenship facts deterministically."""

    updates: dict[str, Any] = {}
    citizenship_values = _extract_citizenship_values(question)
    citizenships = _normalize_many(citizenship_values)
    if citizenships:
        updates["citizenships"] = [citizenship.country_code for citizenship in citizenships]
        if len(citizenships) == 1:
            updates["nationality"] = citizenships[0].country_name
            updates["country_code"] = citizenships[0].country_code
            updates["nationality_category"] = citizenships[0].nationality_category.value
    elif _contains_special_status(question):
        updates["nationality_category"] = NationalityCategory.SPECIAL_OR_UNKNOWN.value

    current_country = _extract_current_country(question)
    if current_country:
        resolution = normalize_country(current_country)
        if resolution.country_code:
            updates["current_country"] = resolution.country_name
            updates["current_country_code"] = resolution.country_code
    intended_city = _extract_intended_city(question)
    if intended_city:
        updates["intended_city"] = intended_city

    if _mentions_job_offer(question):
        existing = str(updates.get("employment_status", "")).strip()
        marker = "has Swiss job offer"
        updates["employment_status"] = f"{existing}; {marker}" if existing else marker
    if _mentions_long_stay(question):
        updates["planned_duration"] = "more_than_one_year"
    return updates


def build_resolved_case(
    *,
    profile: UserProfile,
    intent: str,
    question: str,
) -> ResolvedCase:
    """Build the normalized case object used before retrieval."""

    special_status = _special_status_from_text(question)
    citizenships = _citizenships_from_profile(profile)
    unresolved_fields: list[str] = []

    if special_status:
        category = NationalityCategory.SPECIAL_OR_UNKNOWN
        primary_country_code = None
        unresolved_fields.append("special_status")
    elif not citizenships:
        category = NationalityCategory.SPECIAL_OR_UNKNOWN
        primary_country_code = None
        unresolved_fields.append("nationality")
    elif len(citizenships) > 1:
        category = NationalityCategory.SPECIAL_OR_UNKNOWN
        primary_country_code = None
        unresolved_fields.append("primary_citizenship")
    else:
        category = citizenships[0].nationality_category
        primary_country_code = citizenships[0].country_code

    current_country_code = None
    current_country = profile.current_country
    if current_country:
        current_resolution = normalize_country(current_country)
        current_country_code = current_resolution.country_code
        current_country = current_resolution.country_name or current_country

    return ResolvedCase(
        citizenships=citizenships,
        primary_country_code=primary_country_code,
        nationality_category=category,
        current_country=current_country,
        current_country_code=current_country_code,
        destination_canton=profile.intended_canton,
        procedure_intent=intent,
        employment_status=profile.employment_status,
        has_job_offer=_employment_status_has_job_offer(profile.employment_status),
        planned_duration=profile.planned_duration,
        current_permit=profile.current_permit,
        special_status=special_status,
        unresolved_fields=unresolved_fields,
    )


def _lookup_country(original: str, key: str) -> Any | None:
    if key in ALIASES:
        return pycountry.countries.get(alpha_2=ALIASES[key])
    compact = key.replace(" ", "")
    if len(compact) == 2:
        country = pycountry.countries.get(alpha_2=compact.upper())
        if country is not None:
            return country
    if len(compact) == 3:
        country = pycountry.countries.get(alpha_3=compact.upper())
        if country is not None:
            return country

    for country in pycountry.countries:
        names = {
            country.name,
            getattr(country, "official_name", ""),
            getattr(country, "common_name", ""),
        }
        if key in {normalize_key(name) for name in names if name}:
            return country

    try:
        matches = pycountry.countries.search_fuzzy(original)
    except LookupError:
        return None
    exact_matches = [
        country
        for country in matches
        if key in {
            normalize_key(country.name),
            normalize_key(getattr(country, "official_name", "")),
            normalize_key(getattr(country, "common_name", "")),
        }
    ]
    return exact_matches[0] if len(exact_matches) == 1 else None


def _citizenships_from_profile(profile: UserProfile) -> list[Citizenship]:
    raw_values: list[str] = []
    if profile.citizenships:
        raw_values.extend(profile.citizenships)
    if profile.nationality:
        raw_values.append(profile.nationality)

    normalized = _normalize_many(raw_values)
    if normalized:
        return normalized
    if profile.country_code:
        resolution = normalize_country(profile.country_code)
        if resolution.country_code:
            return [_citizenship_from_resolution(resolution)]
    return []


def _normalize_many(values: list[str]) -> list[Citizenship]:
    seen: set[str] = set()
    citizenships: list[Citizenship] = []
    for value in values:
        resolution = normalize_country(value)
        if not resolution.country_code or resolution.country_code in seen:
            continue
        seen.add(resolution.country_code)
        citizenships.append(_citizenship_from_resolution(resolution))
    return citizenships


def _citizenship_from_resolution(resolution: CountryResolution) -> Citizenship:
    return Citizenship(
        country_name=resolution.country_name or resolution.country_code or "Unknown",
        country_code=resolution.country_code or "",
        alpha3=resolution.alpha3 or "",
        nationality_category=resolution.category,
    )


def _extract_citizenship_values(question: str) -> list[str]:
    values: list[str] = []
    patterns = [
        r"\b(?:i am|i'm|im|as)\s+(?:an?\s+)?([A-Za-zÀ-ÿ' .-]+?)\s+citizen\b",
        r"\b(?:my nationality is|nationality is)\s+([A-Za-zÀ-ÿ' .-]+)",
        r"\b(?:i hold|holding|have)\s+(?:an?\s+)?([A-Za-zÀ-ÿ' .-]+?)\s+passport\b",
        r"\b(?:i have|i hold|holding)\s+([A-Za-zÀ-ÿ' .-]+?)\s+citizenship\b",
        r"\b([A-Za-zÀ-ÿ' .-]+?)\s+citizenship\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, question, flags=re.IGNORECASE):
            values.extend(_split_country_phrase(match.group(1)))

    for alias in sorted(ALIASES, key=len, reverse=True):
        if re.search(rf"\b(?:i am|i'm|im|as)\s+(?:an?\s+)?{re.escape(alias)}\b", question, flags=re.IGNORECASE):
            values.append(alias)
    return values


def _extract_current_country(question: str) -> str | None:
    patterns = [
        r"\b(?:i live in|living in|currently live in|reside in|resident in)\s+([A-Za-zÀ-ÿ' .-]+)",
        r"\bcurrent(?:ly)?\s+in\s+([A-Za-zÀ-ÿ' .-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match:
            return _trim_phrase(match.group(1))
    return None


def _extract_intended_city(question: str) -> str | None:
    resolver = CantonResolver()
    for city in sorted(resolver.CITY_TO_CANTON, key=len, reverse=True):
        if re.search(rf"\b{re.escape(city)}\b", question, flags=re.IGNORECASE):
            return city.title()
    return None


def _split_country_phrase(value: str) -> list[str]:
    cleaned = _trim_phrase(value)
    parts = re.split(r"\s+(?:and|or)\s+|[,/]", cleaned, flags=re.IGNORECASE)
    return [part.strip() for part in parts if part.strip()]


def _trim_phrase(value: str) -> str:
    value = re.split(r"\b(?:but|and want|and i|who|with|for|to|get|legally)\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = re.sub(r"^\s*(?:i\s+(?:am|have|hold)|i'm|im|my nationality is)\s+", "", value, flags=re.IGNORECASE)
    return value.strip(" .,'\"")


def _contains_special_status(question: str) -> bool:
    return _special_status_from_text(question) is not None


def _special_status_from_text(question: str) -> str | None:
    key = normalize_key(question)
    for marker, status in SPECIAL_STATUS_MARKERS.items():
        if marker in key:
            return status
    return None


def _mentions_job_offer(question: str) -> bool:
    key = normalize_key(question)
    return "job offer" in key or "employment offer" in key


def _mentions_long_stay(question: str) -> bool:
    key = normalize_key(question)
    return "more than one year" in key or "longer than one year" in key


def _employment_status_has_job_offer(value: str | None) -> bool | None:
    if not value:
        return None
    key = normalize_key(value)
    if "no swiss job offer" in key:
        return False
    if "job offer" in key:
        return True
    return None
