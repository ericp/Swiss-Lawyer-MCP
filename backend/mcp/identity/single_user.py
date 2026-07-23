"""Fixed single-user identity provider."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class SingleUserIdentityProvider:
    """Server-side identity for the private local portfolio deployment."""

    external_user_key: str

    def __post_init__(self) -> None:
        if not self.external_user_key.strip():
            raise ValueError("MCP_SINGLE_USER_KEY must not be empty")

    def get_external_user_key(self) -> str:
        return self.external_user_key

    def safe_hash_prefix(self) -> str:
        return identity_hash_prefix(self.external_user_key)


def identity_hash_prefix(external_user_key: str) -> str:
    """Return a non-reversible short hash prefix for logs."""

    return hashlib.sha256(external_user_key.encode("utf-8")).hexdigest()[:12]
