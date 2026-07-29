"""Post-generation nationality and applicability safeguards."""

from __future__ import annotations

import logging
import re

from backend.generation.answer_generator import INSUFFICIENT_CONTEXT_MESSAGE
from backend.models.generation import GeneratedAnswer
from backend.models.nationality import NationalityCategory, ResolvedCase
from backend.models.reranking import RerankedChunk

logger = logging.getLogger(__name__)

EU_EFTA_CONTRADICTIONS = [
    r"\bas an eu/?efta citizen\b",
    r"\byou are an eu/?efta citizen\b",
    r"\beu/?efta national\b",
    r"\bfree movement\b",
    r"\bagreement on the free movement of persons\b",
    r"\bafmp\b",
    r"\bno residence permit\b.*\bup to three months\b",
]

THIRD_COUNTRY_CONTRADICTIONS = [
    r"\bthird[- ]country national\b",
    r"\bnon[- ]eu/?efta\b",
    r"\bordinary third[- ]country\b",
]


def validate_generated_answer(
    *,
    answer: GeneratedAnswer,
    resolved_case: ResolvedCase,
    chunks: list[RerankedChunk],
) -> GeneratedAnswer:
    """Return a safe fallback when generated text contradicts the resolved case."""

    text = _answer_text(answer)
    category = resolved_case.nationality_category
    if _sources_inapplicable(category=category, chunks=chunks):
        return _blocked_answer(
            resolved_case=resolved_case,
            reason="retrieved evidence is not applicable to the resolved nationality category",
        )

    if category is NationalityCategory.THIRD_COUNTRY and _matches(text, EU_EFTA_CONTRADICTIONS):
        return _blocked_answer(
            resolved_case=resolved_case,
            reason="third-country case received EU/EFTA wording",
        )

    if category is NationalityCategory.EU_EFTA and _matches(text, THIRD_COUNTRY_CONTRADICTIONS):
        return _blocked_answer(
            resolved_case=resolved_case,
            reason="EU/EFTA case received third-country wording",
        )

    if category is NationalityCategory.UK and _matches(text, EU_EFTA_CONTRADICTIONS):
        return _blocked_answer(
            resolved_case=resolved_case,
            reason="UK case received unsupported EU/EFTA wording",
        )

    return answer


def _answer_text(answer: GeneratedAnswer) -> str:
    return " ".join(
        [
            answer.answer,
            answer.explanation,
            " ".join(answer.procedure_steps),
            " ".join(answer.important_notes),
        ]
    ).lower()


def _matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _sources_inapplicable(
    *,
    category: NationalityCategory,
    chunks: list[RerankedChunk],
) -> bool:
    if category is NationalityCategory.SPECIAL_OR_UNKNOWN:
        return False
    allowed = {"all", category.value}
    applicable_chunks = [
        chunk for chunk in chunks if _chunk_applicability(chunk) & allowed
    ]
    return bool(chunks) and not applicable_chunks


def _chunk_applicability(chunk: RerankedChunk) -> set[str]:
    metadata = chunk.metadata.model_dump()
    raw = metadata.get("nationality_categories") or metadata.get("applicable_person_categories")
    if raw:
        if isinstance(raw, str):
            return {item.strip().lower() for item in raw.split(",") if item.strip()}
        if isinstance(raw, list):
            return {str(item).strip().lower() for item in raw if str(item).strip()}
    source = chunk.metadata.source.lower()
    if "free_movement" in source or "eu_efta" in source:
        return {"eu_efta"}
    return {"all"}


def _blocked_answer(*, resolved_case: ResolvedCase, reason: str) -> GeneratedAnswer:
    logger.warning(
        "Blocked generated answer: %s category=%s destination=%s",
        reason,
        resolved_case.nationality_category.value,
        resolved_case.destination_canton,
    )
    category = resolved_case.nationality_category.value
    country = resolved_case.primary_country_code or "unknown"
    message = (
        f"{INSUFFICIENT_CONTEXT_MESSAGE} The user's nationality was resolved as "
        f"{country}, with category {category}."
    )
    return GeneratedAnswer(
        answer=message,
        explanation=message,
        procedure_steps=[],
        important_notes=[
            "The system blocked a generated answer because it conflicted with the resolved nationality category or used inapplicable evidence."
        ],
        cited_sources=[],
        confidence="Low",
        insufficient_context=True,
    )
