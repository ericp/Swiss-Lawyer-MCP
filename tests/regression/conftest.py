"""Regression test controls."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.getenv("RUN_LIVE_EVALUATION") == "1":
        return
    skip_live = pytest.mark.skip(reason="live evaluation disabled by default; set RUN_LIVE_EVALUATION=1")
    for item in items:
        if "live_evaluation" in item.keywords:
            item.add_marker(skip_live)
