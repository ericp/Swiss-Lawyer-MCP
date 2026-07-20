"""Baseline loading helpers."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.regression.models import BaselineSummary


def load_baseline(path: Path) -> BaselineSummary:
    """Load a committed baseline summary."""

    return BaselineSummary.model_validate(json.loads(path.read_text(encoding="utf-8")))
