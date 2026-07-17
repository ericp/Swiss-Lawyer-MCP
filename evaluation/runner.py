"""Evaluation runner and artifact writer."""

from __future__ import annotations

import importlib.metadata
import json
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from evaluation.adapters.clarification_adapter import ClarificationEvaluationAdapter
from evaluation.adapters.common import normalize
from evaluation.adapters.end_to_end_adapter import EndToEndEvaluationAdapter
from evaluation.adapters.generation_adapter import GenerationEvaluationAdapter
from evaluation.adapters.planner_adapter import PlannerEvaluationAdapter
from evaluation.adapters.reranking_adapter import RerankingEvaluationAdapter
from evaluation.adapters.retrieval_adapter import RetrievalEvaluationAdapter
from evaluation.config import EvaluationConfig
from evaluation.datasets.loader import load_jsonl_dataset
from evaluation.metrics.aggregate import compute_run_metrics
from evaluation.models import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationRunMetadata,
    EvaluationRunResult,
    EvaluationStatus,
)


class EvaluationRunner:
    """Execute evaluation cases and persist raw run artifacts."""

    def __init__(
        self,
        *,
        config: EvaluationConfig,
        cases: list[EvaluationCase] | None = None,
        clarification_adapter: ClarificationEvaluationAdapter | None = None,
        retrieval_adapter: RetrievalEvaluationAdapter | None = None,
        reranking_adapter: RerankingEvaluationAdapter | None = None,
        generation_adapter: GenerationEvaluationAdapter | None = None,
        planner_adapter: PlannerEvaluationAdapter | None = None,
        end_to_end_adapter: EndToEndEvaluationAdapter | None = None,
    ) -> None:
        self.config = config
        self._cases = cases
        self._clarification_adapter = clarification_adapter or ClarificationEvaluationAdapter()
        self._retrieval_adapter = retrieval_adapter or RetrievalEvaluationAdapter(
            execution_mode=config.execution_mode
        )
        self._reranking_adapter = reranking_adapter or RerankingEvaluationAdapter(
            execution_mode=config.execution_mode
        )
        self._generation_adapter = generation_adapter or GenerationEvaluationAdapter(
            execution_mode=config.execution_mode
        )
        self._planner_adapter = planner_adapter or PlannerEvaluationAdapter(
            execution_mode=config.execution_mode
        )
        self._end_to_end_adapter = end_to_end_adapter

    def run(self) -> EvaluationRunResult:
        """Run selected cases and persist artifacts."""

        random.seed(self.config.random_seed)
        metadata = self._metadata()
        warnings: list[str] = []
        errors: list[str] = []
        case_results: list[EvaluationCaseResult] = []
        selected_cases = self._select_cases(self._load_cases())

        for case in selected_cases:
            try:
                case_results.append(self._run_case(case))
            except Exception as error:
                result = EvaluationCaseResult(
                    case_id=case.id,
                    question=case.question,
                    execution_status=EvaluationStatus.FAILED,
                    error=_sanitize_error(error),
                )
                case_results.append(result)
                errors.append(f"{case.id}: {result.error}")
                if self.config.fail_fast:
                    break

        metadata.completed_at = datetime.now(timezone.utc)
        metric_payload = compute_run_metrics(selected_cases, case_results, config=self.config)
        for result in case_results:
            result.metrics = metric_payload["case_level_metrics"].get(result.case_id, [])
        run_result = EvaluationRunResult(
            metadata=metadata,
            case_results=case_results,
            case_level_metrics=metric_payload["case_level_metrics"],
            aggregate_metrics={
                **metric_payload["aggregate_metrics"],
                "execution": {
                    "case_count": len(case_results),
                    "failed_count": sum(
                        result.execution_status is EvaluationStatus.FAILED
                        for result in case_results
                    ),
                },
            },
            metric_applicability_counts=metric_payload["metric_applicability_counts"],
            metric_warnings=metric_payload["metric_warnings"],
            judge_metadata=metric_payload["judge_metadata"],
            timing_summary=metric_payload["timing_summary"],
            warnings=warnings,
            errors=errors,
        )
        self._persist_artifacts(run_result)
        return run_result

    def _run_case(self, case: EvaluationCase) -> EvaluationCaseResult:
        result = self._clarification_adapter.evaluate(case)
        if result.clarification_result and result.clarification_result.get("needs_clarification"):
            return result

        retrieval = self._retrieval_adapter.evaluate(
            case,
            vector_top_k=self.config.retrieval_top_k,
            bm25_top_k=self.config.bm25_top_k,
            hybrid_top_k=self.config.retrieval_top_k,
        )
        result.vector_results = retrieval.vector_results
        result.bm25_results = retrieval.bm25_results
        result.hybrid_results = retrieval.hybrid_results
        result.timings.update(retrieval.timings)
        if self.config.save_intermediate_outputs:
            result.intermediate_outputs["retrieval"] = retrieval.intermediate_outputs

        reranking = self._reranking_adapter.evaluate(
            case,
            hybrid_candidates=case.offline_outputs.get("hybrid_candidates", result.hybrid_results),
            top_k=self.config.rerank_top_k,
        )
        result.reranked_results = reranking.reranked_results
        result.timings.update(reranking.timings)
        if self.config.save_intermediate_outputs:
            result.intermediate_outputs["reranking"] = reranking.intermediate_outputs

        if self.config.generation_enabled:
            generation = self._generation_adapter.evaluate(case)
            result.generated_answer = generation.generated_answer
            result.sources = generation.sources
            result.timings.update(generation.timings)
            if self.config.save_intermediate_outputs:
                result.intermediate_outputs["generation"] = generation.intermediate_outputs

        if self.config.planner_enabled:
            planning = self._planner_adapter.evaluate(
                case,
                generated_answer=result.generated_answer,
            )
            result.procedure_plan = planning.procedure_plan
            result.timings.update(planning.timings)
            if self.config.save_intermediate_outputs:
                result.intermediate_outputs["planner"] = planning.intermediate_outputs

        if self._end_to_end_adapter is not None:
            end_to_end = self._end_to_end_adapter.evaluate(case)
            result.intermediate_outputs["end_to_end"] = end_to_end.intermediate_outputs
            result.timings.update(end_to_end.timings)

        return result

    def _load_cases(self) -> list[EvaluationCase]:
        if self._cases is not None:
            return self._cases
        if self.config.dataset_path is None:
            return []
        text = self.config.dataset_path.read_text(encoding="utf-8")
        if self.config.dataset_path.suffix == ".jsonl":
            return load_jsonl_dataset(self.config.dataset_path).cases
        payload = json.loads(text)
        items = payload.get("cases", payload) if isinstance(payload, dict) else payload
        return [EvaluationCase.model_validate(item) for item in items]

    def _select_cases(self, cases: Iterable[EvaluationCase]) -> list[EvaluationCase]:
        selected = list(cases)
        if self.config.case_ids:
            allowed_ids = set(self.config.case_ids)
            selected = [case for case in selected if case.id in allowed_ids]
        if self.config.tags:
            allowed_tags = set(self.config.tags)
            selected = [
                case for case in selected if allowed_tags.intersection(case.tags)
            ]
        if self.config.max_cases is not None:
            selected = selected[: self.config.max_cases]
        return selected

    def _metadata(self) -> EvaluationRunMetadata:
        return EvaluationRunMetadata(
            run_name=self.config.run_name,
            dataset_name=self.config.dataset_name,
            dataset_version=self.config.dataset_version,
            execution_mode=self.config.execution_mode,
            git_commit=_git_commit(),
            dependency_information=_dependency_information(),
            embedding_model=None,
            generation_model=None,
            reranker_model=None,
            evaluation_configuration=self.config,
        )

    def _persist_artifacts(self, run_result: EvaluationRunResult) -> None:
        run_dir = self.config.output_directory / run_result.metadata.run_id
        if run_dir.exists() and not self.config.overwrite_existing_run:
            raise FileExistsError(f"Evaluation artifact directory already exists: {run_dir}")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_metadata.json").write_text(
            run_result.metadata.model_dump_json(indent=2),
            encoding="utf-8",
        )
        (run_dir / "config.json").write_text(
            self.config.model_dump_json(indent=2),
            encoding="utf-8",
        )
        with (run_dir / "case_results.jsonl").open("w", encoding="utf-8") as file:
            for result in run_result.case_results:
                file.write(result.model_dump_json() + "\n")
        (run_dir / "warnings.json").write_text(
            json.dumps(run_result.warnings, indent=2),
            encoding="utf-8",
        )
        (run_dir / "errors.json").write_text(
            json.dumps(run_result.errors, indent=2),
            encoding="utf-8",
        )
        if self.config.save_intermediate_outputs:
            intermediate_dir = run_dir / "intermediate_outputs"
            intermediate_dir.mkdir(exist_ok=True)
            for result in run_result.case_results:
                (intermediate_dir / f"{result.case_id}.json").write_text(
                    json.dumps(normalize(result.intermediate_outputs), indent=2),
                    encoding="utf-8",
                )
        (run_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "aggregate_metrics": normalize(run_result.aggregate_metrics),
                    "metric_applicability_counts": normalize(run_result.metric_applicability_counts),
                    "metric_warnings": run_result.metric_warnings,
                    "judge_metadata": normalize(run_result.judge_metadata),
                    "timing_summary": normalize(run_result.timing_summary),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        with (run_dir / "case_metrics.jsonl").open("w", encoding="utf-8") as file:
            for case_id, metrics in run_result.case_level_metrics.items():
                file.write(json.dumps({"case_id": case_id, "metrics": normalize(metrics)}) + "\n")
        (run_dir / "aggregate_metrics.json").write_text(
            json.dumps(normalize(run_result.aggregate_metrics), indent=2),
            encoding="utf-8",
        )


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except Exception:
        return None


def _dependency_information() -> dict[str, str]:
    packages = ["pydantic", "chromadb", "openai", "fastapi", "SQLAlchemy"]
    versions: dict[str, str] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            continue
    return versions


def _sanitize_error(error: Exception) -> str:
    return (str(error) or error.__class__.__name__)[:500]
