from __future__ import annotations

import pycountry
import pytest

from backend.generation.answer_generator import INSUFFICIENT_CONTEXT_MESSAGE
from backend.models.chunk import ChunkMetadata
from backend.models.generation import GeneratedAnswer
from backend.models.nationality import NationalityCategory
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile
from backend.nationality.answer_validator import validate_generated_answer
from backend.nationality.resolver import (
    EU_EFTA_COUNTRY_CODES,
    build_resolved_case,
    classify_country,
    extract_current_turn_profile_updates,
    normalize_country,
)


@pytest.mark.parametrize(
    ("value", "code", "category"),
    [
        ("Australia", "AU", NationalityCategory.THIRD_COUNTRY),
        ("Australian", "AU", NationalityCategory.THIRD_COUNTRY),
        ("AU", "AU", NationalityCategory.THIRD_COUNTRY),
        ("AUS", "AU", NationalityCategory.THIRD_COUNTRY),
        ("Spain", "ES", NationalityCategory.EU_EFTA),
        ("Spanish", "ES", NationalityCategory.EU_EFTA),
        ("ES", "ES", NationalityCategory.EU_EFTA),
        ("ESP", "ES", NationalityCategory.EU_EFTA),
        ("United States", "US", NationalityCategory.THIRD_COUNTRY),
        ("United States of America", "US", NationalityCategory.THIRD_COUNTRY),
        ("USA", "US", NationalityCategory.THIRD_COUNTRY),
        ("U.S.", "US", NationalityCategory.THIRD_COUNTRY),
        ("American", "US", NationalityCategory.THIRD_COUNTRY),
        ("United Kingdom", "GB", NationalityCategory.UK),
        ("UK", "GB", NationalityCategory.UK),
        ("U.K.", "GB", NationalityCategory.UK),
        ("Great Britain", "GB", NationalityCategory.UK),
        ("British", "GB", NationalityCategory.UK),
        ("Switzerland", "CH", NationalityCategory.SWISS),
        ("Swiss", "CH", NationalityCategory.SWISS),
        ("CH", "CH", NationalityCategory.SWISS),
        ("CHE", "CH", NationalityCategory.SWISS),
        ("Côte d’Ivoire", "CI", NationalityCategory.THIRD_COUNTRY),
        ("Cote d'Ivoire", "CI", NationalityCategory.THIRD_COUNTRY),
        ("Ivory Coast", "CI", NationalityCategory.THIRD_COUNTRY),
        ("Ivorian", "CI", NationalityCategory.THIRD_COUNTRY),
        ("Türkiye", "TR", NationalityCategory.THIRD_COUNTRY),
        ("Turkey", "TR", NationalityCategory.THIRD_COUNTRY),
        ("Turkish", "TR", NationalityCategory.THIRD_COUNTRY),
        ("Czechia", "CZ", NationalityCategory.EU_EFTA),
        ("Czech Republic", "CZ", NationalityCategory.EU_EFTA),
        ("Czech", "CZ", NationalityCategory.EU_EFTA),
        ("South Korea", "KR", NationalityCategory.THIRD_COUNTRY),
        ("Republic of Korea", "KR", NationalityCategory.THIRD_COUNTRY),
        ("Korean", "KR", NationalityCategory.THIRD_COUNTRY),
        ("North Macedonia", "MK", NationalityCategory.THIRD_COUNTRY),
        ("Bosnia and Herzegovina", "BA", NationalityCategory.THIRD_COUNTRY),
        ("Bosnian", "BA", NationalityCategory.THIRD_COUNTRY),
    ],
)
def test_country_aliases_and_demonyms_normalize(
    value: str,
    code: str,
    category: NationalityCategory,
) -> None:
    resolution = normalize_country(value)

    assert resolution.country_code == code
    assert resolution.category is category


def test_all_iso_countries_resolve_to_one_ordinary_category() -> None:
    countries = list(pycountry.countries)

    assert len(countries) >= 249
    for country in countries:
        by_name = normalize_country(country.name)
        by_alpha2 = normalize_country(country.alpha_2)
        by_alpha3 = normalize_country(country.alpha_3)

        if country.name not in {"Congo"}:
            assert by_name.country_code == country.alpha_2
        assert by_alpha2.country_code == country.alpha_2
        assert by_alpha3.country_code == country.alpha_2
        if by_name.country_code:
            assert by_name.category in {
                NationalityCategory.SWISS,
                NationalityCategory.EU_EFTA,
                NationalityCategory.UK,
                NationalityCategory.THIRD_COUNTRY,
            }


def test_eu_efta_list_uk_and_third_country_classification() -> None:
    assert classify_country("CH") is NationalityCategory.SWISS
    assert classify_country("GB") is NationalityCategory.UK
    for code in EU_EFTA_COUNTRY_CODES:
        assert classify_country(code) is NationalityCategory.EU_EFTA
    assert classify_country("AU") is NationalityCategory.THIRD_COUNTRY
    assert classify_country("US") is NationalityCategory.THIRD_COUNTRY
    assert classify_country("BR") is NationalityCategory.THIRD_COUNTRY


@pytest.mark.parametrize("value", ["Korea", "Congo", "Samoan", "not-a-country"])
def test_ambiguous_or_unknown_input_needs_clarification(value: str) -> None:
    resolution = normalize_country(value)

    assert resolution.needs_clarification is True
    assert resolution.category is NationalityCategory.SPECIAL_OR_UNKNOWN


def test_current_turn_extraction_separates_citizenship_from_residence() -> None:
    american = extract_current_turn_profile_updates("I am an American citizen living in Spain.")
    spanish = extract_current_turn_profile_updates("I live in Australia but I am a Spanish citizen.")

    assert american["country_code"] == "US"
    assert american["current_country_code"] == "ES"
    assert american["nationality_category"] == "third_country"
    assert spanish["country_code"] == "ES"
    assert spanish["current_country_code"] == "AU"
    assert spanish["nationality_category"] == "eu_efta"


def test_dual_citizenship_is_retained_and_requires_primary_choice() -> None:
    updates = extract_current_turn_profile_updates("I have Australian and Spanish citizenship.")
    case = build_resolved_case(
        profile=UserProfile(citizenships=updates["citizenships"]),
        intent="work_permit",
        question="I have Australian and Spanish citizenship.",
    )

    assert {citizenship.country_code for citizenship in case.citizenships} == {"AU", "ES"}
    assert case.nationality_category is NationalityCategory.SPECIAL_OR_UNKNOWN
    assert "primary_citizenship" in case.unresolved_fields


def test_special_status_is_not_silently_third_country() -> None:
    case = build_resolved_case(
        profile=UserProfile(),
        intent="immigration",
        question="I am stateless and want to move to Zurich.",
    )

    assert case.nationality_category is NationalityCategory.SPECIAL_OR_UNKNOWN
    assert case.special_status == "stateless"


def test_post_generation_validator_blocks_third_country_eu_efta_claim() -> None:
    answer = GeneratedAnswer(
        answer="As an EU/EFTA citizen, you benefit from free movement.",
        explanation="You can simply register after arrival under EU/EFTA rules.",
        procedure_steps=["Register after arrival."],
        important_notes=[],
        cited_sources=[],
        confidence="High",
        insufficient_context=False,
    )
    case = build_resolved_case(
        profile=UserProfile(nationality="Australian"),
        intent="work_permit",
        question="I'm an Australian citizen.",
    )
    chunk = RerankedChunk(
        chunk_id="eu",
        text="Free movement applies to EU/EFTA citizens.",
        metadata=ChunkMetadata(source="free_movement_eu_efta.pdf", region="federal", page=1),
        retrieval_source="vector",
        retrieval_score=1.0,
        rerank_score=1.0,
    )

    validated = validate_generated_answer(answer=answer, resolved_case=case, chunks=[chunk])

    assert validated.insufficient_context is True
    assert INSUFFICIENT_CONTEXT_MESSAGE in validated.answer
    assert "third_country" in validated.answer
