"""End-to-end procedure orchestration for the FastAPI layer."""

from __future__ import annotations

from typing import Any

from backend.clarification.clarification_engine import ClarificationEngine
from backend.clarification.intent_classifier import IntentClassifier
from backend.generation.answer_generator import GroundedAnswerGenerator
from backend.location.canton_resolver import CantonResolver
from backend.memory.memory_service import MemoryService
from backend.models.clarification import ClarificationQuestion
from backend.models.memory import SavedProcedure
from backend.models.nationality import NationalityCategory, ResolvedCase
from backend.models.planner import ProcedurePlan
from backend.models.reranking import RerankedChunk
from backend.models.retrieval import HybridRetrievalResult, RetrievedChunk
from backend.models.user_profile import UserProfile
from backend.nationality.answer_validator import validate_generated_answer
from backend.nationality.resolver import (
    build_resolved_case,
    extract_current_turn_profile_updates,
)
from backend.orchestration.models import (
    ProcedureQueryRequest,
    ProcedureQueryResponse,
    ProcedureResponseState,
    SourceReference,
)
from backend.planners.workflow_planner import WorkflowPlanner
from backend.retrieval.hybrid import HybridRetriever
from backend.synchronizer.source_coverage import SourceCoverageService
from backend.synchronizer.regions import REGIONS


class OrchestrationError(Exception):
    """Base orchestration error."""


class UserNotFoundError(OrchestrationError):
    """Requested user does not exist."""


class ProcedureNotFoundError(OrchestrationError):
    """Requested procedure does not exist."""


class ProcedureOwnershipError(OrchestrationError):
    """Requested procedure belongs to another user."""


class CantonResolutionError(OrchestrationError):
    """City cannot be deterministically resolved to a canton."""


class ProcedureOrchestrator:
    """Coordinate Phases 4-7 into one procedure workflow."""

    def __init__(
        self,
        *,
        memory_service: MemoryService,
        intent_classifier: IntentClassifier,
        clarification_engine: ClarificationEngine,
        hybrid_retriever: HybridRetriever,
        reranker: Any,
        answer_generator: GroundedAnswerGenerator,
        workflow_planner: WorkflowPlanner,
        canton_resolver: CantonResolver,
        source_coverage_service: SourceCoverageService | None = None,
        default_retrieval_top_k: int = 10,
        default_rerank_top_k: int = 5,
    ) -> None:
        self._memory_service = memory_service
        self._intent_classifier = intent_classifier
        self._clarification_engine = clarification_engine
        self._hybrid_retriever = hybrid_retriever
        self._reranker = reranker
        self._answer_generator = answer_generator
        self._workflow_planner = workflow_planner
        self._canton_resolver = canton_resolver
        self._source_coverage_service = source_coverage_service
        self._default_retrieval_top_k = default_retrieval_top_k
        self._default_rerank_top_k = default_rerank_top_k

    def handle_query(self, request: ProcedureQueryRequest) -> ProcedureQueryResponse:
        """Run the complete clarification-first procedure workflow."""

        user_id = self._resolve_user_id(request)
        existing_procedure = self._validate_procedure_ownership(
            user_id=user_id,
            procedure_id=request.procedure_id,
        )
        current_turn_updates = extract_current_turn_profile_updates(request.question)
        explicit_updates = request.profile_updates
        runtime_updates = {**current_turn_updates, **explicit_updates}
        saved_profile_fields = self._persist_confirmed_profile_updates(
            user_id=user_id,
            profile_updates=explicit_updates,
            confirmed_fields=request.confirmed_profile_fields,
        )
        stored_profile = self._memory_service.build_user_profile(user_id)
        runtime_profile = _merge_profile_updates(stored_profile, runtime_updates)
        runtime_profile, city_questions = self._resolve_city_to_canton(
            user_id=user_id,
            profile=runtime_profile,
            profile_updates=runtime_updates,
            confirmed_fields=request.confirmed_profile_fields,
            saved_profile_fields=saved_profile_fields,
        )

        detected_intent = self._intent_classifier.classify(request.question)
        resolved_case = build_resolved_case(
            profile=runtime_profile,
            intent=detected_intent.intent,
            question=request.question,
        )
        runtime_profile = _apply_resolved_case_to_profile(runtime_profile, resolved_case)
        nationality_questions = _nationality_clarification_questions(
            resolved_case=resolved_case,
            intent=detected_intent.intent,
        )
        clarification = self._clarification_engine.evaluate(
            user_question=request.question,
            detected_intent=detected_intent,
            user_profile=runtime_profile,
        )
        clarification_questions = [
            *city_questions,
            *nationality_questions,
            *clarification.clarification_questions,
        ]
        clarification_questions = _dedupe_questions(clarification_questions)
        missing_fields = [
            *[question.field for question in city_questions],
            *[question.field for question in nationality_questions],
            *clarification.missing_fields,
        ]
        missing_fields = list(dict.fromkeys(missing_fields))

        if clarification_questions:
            if existing_procedure is not None:
                self._memory_service.record_interaction(
                    procedure_id=existing_procedure.id,
                    interaction_type="clarification_requested",
                    summary="Clarification requested before retrieval.",
                    structured_payload={"missing_fields": missing_fields},
                )
            return ProcedureQueryResponse(
                user_id=user_id,
                procedure_id=existing_procedure.id if existing_procedure else None,
                intent=detected_intent.intent,
                state=ProcedureResponseState.CLARIFICATION_REQUIRED,
                needs_clarification=True,
                clarification_questions=clarification_questions,
                missing_fields=missing_fields,
                answer=None,
                plan=None,
                sources=[],
                confidence=None,
                insufficient_context=False,
                saved_profile_fields=saved_profile_fields,
                workflow_status=existing_procedure.status if existing_procedure else None,
            )

        retrieval_query = _build_retrieval_query(
            question=request.question,
            intent=detected_intent.intent,
            profile=runtime_profile,
        )
        requested_region = _normalize_canton_region(runtime_profile.intended_canton)
        self._refresh_sources_before_retrieval(
            intent=detected_intent.intent,
            requested_region=requested_region,
        )
        retrieval_result = self._hybrid_retriever.retrieve(
            retrieval_query,
            top_k=request.retrieval_top_k or self._default_retrieval_top_k,
        )
        retrieval_result = _filter_retrieval_result_by_region(
            retrieval_result,
            requested_region=requested_region,
        )
        retrieval_result = _filter_retrieval_result_by_nationality(
            retrieval_result,
            resolved_case=resolved_case,
        )
        rerank_result = self._reranker.rerank(
            query=retrieval_query,
            retrieved_chunks=retrieval_result.merged_results,
            top_k=request.rerank_top_k or self._default_rerank_top_k,
        )
        answer = self._answer_generator.generate(
            user_question=request.question,
            detected_intent=detected_intent,
            user_profile=runtime_profile,
            reranked_chunks=rerank_result.chunks,
        )
        answer = _add_missing_canton_coverage_note(
            answer=answer,
            requested_region=requested_region,
            chunks=rerank_result.chunks,
        )
        answer = validate_generated_answer(
            answer=answer,
            resolved_case=resolved_case,
            chunks=rerank_result.chunks,
        )
        plan = None
        saved_procedure = existing_procedure
        if not answer.insufficient_context:
            plan = self._workflow_planner.create_plan(
                user_question=request.question,
                detected_intent=detected_intent,
                user_profile=runtime_profile,
                generated_answer=answer,
                reranked_chunks=rerank_result.chunks,
            )
            saved_procedure = self._save_or_update_procedure(
                user_id=user_id,
                existing_procedure=existing_procedure,
                intent=detected_intent.intent,
                plan=plan,
            )
            self._memory_service.record_interaction(
                procedure_id=saved_procedure.id,
                interaction_type="answer_generated",
                summary="Generated grounded answer and workflow plan.",
                structured_payload={
                    "confidence": answer.confidence,
                    "workflow_status": plan.status.value,
                },
            )

        return ProcedureQueryResponse(
            user_id=user_id,
            procedure_id=saved_procedure.id if saved_procedure else None,
            intent=detected_intent.intent,
            state=(
                ProcedureResponseState.INSUFFICIENT_CONTEXT
                if answer.insufficient_context
                else ProcedureResponseState.ANSWERED
            ),
            needs_clarification=False,
            clarification_questions=[],
            missing_fields=[],
            answer=answer,
            plan=plan,
            sources=_source_references(rerank_result.chunks),
            confidence=answer.confidence,
            insufficient_context=answer.insufficient_context,
            saved_profile_fields=saved_profile_fields,
            workflow_status=plan.status if plan else None,
        )

    def _resolve_user_id(self, request: ProcedureQueryRequest) -> str:
        if request.user_id:
            user = self._memory_service.get_user(request.user_id)
            if user is None:
                raise UserNotFoundError("User not found.")
            self._memory_service.update_last_active_at(user.id)
            return user.id
        if request.external_user_key:
            return self._memory_service.get_or_create_user(
                external_user_key=request.external_user_key
            ).id
        return self._memory_service.create_user().id

    def _validate_procedure_ownership(
        self,
        *,
        user_id: str,
        procedure_id: str | None,
    ) -> SavedProcedure | None:
        if procedure_id is None:
            return None
        procedure = self._memory_service.get_procedure(procedure_id)
        if procedure is None:
            raise ProcedureNotFoundError("Procedure not found.")
        if procedure.user_id != user_id:
            raise ProcedureOwnershipError("Procedure belongs to another user.")
        return procedure

    def _persist_confirmed_profile_updates(
        self,
        *,
        user_id: str,
        profile_updates: dict[str, Any],
        confirmed_fields: list[str],
    ) -> list[str]:
        confirmed = {
            field: profile_updates[field]
            for field in confirmed_fields
            if field in profile_updates
        }
        confirmed.update(_derived_confirmed_nationality_facts(confirmed))
        if not confirmed:
            return []
        self._memory_service.save_confirmed_profile_facts(
            user_id=user_id,
            facts=confirmed,
            source="user_confirmed",
        )
        return list(confirmed)

    def _resolve_city_to_canton(
        self,
        *,
        user_id: str,
        profile: UserProfile,
        profile_updates: dict[str, Any],
        confirmed_fields: list[str],
        saved_profile_fields: list[str],
    ) -> tuple[UserProfile, list[ClarificationQuestion]]:
        city_was_updated = bool(profile_updates.get("intended_city"))
        if city_was_updated:
            resolution = self._canton_resolver.resolve(profile.intended_city)
            if resolution.is_resolved and resolution.canton is not None:
                updates = {
                    "intended_city": resolution.city,
                    "intended_canton": resolution.canton,
                }
                profile = profile.model_copy(update=updates)
                if "intended_city" in confirmed_fields:
                    self._memory_service.save_confirmed_profile_facts(
                        user_id=user_id,
                        facts=updates,
                        source="user_confirmed",
                    )
                    for field in updates:
                        if field not in saved_profile_fields:
                            saved_profile_fields.append(field)
                return profile, []
            if resolution.needs_clarification:
                return profile, [
                    ClarificationQuestion(
                        field="intended_canton",
                        question=(
                            "Which Swiss canton should be used for this city or municipality?"
                        ),
                    )
                ]

        if profile.intended_canton:
            return profile, []
        if not profile.intended_city:
            return profile, []

        resolution = self._canton_resolver.resolve(profile.intended_city)
        if resolution.is_resolved and resolution.canton is not None:
            updates = {
                "intended_city": resolution.city,
                "intended_canton": resolution.canton,
            }
            profile = profile.model_copy(update=updates)
            if "intended_city" in confirmed_fields:
                self._memory_service.save_confirmed_profile_facts(
                    user_id=user_id,
                    facts=updates,
                    source="user_confirmed",
                )
                for field in updates:
                    if field not in saved_profile_fields:
                        saved_profile_fields.append(field)
            return profile, []

        if resolution.needs_clarification:
            return profile, [
                ClarificationQuestion(
                    field="intended_canton",
                    question=(
                        "Which Swiss canton should be used for this city or municipality?"
                    ),
                )
            ]
        return profile, []

    def _save_or_update_procedure(
        self,
        *,
        user_id: str,
        existing_procedure: SavedProcedure | None,
        intent: str,
        plan: ProcedurePlan,
    ) -> SavedProcedure:
        if existing_procedure is None:
            return self._memory_service.save_procedure_plan(
                user_id=user_id,
                intent=intent,
                plan=plan,
                current_step=1 if plan.steps else None,
            )
        return self._memory_service.update_procedure_plan(
            procedure_id=existing_procedure.id,
            plan=plan,
        )

    def _refresh_sources_before_retrieval(
        self,
        *,
        intent: str,
        requested_region: str | None,
    ) -> None:
        if self._source_coverage_service is None:
            return
        result = self._source_coverage_service.refresh_for_case(
            intent=intent,
            requested_region=requested_region,
        )
        if result.refresh_succeeded:
            refresh = getattr(self._hybrid_retriever, "refresh", None)
            if callable(refresh):
                refresh()


def _merge_profile_updates(
    profile: UserProfile,
    profile_updates: dict[str, Any],
) -> UserProfile:
    allowed_fields = set(UserProfile.model_fields)
    valid_updates = {
        field: value for field, value in profile_updates.items() if field in allowed_fields
    }
    return profile.model_copy(update=valid_updates)


def _dedupe_questions(
    questions: list[ClarificationQuestion],
) -> list[ClarificationQuestion]:
    deduped: dict[str, ClarificationQuestion] = {}
    for question in questions:
        deduped.setdefault(question.field, question)
    return list(deduped.values())


def _apply_resolved_case_to_profile(
    profile: UserProfile,
    resolved_case: ResolvedCase,
) -> UserProfile:
    updates: dict[str, Any] = {
        "nationality_category": resolved_case.nationality_category.value,
        "eu_efta_citizen": resolved_case.nationality_category is NationalityCategory.EU_EFTA,
        "third_country_national": resolved_case.nationality_category is NationalityCategory.THIRD_COUNTRY,
        "is_swiss": resolved_case.nationality_category is NationalityCategory.SWISS,
        "is_uk_national": resolved_case.nationality_category is NationalityCategory.UK,
        "immigration_regime": resolved_case.nationality_category.value,
    }
    if resolved_case.citizenships:
        updates["citizenships"] = [
            citizenship.country_code for citizenship in resolved_case.citizenships
        ]
    if len(resolved_case.citizenships) == 1:
        citizenship = resolved_case.citizenships[0]
        updates.update(
            {
                "nationality": citizenship.country_name,
                "country_code": citizenship.country_code,
            }
        )
    if resolved_case.current_country_code:
        updates["current_country_code"] = resolved_case.current_country_code
    if resolved_case.current_country:
        updates["current_country"] = resolved_case.current_country
    return profile.model_copy(update=updates)


def _derived_confirmed_nationality_facts(
    confirmed: dict[str, Any],
) -> dict[str, Any]:
    nationality = confirmed.get("nationality")
    if not isinstance(nationality, str) or not nationality.strip():
        return {}
    case = build_resolved_case(
        profile=UserProfile(nationality=nationality),
        intent="immigration",
        question="",
    )
    if len(case.citizenships) != 1:
        return {}
    citizenship = case.citizenships[0]
    return {
        "nationality": citizenship.country_name,
        "citizenships": [citizenship.country_code],
        "country_code": citizenship.country_code,
        "nationality_category": citizenship.nationality_category.value,
        "eu_efta_citizen": citizenship.nationality_category is NationalityCategory.EU_EFTA,
        "third_country_national": citizenship.nationality_category is NationalityCategory.THIRD_COUNTRY,
        "is_swiss": citizenship.nationality_category is NationalityCategory.SWISS,
        "is_uk_national": citizenship.nationality_category is NationalityCategory.UK,
        "immigration_regime": citizenship.nationality_category.value,
    }


def _nationality_clarification_questions(
    *,
    resolved_case: ResolvedCase,
    intent: str,
) -> list[ClarificationQuestion]:
    if intent not in {"immigration", "residence_permit", "work_permit", "citizenship"}:
        return []
    if "primary_citizenship" in resolved_case.unresolved_fields:
        countries = " and ".join(
            f"{citizenship.country_name} ({citizenship.country_code})"
            for citizenship in resolved_case.citizenships
        )
        return [
            ClarificationQuestion(
                field="nationality",
                question=(
                    f"You mentioned both {countries}. Which citizenship or passport "
                    "will you use for this Swiss procedure?"
                ),
            )
        ]
    if resolved_case.nationality_category is NationalityCategory.SPECIAL_OR_UNKNOWN:
        return [
            ClarificationQuestion(
                field="nationality",
                question="Which country or countries are you a citizen of?",
            )
        ]
    return []


def _build_retrieval_query(
    *,
    question: str,
    intent: str,
    profile: UserProfile,
) -> str:
    relevant_fields = [
        "nationality",
        "country_code",
        "nationality_category",
        "current_country",
        "current_country_code",
        "intended_city",
        "intended_canton",
        "purpose_of_stay",
        "employment_status",
        "profession",
        "current_permit",
        "driving_licence_country",
        "swiss_residence_start_date",
        "planned_duration",
    ]
    facts = []
    data = profile.model_dump(exclude_none=True)
    for field in relevant_fields:
        if field in data:
            facts.append(f"{field}: {data[field]}")
    context = "; ".join(facts)
    return f"{question}\nIntent: {intent}\nConfirmed context: {context}".strip()


def _normalize_canton_region(canton: str | None) -> str | None:
    if canton is None or not canton.strip():
        return None
    normalized = canton.strip().lower()
    if normalized in REGIONS:
        return normalized
    for code, region in REGIONS.items():
        names = {region.name.lower()}
        if region.name.lower() == "zurich":
            names.add("zürich")
        if normalized in names:
            return code
    return None


def _filter_retrieval_result_by_region(
    result: HybridRetrievalResult,
    *,
    requested_region: str | None,
) -> HybridRetrievalResult:
    if requested_region is None or requested_region == "federal":
        return result
    allowed_regions = {"federal", requested_region}
    return result.model_copy(
        update={
            "vector_results": _filter_chunks_by_region(
                result.vector_results,
                allowed_regions=allowed_regions,
            ),
            "bm25_results": _filter_chunks_by_region(
                result.bm25_results,
                allowed_regions=allowed_regions,
            ),
            "merged_results": _filter_chunks_by_region(
                result.merged_results,
                allowed_regions=allowed_regions,
            ),
        }
    )


def _filter_retrieval_result_by_nationality(
    result: HybridRetrievalResult,
    *,
    resolved_case: ResolvedCase,
) -> HybridRetrievalResult:
    if resolved_case.nationality_category is NationalityCategory.SPECIAL_OR_UNKNOWN:
        return result.model_copy(
            update={
                "vector_results": [],
                "bm25_results": [],
                "merged_results": [],
            }
        )
    allowed = resolved_case.applicable_nationality_categories
    return result.model_copy(
        update={
            "vector_results": _filter_chunks_by_nationality(
                result.vector_results,
                allowed_categories=allowed,
            ),
            "bm25_results": _filter_chunks_by_nationality(
                result.bm25_results,
                allowed_categories=allowed,
            ),
            "merged_results": _filter_chunks_by_nationality(
                result.merged_results,
                allowed_categories=allowed,
            ),
        }
    )


def _filter_chunks_by_region(
    chunks: list[RetrievedChunk],
    *,
    allowed_regions: set[str],
) -> list[RetrievedChunk]:
    return [
        chunk
        for chunk in chunks
        if chunk.metadata.region.strip().lower() in allowed_regions
    ]


def _filter_chunks_by_nationality(
    chunks: list[RetrievedChunk],
    *,
    allowed_categories: set[str],
) -> list[RetrievedChunk]:
    return [
        chunk
        for chunk in chunks
        if _chunk_applicability(chunk) & allowed_categories
    ]


def _chunk_applicability(chunk: RetrievedChunk | RerankedChunk) -> set[str]:
    metadata = chunk.metadata.model_dump()
    raw = metadata.get("nationality_categories") or metadata.get("applicable_person_categories")
    if raw:
        if isinstance(raw, str):
            return {item.strip().lower() for item in raw.split(",") if item.strip()}
        if isinstance(raw, list):
            return {str(item).strip().lower() for item in raw if str(item).strip()}
    source = chunk.metadata.source.lower()
    eu_efta_sources = {
        "b_permit_gainful_activity.pdf",
        "b_permit_sem.pdf",
        "family_reunification.pdf",
        "free_movement_eu_efta.pdf",
        "residence_permits_overview.pdf",
        "without_gainful_activity.pdf",
    }
    if source in eu_efta_sources or "free_movement" in source or "eu_efta" in source:
        return {"eu_efta"}
    return {"all"}


def _add_missing_canton_coverage_note(
    *,
    answer: Any,
    requested_region: str | None,
    chunks: list[RerankedChunk],
) -> Any:
    if requested_region is None or requested_region == "federal":
        return answer
    has_requested_region = any(
        chunk.metadata.region.strip().lower() == requested_region
        for chunk in chunks
    )
    if has_requested_region:
        return answer
    note = (
        f"Canton-specific official source coverage for {requested_region.upper()} "
        "was not found in the retrieved local knowledge base. The answer may include "
        "federal information only."
    )
    if note in answer.important_notes:
        return answer
    return answer.model_copy(update={"important_notes": [*answer.important_notes, note]})


def _source_references(chunks: list[RerankedChunk]) -> list[SourceReference]:
    references: dict[tuple[str, int | None, str | None], SourceReference] = {}
    for chunk in chunks:
        key = (chunk.metadata.source, chunk.metadata.page, chunk.metadata.region)
        references.setdefault(
            key,
            SourceReference(
                chunk_id=chunk.chunk_id,
                source=chunk.metadata.source,
                page=chunk.metadata.page,
                region=chunk.metadata.region,
                retrieval_source=chunk.retrieval_source,
                rerank_score=chunk.rerank_score,
            ),
        )
    return list(references.values())
