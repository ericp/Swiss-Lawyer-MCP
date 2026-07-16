"""JSONL dataset loading for evaluation cases."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from evaluation.models import EvaluationCase


class EvaluationDatasetMetadata(BaseModel):
    """Version metadata for one JSONL evaluation dataset."""

    record_type: str = "metadata"
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    description: str = Field(min_length=1)
    source_registry_version: str = Field(min_length=1)
    applicable_knowledge_base_version: str = Field(min_length=1)
    authoring_notes: str = Field(min_length=1)


class VersionedEvaluationDataset(BaseModel):
    """Loaded metadata plus cases."""

    metadata: EvaluationDatasetMetadata
    cases: list[EvaluationCase]
    path: Path


def load_jsonl_dataset(path: Path) -> VersionedEvaluationDataset:
    """Load a versioned JSONL dataset."""

    metadata: EvaluationDatasetMetadata | None = None
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        record_type = payload.get("record_type", "case")
        if record_type == "metadata":
            metadata = EvaluationDatasetMetadata.model_validate(payload)
            continue
        if record_type != "case":
            raise ValueError(f"Unsupported record_type on line {line_number}: {record_type}")
        payload = {key: value for key, value in payload.items() if key != "record_type"}
        cases.append(EvaluationCase.model_validate(payload))

    if metadata is None:
        raise ValueError(f"Dataset metadata record is missing: {path}")
    return VersionedEvaluationDataset(metadata=metadata, cases=cases, path=path)


def load_all_datasets(root: Path = Path("evaluation/datasets")) -> list[VersionedEvaluationDataset]:
    """Load all versioned JSONL datasets under the evaluation dataset root."""

    return [
        load_jsonl_dataset(path)
        for path in sorted(root.glob("*/*.jsonl"))
        if "fixtures" not in path.parts and "schemas" not in path.parts
    ]
