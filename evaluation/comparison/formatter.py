"""JSON, Markdown, and HTML comparison report formatting."""

from __future__ import annotations

import html
import json
from pathlib import Path

from evaluation.comparison.models import ComparisonReport, MetricDelta


def write_comparison_reports(
    report: ComparisonReport,
    *,
    output_root: Path = Path("evaluation/reports"),
) -> Path:
    """Write JSON, Markdown, HTML, and metadata report files."""

    report_dir = output_root / report.comparison_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "comparison.json").write_text(format_json(report), encoding="utf-8")
    (report_dir / "comparison.md").write_text(format_markdown(report), encoding="utf-8")
    (report_dir / "comparison.html").write_text(format_html(report), encoding="utf-8")
    (report_dir / "report_metadata.json").write_text(
        json.dumps(
            {
                "comparison_id": report.comparison_id,
                "created_at": report.created_at.isoformat(),
                "overall_status": report.overall_status.value,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return report_dir


def format_json(report: ComparisonReport) -> str:
    """Machine-readable comparison report."""

    return report.model_dump_json(indent=2)


def format_markdown(report: ComparisonReport) -> str:
    """GitHub-friendly Markdown comparison report."""

    lines = [
        f"# Evaluation Comparison {report.comparison_id}",
        "",
        f"Overall status: **{report.overall_status.value}**",
        "",
        "## Executive Summary",
        "",
        f"- Passed checks: {report.passed_count}",
        f"- Warnings: {report.warning_count}",
        f"- Failed checks: {report.failed_count}",
        f"- Improved metrics: {len(report.improved_metrics)}",
        f"- Regressed metrics: {len(report.regressed_metrics)}",
        "",
        "## Run Metadata",
        "",
        f"- Before: `{_metadata_label(report.before_metadata)}`",
        f"- After: `{_metadata_label(report.after_metadata)}`",
        "",
        "## Metric Deltas",
        "",
        "| Metric | Category | Before | After | Change | Direction | Status |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for delta in report.metric_deltas:
        lines.append(
            f"| `{delta.metric_name}` | {delta.category or ''} | {_fmt(delta.before_value)} | {_fmt(delta.after_value)} | {_fmt(delta.absolute_change)} | {delta.direction.value} | {delta.regression_status.value} |"
        )

    lines.extend(["", "## Critical Failures", ""])
    if report.critical_failures:
        for failure in report.critical_failures:
            lines.append(f"- `{failure.get('metric_name')}`: {failure.get('explanation')}")
    else:
        lines.append("None.")

    lines.extend(["", "## Recommendations", ""])
    if report.recommendations:
        lines.extend(f"- {item}" for item in report.recommendations)
    else:
        lines.append("No rule-based investigation recommendations.")

    lines.extend(["", "## Warnings", ""])
    if report.warnings:
        lines.extend(f"- {item}" for item in report.warnings)
    else:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def format_html(report: ComparisonReport) -> str:
    """Standalone deterministic HTML report."""

    status_class = html.escape(report.overall_status.value)
    metric_rows = "\n".join(_metric_row(delta) for delta in report.metric_deltas)
    retrieval_chart = _bar_chart(
        "Retrieval Metrics",
        [delta for delta in report.metric_deltas if delta.category == "retrieval"][:8],
    )
    safety_chart = _bar_chart(
        "Generation and Safety Metrics",
        [delta for delta in report.metric_deltas if delta.category in {"generation", "citations"}][:8],
    )
    latency_chart = _bar_chart(
        "Latency",
        list(report.latency_changes.values())[:8],
    )
    recommendations = "".join(f"<li>{html.escape(item)}</li>" for item in report.recommendations) or "<li>No rule-based recommendations.</li>"
    warnings = "".join(f"<li>{html.escape(item)}</li>" for item in report.warnings) or "<li>None.</li>"
    critical = "".join(
        f"<li><code>{html.escape(str(item.get('metric_name')))}</code>: {html.escape(str(item.get('explanation')))}</li>"
        for item in report.critical_failures
    ) or "<li>None.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Evaluation Comparison {html.escape(report.comparison_id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #202124; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 20px 0; }}
    .tile {{ border: 1px solid #d7dce2; border-radius: 8px; padding: 12px; }}
    .{status_class} {{ font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
    th, td {{ border: 1px solid #d7dce2; padding: 8px; text-align: left; }}
    th {{ background: #f5f7fa; }}
    .failed {{ color: #b42318; }}
    .passed {{ color: #067647; }}
    .warning, .not_comparable {{ color: #b54708; }}
    .bars {{ margin: 20px 0; }}
    .bar-row {{ display: grid; grid-template-columns: 220px 1fr 1fr; gap: 8px; align-items: center; margin: 6px 0; }}
    .bar {{ height: 12px; background: #d8e7ff; border-radius: 3px; }}
    .bar.after {{ background: #9fd6b5; }}
    code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Evaluation Comparison</h1>
  <p>Comparison ID: <code>{html.escape(report.comparison_id)}</code></p>
  <p>Overall status: <span class="{status_class}">{html.escape(report.overall_status.value)}</span></p>
  <section class="summary">
    <div class="tile"><strong>{report.passed_count}</strong><br>Passed</div>
    <div class="tile"><strong>{report.warning_count}</strong><br>Warnings</div>
    <div class="tile"><strong>{report.failed_count}</strong><br>Failed</div>
    <div class="tile"><strong>{len(report.regressed_metrics)}</strong><br>Regressed Metrics</div>
  </section>
  <h2>Metric Category Tables</h2>
  <table>
    <thead><tr><th>Metric</th><th>Category</th><th>Before</th><th>After</th><th>Change</th><th>Direction</th><th>Status</th></tr></thead>
    <tbody>{metric_rows}</tbody>
  </table>
  {retrieval_chart}
  {safety_chart}
  {latency_chart}
  <h2>Critical Failures</h2>
  <ul>{critical}</ul>
  <h2>Configuration Comparison</h2>
  <pre>{html.escape(json.dumps(report.model_configuration_diff, indent=2, default=str))}</pre>
  <h2>Knowledge Base Comparison</h2>
  <pre>{html.escape(json.dumps(report.knowledge_base_comparison, indent=2, default=str))}</pre>
  <h2>Warnings</h2>
  <ul>{warnings}</ul>
  <h2>Recommended Investigation Areas</h2>
  <ul>{recommendations}</ul>
</body>
</html>
"""


def _metric_row(delta: MetricDelta) -> str:
    status = html.escape(delta.regression_status.value)
    return (
        "<tr>"
        f"<td><code>{html.escape(delta.metric_name)}</code></td>"
        f"<td>{html.escape(delta.category or '')}</td>"
        f"<td>{_fmt(delta.before_value)}</td>"
        f"<td>{_fmt(delta.after_value)}</td>"
        f"<td>{_fmt(delta.absolute_change)}</td>"
        f"<td>{html.escape(delta.direction.value)}</td>"
        f"<td class=\"{status}\">{status}</td>"
        "</tr>"
    )


def _bar_chart(title: str, deltas: list[MetricDelta]) -> str:
    if not deltas:
        return ""
    rows = []
    max_value = max([value for delta in deltas for value in [delta.before_value, delta.after_value] if value is not None] or [1.0])
    max_value = max(max_value, 1.0)
    for delta in deltas:
        before_width = int(((delta.before_value or 0.0) / max_value) * 100)
        after_width = int(((delta.after_value or 0.0) / max_value) * 100)
        rows.append(
            f"<div class=\"bar-row\"><code>{html.escape(delta.metric_name)}</code><div class=\"bar\" style=\"width:{before_width}%\"></div><div class=\"bar after\" style=\"width:{after_width}%\"></div></div>"
        )
    return f"<section class=\"bars\"><h2>{html.escape(title)}</h2>{''.join(rows)}</section>"


def _metadata_label(metadata: dict) -> str:
    return str(metadata.get("run_id") or metadata.get("baseline_id") or metadata.get("run_name") or metadata.get("dataset_name") or "unknown")


def _fmt(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4g}"
