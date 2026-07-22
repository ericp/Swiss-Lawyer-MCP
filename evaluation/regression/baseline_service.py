"""Baseline summary generation with explicit approval controls."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from evaluation.models import EvaluationRunResult, EvaluationStatus
from evaluation.regression.fingerprint import build_knowledge_base_fingerprint
from evaluation.regression.models import BaselineSummary


class BaselineGenerationService:
    """Create committed-safe baseline summaries from evaluation runs."""

    def create_baseline(
        self,
        *,
        run_result: EvaluationRunResult,
        output_path: Path,
        approval_note: str,
        force: bool = False,
        knowledge_base_fingerprint: dict[str, Any] | None = None,
        selected_case_ids: list[str] | None = None,
    ) -> BaselineSummary:
        """Create a baseline summary and write it only when explicitly allowed."""

        if not approval_note.strip():
            raise ValueError("A human approval note is required to create a baseline")
        if output_path.exists() and not force:
            raise FileExistsError(f"Baseline already exists: {output_path}")

        failed_cases = [
            result.case_id
            for result in run_result.case_results
            if result.execution_status is EvaluationStatus.FAILED or result.error
        ]
        notes = approval_note
        if failed_cases:
            notes = f"WARNING: baseline generated from a run with failing cases {failed_cases}. {approval_note}"

        selected_case_ids = selected_case_ids or [
            result.case_id
            for result in run_result.case_results
            if any(metric.get("severity") == "critical" for metric in _metrics_as_dicts(result.metrics))
        ]
        selected_results = {
            case_id: [
                metric
                for metric in _metrics_as_dicts(
                    next(result for result in run_result.case_results if result.case_id == case_id).metrics
                )
                if metric.get("metric_name")
            ]
            for case_id in selected_case_ids
            if any(result.case_id == case_id for result in run_result.case_results)
        }

        baseline = BaselineSummary(
            baseline_id=f"{run_result.metadata.dataset_name}_{run_result.metadata.dataset_version}",
            source_run_id=run_result.metadata.run_id,
            dataset_name=run_result.metadata.dataset_name,
            dataset_version=run_result.metadata.dataset_version,
            creation_date=date.today(),
            git_commit=run_result.metadata.git_commit,
            model_configuration={
                "embedding_model": run_result.metadata.embedding_model,
                "generation_model": run_result.metadata.generation_model,
                "reranker_model": run_result.metadata.reranker_model,
            },
            prompt_hashes={},
            source_registry_version=(knowledge_base_fingerprint or {}).get("source_registry_version"),
            knowledge_base_fingerprint=knowledge_base_fingerprint or build_knowledge_base_fingerprint(),
            aggregate_metrics=run_result.aggregate_metrics,
            selected_critical_case_results=selected_results,
            approved_notes=notes,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(baseline.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return baseline


def _metrics_as_dicts(metrics: list[Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for metric in metrics:
        output.append(metric.model_dump(mode="json") if hasattr(metric, "model_dump") else dict(metric))
    return output
