"""Evaluation adapter for reranking."""

from __future__ import annotations

from typing import Any

from evaluation.adapters.common import normalize, timed
from evaluation.config import ExecutionMode
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class RerankingEvaluationAdapter:
    """Run the production reranker over supplied hybrid candidates."""

    def __init__(
        self,
        *,
        reranker: Any | None = None,
        execution_mode: ExecutionMode = ExecutionMode.OFFLINE,
    ) -> None:
        self._reranker = reranker
        self._execution_mode = execution_mode

    def evaluate(
        self,
        case: EvaluationCase,
        *,
        hybrid_candidates: list[Any] | None = None,
        top_k: int = 5,
    ) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        if self._execution_mode is ExecutionMode.OFFLINE and self._reranker is None:
            outputs = case.offline_outputs.get("reranking", {})
            return EvaluationCaseResult(
                case_id=case.id,
                question=case.question,
                execution_status=EvaluationStatus.PASSED,
                reranked_results=outputs.get("reranked_results", []),
                timings=timings,
                intermediate_outputs={"reranking_mode": "offline"},
            )
        with timed("reranking", timings):
            result = self._reranker.rerank(
                query=case.question,
                retrieved_chunks=hybrid_candidates or [],
                top_k=top_k,
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            reranked_results=normalize(result.chunks),
            timings=timings,
            intermediate_outputs={"rerank_result": normalize(result)},
        )
