# Evaluation Datasets

Phase 10 Part 2 adds versioned JSONL datasets for the Swiss Lawyer MCP evaluation module.

JSONL is the canonical format because evaluation cases contain nested structures such as user profiles, fact expectations, relevance judgments, fixture references, and planning concepts.

## Directory Structure

```text
evaluation/datasets/
├── schemas/
│   └── evaluation_case.schema.json
├── smoke/
│   └── v1.jsonl
├── clarification/
│   └── v1.jsonl
├── retrieval/
│   └── v1.jsonl
├── generation/
│   └── v1.jsonl
├── planning/
│   └── v1.jsonl
├── end_to_end/
│   └── v1.jsonl
└── fixtures/
    └── synthetic_contexts/
```

Each JSONL file starts with one metadata record:

```json
{"record_type":"metadata","name":"smoke","version":"v1","created_at":"2026-07-15","description":"...","source_registry_version":"1","applicable_knowledge_base_version":"seed-local-v1","authoring_notes":"..."}
```

All remaining lines are `record_type: "case"` records compatible with `EvaluationCase`.

## Dataset Groups

- `smoke`: 10 representative cases for quick runner checks.
- `clarification`: 20 cases testing material missing-field detection and forbidden clarification fields.
- `retrieval`: 25 cases testing exact keyword, semantic, federal, Zurich canton, hybrid, multilingual, and unsupported retrieval behavior.
- `generation`: 15 cases using synthetic retrieved-context fixtures and fact-level answer expectations.
- `planning`: 10 cases using grounded-answer fixtures with expected workflow concepts and statuses.
- `end_to_end`: 15 realistic scenarios covering non-EU/EFTA, EU/EFTA, UK, Swiss permit holders, memory continuation, unsupported topics, ambiguous cities, and insufficient context.

## Expected Facts

Expected and forbidden answer facts are structured statements:

```json
{
  "fact_id": "job_offer_required_non_eu",
  "description": "A non-EU/EFTA employment route depends on applicable admission requirements and employer involvement.",
  "importance": "critical",
  "required_source_ids": ["seed_federal_b_permit_gainful_activity"]
}
```

Facts are paraphrased. Datasets do not store long copyrighted excerpts.

## Relevance Judgments

Retrieval cases can include graded relevance:

```json
"relevance_judgments": {
  "seed_federal_b_permit_gainful_activity": 3,
  "seed_federal_b_permit_sem": 2
}
```

Grades:

- `0`: irrelevant
- `1`: partially relevant
- `2`: relevant
- `3`: highly relevant

## Coverage Status

Cases distinguish current and future knowledge-base expectations:

- `supported`: expected evidence exists in current seed sources.
- `insufficient_context`: the correct behavior is to abstain or say context is insufficient.
- `future_coverage`: architecturally supported, but not covered by current indexed seed documents.
- `synchronizer_coverage`: expected to become supported through approved synchronizer sources later.

Do not mark a response wrong just because a canton has not been indexed yet when the correct behavior is insufficient context.

## Adding Cases

1. Choose the dataset group.
2. Add a new line to the latest versioned JSONL file.
3. Use a unique `id`.
4. Use fictional users only.
5. Use source IDs from `data/pdfs/metadata/sources.yaml` for supported cases.
6. Use `coverage_status` to mark unsupported or future coverage cases.
7. Validate all datasets:

```bash
python -m evaluation.datasets.validator
```

## Creating a New Version

Do not silently modify an existing version when expectations materially change.

Create a new file such as:

```text
evaluation/datasets/retrieval/v2.jsonl
```

Update the metadata record with the new version, date, source-registry version, knowledge-base version, and authoring notes.
