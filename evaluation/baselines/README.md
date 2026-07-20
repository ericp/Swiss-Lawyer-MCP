# Evaluation Baselines

Baseline files are committed summaries used by Phase 10 Part 4 regression checks.

They contain:

- baseline ID
- dataset name and version
- creation date
- Git commit when available
- model configuration
- prompt hashes
- source-registry version
- knowledge-base fingerprint
- aggregate metric summaries
- selected critical case results
- human approval notes

They must not contain raw private model outputs, full conversations, personal user data, or full generated answers.

Baselines are never updated automatically. To approve a new baseline, create it from an explicit evaluation run through `BaselineGenerationService.create_baseline(...)`, provide a human approval note, and use `force=True` only when intentionally replacing an existing baseline.
