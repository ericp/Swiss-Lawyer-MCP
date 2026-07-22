"""Command-line interface for evaluation, comparison, and reporting."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from evaluation.comparison.comparator import EvaluationComparator, load_baseline_by_name, load_run_result
from evaluation.comparison.formatter import format_html, format_json, format_markdown, write_comparison_reports
from evaluation.config import EvaluationConfig, ExecutionMode
from evaluation.datasets.validator import validate_all_datasets
from evaluation.regression.baseline_service import BaselineGenerationService
from evaluation.regression.fingerprint import build_knowledge_base_fingerprint
from evaluation.regression.models import RegressionStatus
from evaluation.regression.thresholds import load_threshold_config
from evaluation.runner import EvaluationRunner


EXIT_PASSED = 0
EXIT_REGRESSION_FAILURE = 1
EXIT_CONFIGURATION_ERROR = 2
EXIT_EXECUTION_FAILURE = 3
EXIT_BASELINE_INCOMPATIBLE = 4


def build_parser() -> argparse.ArgumentParser:
    """Build the evaluation CLI parser."""

    parser = argparse.ArgumentParser(prog="python -m evaluation.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate-datasets", help="Validate committed evaluation datasets")

    run_parser = subparsers.add_parser("run", help="Run an evaluation dataset")
    _add_run_options(run_parser)

    compare_parser = subparsers.add_parser("compare", help="Compare two runs or a baseline and run")
    before_group = compare_parser.add_mutually_exclusive_group(required=True)
    before_group.add_argument("--before", help="Before run id or artifact path")
    before_group.add_argument("--baseline", help="Baseline name such as retrieval_v1 or path")
    compare_parser.add_argument("--after", required=True, help="After run id or artifact path")
    compare_parser.add_argument("--output-dir", default="evaluation/reports")

    baseline_parser = subparsers.add_parser("baseline", help="Manage baselines")
    baseline_subparsers = baseline_parser.add_subparsers(dest="baseline_command", required=True)
    create_parser = baseline_subparsers.add_parser("create", help="Create a baseline from a run")
    create_parser.add_argument("--run", required=True)
    create_parser.add_argument("--name", required=True)
    create_parser.add_argument("--approval-note", required=True)
    create_parser.add_argument("--output-dir", default="evaluation/baselines")
    create_parser.add_argument("--force", action="store_true")

    list_parser = subparsers.add_parser("list-runs", help="List evaluation artifact runs")
    list_parser.add_argument("--output-dir", default="evaluation/artifacts")

    show_parser = subparsers.add_parser("show-run", help="Show one evaluation run summary")
    show_parser.add_argument("run")
    show_parser.add_argument("--output-dir", default="evaluation/artifacts")

    report_parser = subparsers.add_parser("report", help="Generate a report for one run")
    report_parser.add_argument("run")
    report_parser.add_argument("--format", choices=["json", "markdown", "html"], default="markdown")
    report_parser.add_argument("--output-dir", default="evaluation/reports")
    report_parser.add_argument("--artifacts-dir", default="evaluation/artifacts")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a CI-friendly exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-datasets":
            return _validate_datasets()
        if args.command == "run":
            return _run_evaluation(args)
        if args.command == "compare":
            return _compare(args)
        if args.command == "baseline":
            return _baseline(args)
        if args.command == "list-runs":
            return _list_runs(args)
        if args.command == "show-run":
            return _show_run(args)
        if args.command == "report":
            return _report(args)
    except (FileNotFoundError, FileExistsError, ValueError, json.JSONDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    except Exception as error:
        print(f"Execution failure: {error}", file=sys.stderr)
        return EXIT_EXECUTION_FAILURE
    return EXIT_CONFIGURATION_ERROR


def _add_run_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", required=True, help="Dataset name/version such as smoke/v1")
    parser.add_argument("--mode", choices=[mode.value for mode in ExecutionMode], default=ExecutionMode.OFFLINE.value)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--run-name", default="evaluation")
    parser.add_argument("--output-dir", default="evaluation/artifacts")
    parser.add_argument("--save-intermediate", action="store_true", default=False)
    parser.add_argument("--generation", action="store_true")
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--judge-model")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--config")
    parser.add_argument("--notes")
    parser.add_argument("--yes", action="store_true", help="Confirm live API-backed evaluation")


def _validate_datasets() -> int:
    result = validate_all_datasets()
    if result.is_valid:
        print(f"Validated {result.checked_cases} cases in {result.checked_files} files.")
        return EXIT_PASSED
    for error in result.errors:
        print(error, file=sys.stderr)
    return EXIT_CONFIGURATION_ERROR


def _run_evaluation(args: argparse.Namespace) -> int:
    mode = ExecutionMode(args.mode)
    if mode is ExecutionMode.LIVE and not args.yes:
        print("Live evaluation may make API calls and incur costs. Re-run with --yes to confirm.", file=sys.stderr)
        return EXIT_CONFIGURATION_ERROR
    dataset_path = _dataset_path(args.dataset)
    config_payload = _load_config_payload(args.config)
    config = EvaluationConfig(
        dataset_path=dataset_path,
        dataset_name=args.dataset.split("/", 1)[0],
        dataset_version=args.dataset.split("/", 1)[1] if "/" in args.dataset else "v1",
        run_name=args.run_name,
        execution_mode=mode,
        output_directory=Path(args.output_dir),
        random_seed=args.seed,
        generation_enabled=args.generation,
        planner_enabled=args.planner,
        judge_model_enabled=bool(args.judge_model),
        judge_model=args.judge_model,
        max_cases=args.max_cases,
        case_ids=args.case_id,
        tags=args.tag,
        fail_fast=args.fail_fast,
        save_intermediate_outputs=args.save_intermediate,
        notes=args.notes,
        **config_payload,
    )
    run_result = EvaluationRunner(config=config).run()
    print(f"Run ID: {run_result.metadata.run_id}")
    print(f"Artifacts: {config.output_directory / run_result.metadata.run_id}")
    return EXIT_EXECUTION_FAILURE if run_result.errors else EXIT_PASSED


def _compare(args: argparse.Namespace) -> int:
    thresholds = load_threshold_config()
    comparator = EvaluationComparator(thresholds=thresholds)
    after = load_run_result(args.after)
    if args.baseline:
        report = comparator.compare_baseline(
            baseline=load_baseline_by_name(args.baseline),
            after=after,
        )
    else:
        report = comparator.compare_runs(
            before=load_run_result(args.before),
            after=after,
        )
    report_dir = write_comparison_reports(report, output_root=Path(args.output_dir))
    print(f"Comparison ID: {report.comparison_id}")
    print(f"Overall status: {report.overall_status.value}")
    print(f"Reports: {report_dir}")
    return _exit_code_for_report(report)


def _baseline(args: argparse.Namespace) -> int:
    if args.baseline_command == "create":
        run_result = load_run_result(args.run)
        output_path = Path(args.output_dir) / f"{args.name}.json"
        baseline = BaselineGenerationService().create_baseline(
            run_result=run_result,
            output_path=output_path,
            approval_note=args.approval_note,
            force=args.force,
            knowledge_base_fingerprint=build_knowledge_base_fingerprint(),
        )
        print(f"Baseline created: {output_path}")
        print(f"Baseline ID: {baseline.baseline_id}")
        return EXIT_PASSED
    return EXIT_CONFIGURATION_ERROR


def _list_runs(args: argparse.Namespace) -> int:
    root = Path(args.output_dir)
    if not root.exists():
        print("No evaluation runs found.")
        return EXIT_PASSED
    for path in sorted(item for item in root.iterdir() if item.is_dir()):
        metadata_path = path / "run_metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        print(f"{metadata.get('run_id')} {metadata.get('dataset_name')}/{metadata.get('dataset_version')} {metadata.get('run_name')}")
    return EXIT_PASSED


def _show_run(args: argparse.Namespace) -> int:
    run = load_run_result(args.run, output_dir=Path(args.output_dir))
    execution = run.aggregate_metrics.get("execution", {})
    print(f"Run ID: {run.metadata.run_id}")
    print(f"Dataset: {run.metadata.dataset_name}/{run.metadata.dataset_version}")
    print(f"Mode: {run.metadata.execution_mode.value}")
    print(f"Cases: {execution.get('case_count', len(run.case_results))}")
    print(f"Failed cases: {execution.get('failed_count', 0)}")
    return EXIT_PASSED


def _report(args: argparse.Namespace) -> int:
    run = load_run_result(args.run, output_dir=Path(args.artifacts_dir))
    report = EvaluationComparator().compare_runs(before=run, after=run)
    report_dir = write_comparison_reports(report, output_root=Path(args.output_dir))
    if args.format == "json":
        print(format_json(report))
    elif args.format == "html":
        print(report_dir / "comparison.html")
    else:
        print(format_markdown(report))
    return EXIT_PASSED


def _dataset_path(dataset: str) -> Path:
    name, _, version = dataset.partition("/")
    version = version or "v1"
    path = Path("evaluation/datasets") / name / f"{version}.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset}")
    return path


def _load_config_payload(config_path: str | None) -> dict:
    if not config_path:
        return {}
    return json.loads(Path(config_path).read_text(encoding="utf-8"))


def _exit_code_for_report(report) -> int:
    if report.overall_status is RegressionStatus.FAILED:
        return EXIT_REGRESSION_FAILURE
    if report.knowledge_base_comparison.get("comparison_context") == "limited_comparability":
        return EXIT_BASELINE_INCOMPATIBLE
    return EXIT_PASSED


if __name__ == "__main__":
    raise SystemExit(main())
