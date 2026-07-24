"""Workflow planner that turns grounded answers into actionable plans."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from backend.generation.source_attribution import format_context
from backend.models.clarification import DetectedIntent
from backend.models.generation import CitedSource, GeneratedAnswer
from backend.models.planner import ProcedurePlan, WorkflowStatus
from backend.models.reranking import RerankedChunk
from backend.models.user_profile import UserProfile
from backend.planners.prompts import load_workflow_planner_system_prompt
from backend.utils.config import load_project_env

NOT_SPECIFIED = "Not specified in retrieved sources."


class WorkflowPlanner:
    """Create structured procedure workflows from grounded answers."""

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        client: Any | None = None,
        system_prompt: str | None = None,
    ) -> None:
        load_project_env()
        if client is None and os.getenv("AI_MODE", "").strip().lower() == "local":
            raise RuntimeError("OpenAI provider was requested while AI_MODE=local.")
        if not api_key and client is None:
            raise ValueError("OPENAI_API_KEY is required to create workflow plans")
        if client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key)
        else:
            self._client = client
        self._model = model
        self._system_prompt = system_prompt or load_workflow_planner_system_prompt()

    def create_plan(
        self,
        *,
        user_question: str,
        detected_intent: DetectedIntent,
        user_profile: UserProfile,
        generated_answer: GeneratedAnswer,
        reranked_chunks: list[RerankedChunk],
    ) -> ProcedurePlan:
        """Create and validate a procedure workflow plan."""

        if generated_answer.insufficient_context:
            return _insufficient_context_plan(
                user_question=user_question,
                generated_answer=generated_answer,
            )

        messages = [
            {"role": "system", "content": self._system_prompt},
            {
                "role": "user",
                "content": _build_planner_user_prompt(
                    user_question=user_question,
                    detected_intent=detected_intent,
                    user_profile=user_profile,
                    generated_answer=generated_answer,
                    reranked_chunks=reranked_chunks,
                ),
            },
        ]
        payload = _load_json_with_repair(
            client=self._client,
            model=self._model,
            messages=messages,
        )
        if payload is None:
            return _insufficient_context_plan(
                user_question=user_question,
                generated_answer=generated_answer,
            )

        payload["source_references"] = _filter_source_references(
            generated_sources=payload.get("source_references", []),
            allowed_sources=generated_answer.cited_sources,
        )
        try:
            plan = ProcedurePlan.model_validate(payload)
        except ValidationError:
            return _insufficient_context_plan(
                user_question=user_question,
                generated_answer=generated_answer,
            )
        return _apply_planner_safeguards(plan, generated_answer)


def _load_json_with_repair(
    *,
    client: Any,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any] | None:
    content = _call_chat_json(client=client, model=model, messages=messages)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        repair_messages = [
            *messages,
            {"role": "assistant", "content": content},
            {
                "role": "user",
                "content": "Return only valid JSON for the previous workflow plan. Do not add commentary.",
            },
        ]
        repaired = _call_chat_json(client=client, model=model, messages=repair_messages)
        if not repaired:
            return None
        try:
            return json.loads(repaired)
        except json.JSONDecodeError:
            return None


def _call_chat_json(*, client: Any, model: str, messages: list[dict[str, str]]) -> str | None:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def _build_planner_user_prompt(
    *,
    user_question: str,
    detected_intent: DetectedIntent,
    user_profile: UserProfile,
    generated_answer: GeneratedAnswer,
    reranked_chunks: list[RerankedChunk],
) -> str:
    return "\n\n".join(
        [
            f"User question:\n{user_question}",
            f"Detected intent:\n{detected_intent.intent}",
            f"Known user profile JSON:\n{user_profile.model_dump_json(exclude_none=True)}",
            f"Grounded answer JSON:\n{generated_answer.model_dump_json()}",
            "Cited evidence context:\n" + format_context(reranked_chunks),
            (
                "Convert the grounded answer into the required workflow JSON. "
                "Use only the grounded answer and cited evidence."
            ),
        ]
    )


def _filter_source_references(
    *,
    generated_sources: list[dict[str, Any]],
    allowed_sources: list[CitedSource],
) -> list[dict[str, Any]]:
    allowed_keys = {
        (source.source, source.page, source.region)
        for source in allowed_sources
    }
    filtered = [
        source
        for source in generated_sources
        if (source.get("source"), source.get("page"), source.get("region"))
        in allowed_keys
    ]
    if filtered:
        return filtered
    return [source.model_dump() for source in allowed_sources]


def _apply_planner_safeguards(
    plan: ProcedurePlan,
    generated_answer: GeneratedAnswer,
) -> ProcedurePlan:
    missing_information = [
        item for item in plan.missing_information if item.strip()
    ]
    status = _determine_status(
        generated_answer=generated_answer,
        missing_information=missing_information,
        proposed_status=plan.status,
    )
    estimated_timelines = _fallback_list(plan.estimated_timelines)
    required_documents = _fallback_list(plan.required_documents)
    potential_blockers = _fallback_list(plan.potential_blockers)

    return plan.model_copy(
        update={
            "status": status,
            "missing_information": missing_information,
            "estimated_timelines": estimated_timelines,
            "required_documents": required_documents,
            "potential_blockers": potential_blockers,
        }
    )


def _determine_status(
    *,
    generated_answer: GeneratedAnswer,
    missing_information: list[str],
    proposed_status: WorkflowStatus,
) -> WorkflowStatus:
    answer_text = " ".join(
        [
            generated_answer.answer,
            generated_answer.explanation,
            " ".join(generated_answer.important_notes),
        ]
    ).lower()

    blocker_markers = [
        "not eligible",
        "not qualify",
        "cannot proceed",
        "may not currently qualify",
    ]
    if any(marker in answer_text for marker in blocker_markers):
        return WorkflowStatus.BLOCKED
    if generated_answer.insufficient_context or missing_information:
        return WorkflowStatus.NEEDS_MORE_INFORMATION
    if proposed_status in {
        WorkflowStatus.IN_PROGRESS,
        WorkflowStatus.COMPLETED,
    }:
        return WorkflowStatus.READY_TO_START
    return proposed_status


def _fallback_list(values: list[str]) -> list[str]:
    cleaned = [value for value in values if value.strip()]
    return cleaned or [NOT_SPECIFIED]


def _insufficient_context_plan(
    *,
    user_question: str,
    generated_answer: GeneratedAnswer,
) -> ProcedurePlan:
    return ProcedurePlan(
        title=user_question,
        summary=generated_answer.explanation,
        status=WorkflowStatus.NEEDS_MORE_INFORMATION,
        steps=[],
        required_documents=[NOT_SPECIFIED],
        estimated_timelines=[NOT_SPECIFIED],
        potential_blockers=["Important information is missing or requires official confirmation."],
        next_recommended_action="Obtain additional official information before starting the procedure.",
        source_references=generated_answer.cited_sources,
        missing_information=["Additional official information is required."],
    )
