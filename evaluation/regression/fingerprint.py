"""Deterministic knowledge-base fingerprinting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def build_knowledge_base_fingerprint(
    *,
    source_registry_path: Path = Path("data/pdfs/metadata/sources.yaml"),
    document_roots: list[Path] | None = None,
    chromadb_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic fingerprint from local source metadata and files."""

    document_roots = document_roots or [Path("data/pdfs"), Path("data/documents")]
    registry = _read_registry(source_registry_path)
    sources = registry.get("sources", []) if isinstance(registry, dict) else []
    active_sources = [
        source
        for source in sources
        if isinstance(source, dict) and source.get("enabled", False)
    ]
    active_source_ids = sorted(str(source.get("id")) for source in active_sources if source.get("id"))
    file_hashes = _hash_documents(document_roots)
    payload = {
        "source_registry_version": str(registry.get("version", "unknown")) if isinstance(registry, dict) else "unknown",
        "active_source_ids": active_source_ids,
        "document_ids": sorted(file_hashes),
        "source_content_hashes": file_hashes,
        "chromadb_collection_metadata": chromadb_metadata or {},
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    return payload


def compare_fingerprints(
    baseline: dict[str, Any] | None,
    current: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compare two fingerprint payloads."""

    baseline_value = (baseline or {}).get("fingerprint")
    current_value = (current or {}).get("fingerprint")
    comparable = bool(baseline_value and current_value and baseline_value == current_value)
    return {
        "baseline_fingerprint": baseline_value,
        "current_fingerprint": current_value,
        "comparable": comparable,
        "comparison_context": "same_knowledge_base" if comparable else "limited_comparability",
    }


def _read_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": "missing", "sources": []}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _hash_documents(roots: list[Path]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            if path.name.startswith(".") or "metadata" in path.parts:
                continue
            hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes
