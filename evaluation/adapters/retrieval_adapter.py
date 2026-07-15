"""Evaluation adapter for vector, BM25, and hybrid retrieval."""

from __future__ import annotations

from typing import Any

from evaluation.adapters.common import normalize, timed
from evaluation.config import ExecutionMode
from evaluation.models import EvaluationCase, EvaluationCaseResult, EvaluationStatus


class RetrievalEvaluationAdapter:
    """Run production retrieval components and normalize result sets."""

    def __init__(
        self,
        *,
        vector_retriever: Any | None = None,
        bm25_retriever: Any | None = None,
        hybrid_retriever: Any | None = None,
        execution_mode: ExecutionMode = ExecutionMode.OFFLINE,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._bm25_retriever = bm25_retriever
        self._hybrid_retriever = hybrid_retriever
        self._execution_mode = execution_mode

    def evaluate(
        self,
        case: EvaluationCase,
        *,
        vector_top_k: int = 10,
        bm25_top_k: int = 10,
        hybrid_top_k: int = 10,
    ) -> EvaluationCaseResult:
        timings: dict[str, float] = {}
        if self._execution_mode is ExecutionMode.OFFLINE and not self._has_dependencies():
            outputs = case.offline_outputs.get("retrieval", {})
            return EvaluationCaseResult(
                case_id=case.id,
                question=case.question,
                execution_status=EvaluationStatus.PASSED,
                vector_results=outputs.get("vector_results", []),
                bm25_results=outputs.get("bm25_results", []),
                hybrid_results=outputs.get("hybrid_results", []),
                timings=timings,
                intermediate_outputs={"retrieval_mode": "offline"},
            )

        with timed("vector_retrieval", timings):
            vector_results = (
                self._vector_retriever.retrieve(case.question, top_k=vector_top_k)
                if self._vector_retriever is not None
                else []
            )
        with timed("bm25_retrieval", timings):
            bm25_results = (
                self._bm25_retriever.retrieve(case.question, top_k=bm25_top_k)
                if self._bm25_retriever is not None
                else []
            )
        with timed("hybrid_retrieval", timings):
            hybrid_result = (
                self._hybrid_retriever.retrieve(case.question, top_k=hybrid_top_k)
                if self._hybrid_retriever is not None
                else None
            )
        return EvaluationCaseResult(
            case_id=case.id,
            question=case.question,
            execution_status=EvaluationStatus.PASSED,
            vector_results=normalize(vector_results),
            bm25_results=normalize(bm25_results),
            hybrid_results=normalize(
                hybrid_result.merged_results if hybrid_result is not None else []
            ),
            timings=timings,
            intermediate_outputs={"hybrid_result": normalize(hybrid_result)},
        )

    def _has_dependencies(self) -> bool:
        return any(
            dependency is not None
            for dependency in [
                self._vector_retriever,
                self._bm25_retriever,
                self._hybrid_retriever,
            ]
        )
