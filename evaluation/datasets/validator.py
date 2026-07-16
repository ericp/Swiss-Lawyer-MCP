"""Validation utilities for committed evaluation datasets."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from backend.synchronizer.regions import REGIONS
from backend.synchronizer.source_registry import load_source_registry
from evaluation.datasets.loader import VersionedEvaluationDataset, load_all_datasets, load_jsonl_dataset
from evaluation.models import EvaluationCase

SUPPORTED_TAGS = {
    "smoke",
    "clarification",
    "retrieval",
    "generation",
    "planning",
    "end_to_end",
    "intent",
    "vector",
    "bm25",
    "hybrid",
    "reranking",
    "citation",
    "abstention",
    "memory",
    "multilingual",
    "city_canton",
    "ambiguous",
    "contradiction",
    "federal",
    "canton",
    "zh",
    "ge",
    "vd",
    "be",
    "future_coverage",
    "synchronizer_coverage",
    "unsupported",
    "eu_efta",
    "non_eu_efta",
    "uk",
    "swiss_permit_holder",
    "unclear_nationality",
    "immigration",
    "residence_permit",
    "work_permit",
    "family_reunification",
    "municipality_registration",
    "driving_licence_exchange",
    "citizenship",
}
VALID_COVERAGE = {
    "supported",
    "insufficient_context",
    "future_coverage",
    "synchronizer_coverage",
}
PRIVATE_PATTERNS = [
    re.compile(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b"),
    re.compile(r"[\w.\-]+@[\w.\-]+\.\w+"),
    re.compile(r"\+?\d[\d\s().-]{7,}\d"),
]


@dataclass
class DatasetValidationResult:
    """Dataset validation report."""

    checked_files: int = 0
    checked_cases: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def validate_dataset_file(
    path: Path,
    *,
    source_registry_path: Path = Path("data/pdfs/metadata/sources.yaml"),
) -> DatasetValidationResult:
    """Validate one JSONL dataset file."""

    return validate_datasets(
        [load_jsonl_dataset(path)],
        source_registry_path=source_registry_path,
    )


def validate_all_datasets(
    *,
    dataset_root: Path = Path("evaluation/datasets"),
    source_registry_path: Path = Path("data/pdfs/metadata/sources.yaml"),
) -> DatasetValidationResult:
    """Validate all committed JSONL datasets."""

    return validate_datasets(
        load_all_datasets(dataset_root),
        source_registry_path=source_registry_path,
    )


def validate_datasets(
    datasets: list[VersionedEvaluationDataset],
    *,
    source_registry_path: Path,
) -> DatasetValidationResult:
    """Validate loaded datasets."""

    result = DatasetValidationResult(checked_files=len(datasets))
    source_ids = {
        source.id
        for source in load_source_registry(source_registry_path).sources
    }
    seen_ids: set[str] = set()
    for dataset in datasets:
        if not dataset.metadata.version:
            result.errors.append(f"{dataset.path}: dataset version is missing")
        if not dataset.metadata.name:
            result.errors.append(f"{dataset.path}: dataset name is missing")
        for case in dataset.cases:
            result.checked_cases += 1
            _validate_case(
                case,
                dataset_path=dataset.path,
                seen_ids=seen_ids,
                source_ids=source_ids,
                result=result,
            )
    return result


def _validate_case(
    case: EvaluationCase,
    *,
    dataset_path: Path,
    seen_ids: set[str],
    source_ids: set[str],
    result: DatasetValidationResult,
) -> None:
    prefix = f"{dataset_path}:{case.id}"
    if case.id in seen_ids:
        result.errors.append(f"{prefix}: duplicate case id")
    seen_ids.add(case.id)
    if not case.question.strip():
        result.errors.append(f"{prefix}: question is empty")
    unsupported_tags = sorted(set(case.tags) - SUPPORTED_TAGS)
    if unsupported_tags:
        result.errors.append(f"{prefix}: unsupported tags {unsupported_tags}")
    invalid_regions = [region for region in case.expected_regions if region not in REGIONS]
    if invalid_regions:
        result.errors.append(f"{prefix}: invalid regions {invalid_regions}")
    invalid_grades = {
        key: value
        for key, value in case.relevance_judgments.items()
        if value not in {0, 1, 2, 3}
    }
    if invalid_grades:
        result.errors.append(f"{prefix}: invalid relevance grades {invalid_grades}")
    unknown_sources = sorted(set(case.expected_source_ids) - source_ids)
    if unknown_sources and case.coverage_status == "supported":
        result.errors.append(f"{prefix}: unknown expected source ids {unknown_sources}")
    overlap = set(case.expected_clarification_fields).intersection(case.forbidden_clarification_fields)
    if overlap:
        result.errors.append(f"{prefix}: contradictory clarification expectations {sorted(overlap)}")
    if case.should_abstain and case.expected_answer_facts:
        result.errors.append(f"{prefix}: abstention case cannot require answer facts")
    if case.coverage_status not in VALID_COVERAGE:
        result.errors.append(f"{prefix}: invalid coverage_status {case.coverage_status}")
    if _contains_private_data(case):
        result.errors.append(f"{prefix}: possible private or production user data")


def _contains_private_data(case: EvaluationCase) -> bool:
    text = " ".join(
        [
            case.question,
            case.notes or "",
            " ".join(str(value) for value in case.user_profile.values()),
        ]
    )
    if "fictional" in text.lower():
        return False
    return any(pattern.search(text) for pattern in PRIVATE_PATTERNS)


def main() -> None:
    result = validate_all_datasets()
    if result.is_valid:
        print(f"Validated {result.checked_cases} cases in {result.checked_files} files.")
        return
    for error in result.errors:
        print(error)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
