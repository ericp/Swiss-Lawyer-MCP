from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.datasets.loader import load_all_datasets, load_jsonl_dataset
from evaluation.datasets.validator import validate_all_datasets, validate_dataset_file


def _write_dataset(path: Path, cases: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {
        "record_type": "metadata",
        "name": "unit",
        "version": "v1",
        "created_at": "2026-07-15",
        "description": "Unit dataset.",
        "source_registry_version": "1",
        "applicable_knowledge_base_version": "unit",
        "authoring_notes": "Synthetic fictional unit data.",
    }
    lines = [json.dumps(metadata)]
    lines.extend(json.dumps({"record_type": "case", **case}) for case in cases)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _case(case_id: str = "case-1", **updates):
    data = {
        "id": case_id,
        "question": "Can a fictional Brazilian citizen move to Switzerland?",
        "tags": ["clarification", "immigration"],
        "user_profile": {"nationality": "Brazil"},
        "expected_intent": "immigration",
        "coverage_status": "supported",
        "notes": "Fictional profile.",
    }
    data.update(updates)
    return data


def test_dataset_loading_and_jsonl_parsing() -> None:
    dataset = load_jsonl_dataset(Path("evaluation/datasets/smoke/v1.jsonl"))

    assert dataset.metadata.name == "smoke"
    assert dataset.metadata.version == "v1"
    assert len(dataset.cases) == 10


def test_schema_file_exists_and_describes_case_records() -> None:
    schema = json.loads(
        Path("evaluation/datasets/schemas/evaluation_case.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert schema["title"] == "Swiss Lawyer MCP Evaluation JSONL Record"
    assert "oneOf" in schema


def test_duplicate_id_detection(tmp_path: Path) -> None:
    path = tmp_path / "dup.jsonl"
    _write_dataset(path, [_case("dup"), _case("dup")])

    result = validate_dataset_file(path)

    assert not result.is_valid
    assert any("duplicate case id" in error for error in result.errors)


def test_invalid_relevance_grade_rejection(tmp_path: Path) -> None:
    path = tmp_path / "bad_grade.jsonl"
    _write_dataset(path, [_case(relevance_judgments={"source": 4})])

    result = validate_dataset_file(path)

    assert any("invalid relevance grades" in error for error in result.errors)


def test_invalid_region_rejection(tmp_path: Path) -> None:
    path = tmp_path / "bad_region.jsonl"
    _write_dataset(path, [_case(expected_regions=["xx"])])

    result = validate_dataset_file(path)

    assert any("invalid regions" in error for error in result.errors)


def test_contradictory_expectation_rejection(tmp_path: Path) -> None:
    path = tmp_path / "contradiction.jsonl"
    _write_dataset(
        path,
        [
            _case(
                expected_clarification_fields=["intended_canton"],
                forbidden_clarification_fields=["intended_canton"],
            )
        ],
    )

    result = validate_dataset_file(path)

    assert any("contradictory clarification" in error for error in result.errors)


def test_dataset_version_validation(tmp_path: Path) -> None:
    path = tmp_path / "missing_metadata.jsonl"
    path.write_text(json.dumps({"record_type": "case", **_case()}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="metadata"):
        load_jsonl_dataset(path)


def test_tag_filtering_compatible_with_loader() -> None:
    datasets = load_all_datasets()
    smoke_cases = [
        case
        for dataset in datasets
        for case in dataset.cases
        if "smoke" in case.tags
    ]

    assert len(smoke_cases) == 10


def test_expected_source_existence_checks(tmp_path: Path) -> None:
    path = tmp_path / "bad_source.jsonl"
    _write_dataset(path, [_case(expected_source_ids=["missing_source"])])

    result = validate_dataset_file(path)

    assert any("unknown expected source ids" in error for error in result.errors)


def test_no_private_or_production_user_data(tmp_path: Path) -> None:
    path = tmp_path / "private.jsonl"
    _write_dataset(
        path,
        [
            _case(
                question="Can John Smith move to Switzerland?",
                notes="Real-looking personal name should be rejected.",
            )
        ],
    )

    result = validate_dataset_file(path)

    assert any("private" in error for error in result.errors)


def test_all_committed_datasets_pass_validation() -> None:
    result = validate_all_datasets()

    assert result.is_valid, result.errors
    assert result.checked_files == 6
    assert result.checked_cases == 95
