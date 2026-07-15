"""Shared helpers for evaluation adapters."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from pydantic import BaseModel


@contextmanager
def timed(stage: str, timings: dict[str, float]) -> Iterator[None]:
    """Capture elapsed seconds for a stage."""

    start = time.perf_counter()
    try:
        yield
    finally:
        timings[stage] = time.perf_counter() - start


def normalize(value: Any) -> Any:
    """Convert common production objects into JSON-safe structures."""

    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, tuple):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize(item) for key, item in value.items()}
    return value
