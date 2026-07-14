"""Hashing helpers for synchronized content."""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_bytes(content: bytes) -> str:
    """Return a SHA-256 hex digest for bytes."""

    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Return a SHA-256 hex digest for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
