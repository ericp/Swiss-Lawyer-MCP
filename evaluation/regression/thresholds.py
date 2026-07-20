"""Threshold configuration loading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from evaluation.regression.models import (
    CriticalCaseRequirement,
    RegressionThresholdConfig,
    ThresholdRule,
)


DEFAULT_THRESHOLDS_PATH = Path("evaluation/regression/thresholds.yaml")


def load_threshold_config(path: Path = DEFAULT_THRESHOLDS_PATH) -> RegressionThresholdConfig:
    """Load regression thresholds from YAML."""

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RegressionThresholdConfig(
        version=payload.get("version", 1),
        global_thresholds=[
            ThresholdRule(metric_name=name, **rule)
            for name, rule in payload.get("global_thresholds", {}).items()
        ],
        dataset_thresholds=_load_rule_groups(payload.get("dataset_thresholds", {})),
        metric_thresholds={
            name: ThresholdRule(metric_name=name, **rule)
            for name, rule in payload.get("metric_thresholds", {}).items()
        },
        tag_thresholds=_load_rule_groups(payload.get("tag_thresholds", {})),
        critical_cases=[
            CriticalCaseRequirement.model_validate(item)
            for item in payload.get("critical_cases", [])
        ],
    )


def _load_rule_groups(groups: dict[str, Any]) -> dict[str, list[ThresholdRule]]:
    return {
        group_name: [
            ThresholdRule(metric_name=metric_name, **rule)
            for metric_name, rule in metrics.items()
        ]
        for group_name, metrics in groups.items()
    }
