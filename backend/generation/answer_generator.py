"""Grounded answer generation using OpenAI GPT."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from backend.generation.confidence import Confidence, estimate_confidence
from backend.generation.prompts import load_grounded_answer_system_prompt
from backend.generation.source_attribution import build_cited_sources, format_context
from backend.models.clarification import DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile

INSUFFICIENT_CONTEXT_MESSAGE = (
    "The retrieved official documentation does not contain enough information "
    "to answer this question completely."
)


class GroundedAnswerGenerator:
    """Generate structured answers from reranked official context only."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        client: Any | None = None,
        system_prompt: str | None = None,
    ) -> None:
        if not api_key and client is None:
            raise ValueError("OPENAI_API_KEY is required to generate answers")
        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._system_prompt = system_prompt or load_grounded_answer_system_prompt()

    def generate(
        self,
        *,
        user_question: str,
        detected_intent: DetectedIntent,
        user_profile: UserProfile,
        reranked_chunks: list[RerankedChunk],
    ) -> GeneratedAnswer:
        """Generate a grounded answer from supplied reranked chunks."""

        citations = build_cited_sources(reranked_chunks)
        confidence = estimate_confidence(reranked_chunks)

        if not reranked_chunks:
            return _insufficient_answer(confidence=confidence, citations=citations)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        user_question=user_question,
                        detected_intent=detected_intent,
                        user_profile=user_profile,
                        reranked_chunks=reranked_chunks,
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            return _insufficient_answer(confidence=confidence, citations=citations)

        payload = json.loads(content)
        if payload.get("insufficient_context") is True:
            payload["answer"] = INSUFFICIENT_CONTEXT_MESSAGE
            payload["explanation"] = INSUFFICIENT_CONTEXT_MESSAGE
            payload["procedure_steps"] = []
        payload["confidence"] = confidence
        payload["cited_sources"] = _merge_citations(
            generated_sources=payload.get("cited_sources", []),
            required_sources=citations,
        )
        return GeneratedAnswer.model_validate(payload)


def _build_user_prompt(
    *,
    user_question: str,
    detected_intent: DetectedIntent,
    user_profile: UserProfile,
    reranked_chunks: list[RerankedChunk],
) -> str:
    profile_json = user_profile.model_dump_json(exclude_none=True)
    context = format_context(reranked_chunks)
    return "\n\n".join(
        [
            f"User question:\n{user_question}",
            f"Detected intent:\n{detected_intent.intent}",
            f"Known user profile JSON:\n{profile_json}",
            "Official retrieved context:\n" + context,
            (
                "Generate the answer in the required JSON format. Use only the "
                "official retrieved context. Cite only sources that appear in the context."
            ),
        ]
    )


def _merge_citations(
    *,
    generated_sources: list[dict[str, Any]],
    required_sources: list[CitedSource],
) -> list[dict[str, Any]]:
    allowed_keys = {
        (source.source, source.page, source.region)
        for source in required_sources
    }
    generated = {
        (source.get("source"), source.get("page"), source.get("region")): source
        for source in generated_sources
        if (source.get("source"), source.get("page"), source.get("region"))
        in allowed_keys
    }
    for source in required_sources:
        key = (source.source, source.page, source.region)
        generated.setdefault(key, source.model_dump())
    return list(generated.values())


def _insufficient_answer(
    *,
    confidence: Confidence,
    citations: list[CitedSource],
) -> GeneratedAnswer:
    return GeneratedAnswer(
        answer=INSUFFICIENT_CONTEXT_MESSAGE,
        explanation=INSUFFICIENT_CONTEXT_MESSAGE,
        procedure_steps=[],
        important_notes=[
            "Additional official Swiss documentation is required before giving procedural guidance."
        ],
        cited_sources=citations,
        confidence=confidence,
        insufficient_context=True,
    )
