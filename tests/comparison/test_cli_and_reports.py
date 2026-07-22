"""Evaluation CLI and before/after report tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.cli import (
    EXIT_BASELINE_INCOMPATIBLE,
    EXIT_CONFIGURATION_ERROR,
    EXIT_PASSED,
    EXIT_REGRESSION_FAILURE,
    build_parser,
    main,
)
from evaluation.comparison.comparator import EvaluationComparator
from evaluation.comparison.formatter import format_html, format_json, format_markdown, write_comparison_reports
from evaluation.regression.models import MetricDirection, RegressionStatus, RegressionThresholdConfig, ThresholdRule
from tests.regression.helpers import baseline, run_result


def _write_run_artifact(root: Path, metrics: dict[str, float], *, run_name: str = "test") -> Path:
    run = run_result(metrics=metrics)
    run.metadata.run_name = run_name
    run_dir = root / run.metadata.run_id
    run_dir.mkdir(parents=True)
    (run_dir / "run_metadata.json").write_text(run.metadata.model_dump_json(indent=2), encoding="utf-8")
    with (run_dir / "case_results.jsonl").open("w", encoding="utf-8") as file:
        for result in run.case_results:
            file.write(result.model_dump_json() + "\n")
    (run_dir / "aggregate_metrics.json").write_text(json.dumps(run.aggregate_metrics), encoding="utf-8")
    (run_dir / "metrics.json").write_text(
        json.dumps({"aggregate_metrics": run.aggregate_metrics, "metric_applicability_counts": {}}),
        encoding="utf-8",
    )
    (run_dir / "warnings.json").write_text("[]", encoding="utf-8")
    (run_dir / "errors.json").write_text("[]", encoding="utf-8")
    return run_dir


def test_cli_argument_parsing() -> None:
    args = build_parser().parse_args(["run", "--dataset", "smoke/v1", "--mode", "offline", "--tag", "immigration"])

    assert args.command == "run"
    assert args.dataset == "smoke/v1"
    assert args.tag == ["immigration"]


def test_dataset_validation_command() -> None:
    assert main(["validate-datasets"]) == EXIT_PASSED


def test_offline_evaluation_run(tmp_path: Path) -> None:
    exit_code = main([
        "run",
        "--dataset",
        "smoke/v1",
        "--mode",
        "offline",
        "--max-cases",
        "1",
        "--output-dir",
        str(tmp_path),
        "--save-intermediate",
    ])

    assert exit_code == EXIT_PASSED
    assert list(tmp_path.glob("*/run_metadata.json"))


def test_live_mode_requires_confirmation(tmp_path: Path) -> None:
    exit_code = main([
        "run",
        "--dataset",
        "smoke/v1",
        "--mode",
        "live",
        "--max-cases",
        "1",
        "--output-dir",
        str(tmp_path),
    ])

    assert exit_code == EXIT_CONFIGURATION_ERROR


def test_run_listing_and_show_run(tmp_path: Path) -> None:
    run_dir = _write_run_artifact(tmp_path, {"intent_accuracy": 1.0})

    assert main(["list-runs", "--output-dir", str(tmp_path)]) == EXIT_PASSED
    assert main(["show-run", str(run_dir)]) == EXIT_PASSED


def test_before_after_comparison_and_reports(tmp_path: Path) -> None:
    before = _write_run_artifact(tmp_path / "runs", {"intent_accuracy": 0.8}, run_name="before")
    after = _write_run_artifact(tmp_path / "runs", {"intent_accuracy": 0.9}, run_name="after")

    exit_code = main(["compare", "--before", str(before), "--after", str(after), "--output-dir", str(tmp_path / "reports")])

    assert exit_code in {EXIT_PASSED, EXIT_BASELINE_INCOMPATIBLE}
    report_files = list((tmp_path / "reports").glob("*/comparison.json"))
    assert report_files
    report_dir = report_files[0].parent
    assert (report_dir / "comparison.md").exists()
    assert (report_dir / "comparison.html").exists()
    assert (report_dir / "report_metadata.json").exists()


def test_baseline_comparison(tmp_path: Path) -> None:
    after = _write_run_artifact(tmp_path / "runs", {"intent_accuracy": 0.9})
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(baseline(metrics={"intent_accuracy": 0.8}).model_dump_json(indent=2), encoding="utf-8")

    exit_code = main(["compare", "--baseline", str(baseline_path), "--after", str(after), "--output-dir", str(tmp_path / "reports")])

    assert exit_code in {EXIT_PASSED, EXIT_BASELINE_INCOMPATIBLE}


def test_higher_and_lower_is_better_display() -> None:
    thresholds = RegressionThresholdConfig(global_thresholds=[
        ThresholdRule(metric_name="intent_accuracy", direction=MetricDirection.HIGHER_IS_BETTER, minimum=0.8),
        ThresholdRule(metric_name="unsupported_claim_rate", direction=MetricDirection.LOWER_IS_BETTER, maximum=0.05),
    ])
    report = EvaluationComparator(thresholds=thresholds).compare_baseline(
        baseline=baseline(metrics={"intent_accuracy": 0.8, "unsupported_claim_rate": 0.02}),
        after=run_result(metrics={"intent_accuracy": 0.9, "unsupported_claim_rate": 0.01}),
    )

    directions = {delta.metric_name: delta.direction for delta in report.metric_deltas}
    assert directions["intent_accuracy"] is MetricDirection.HIGHER_IS_BETTER
    assert directions["unsupported_claim_rate"] is MetricDirection.LOWER_IS_BETTER


def test_critical_failure_reporting_and_regression_exit(tmp_path: Path) -> None:
    before = _write_run_artifact(tmp_path / "runs", {"unsafe_answer_rate": 0.0})
    after = _write_run_artifact(tmp_path / "runs", {"unsafe_answer_rate": 1.0})

    exit_code = main(["compare", "--before", str(before), "--after", str(after), "--output-dir", str(tmp_path / "reports")])

    assert exit_code == EXIT_REGRESSION_FAILURE
    payload = json.loads(next((tmp_path / "reports").glob("*/comparison.json")).read_text(encoding="utf-8"))
    assert payload["critical_failures"]


def test_report_formatters_include_metadata_and_recommendations(tmp_path: Path) -> None:
    report = EvaluationComparator().compare_baseline(
        baseline=baseline(metrics={"citation_support_accuracy": 1.0}),
        after=run_result(metrics={"citation_support_accuracy": 0.0}),
    )
    report_dir = write_comparison_reports(report, output_root=tmp_path)

    assert "comparison_id" in format_json(report)
    assert "Run Metadata" in format_markdown(report)
    assert "Configuration Comparison" in format_html(report)
    assert "Citation quality decreased" in format_markdown(report)
    assert (report_dir / "comparison.html").exists()


def test_report_command_generates_html(tmp_path: Path) -> None:
    run_dir = _write_run_artifact(tmp_path / "runs", {"intent_accuracy": 1.0})

    assert main(["report", str(run_dir), "--format", "html", "--output-dir", str(tmp_path / "reports")]) == EXIT_PASSED
    assert list((tmp_path / "reports").glob("*/comparison.html"))


def test_invalid_configuration_exit_code() -> None:
    assert main(["run", "--dataset", "missing/v1", "--mode", "offline"]) == EXIT_CONFIGURATION_ERROR


def test_baseline_create_and_overwrite_protection(tmp_path: Path) -> None:
    run_dir = _write_run_artifact(tmp_path / "runs", {"intent_accuracy": 1.0})
    args = [
        "baseline",
        "create",
        "--run",
        str(run_dir),
        "--name",
        "demo_baseline",
        "--approval-note",
        "approved",
        "--output-dir",
        str(tmp_path / "baselines"),
    ]

    assert main(args) == EXIT_PASSED
    assert main(args) == EXIT_CONFIGURATION_ERROR
