"""Source registry loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.synchronizer.regions import REGIONS, is_approved_url

SourceType = Literal["pdf", "webpage", "landing_page", "local_only"]


class SourceDefinition(BaseModel):
    """One approved or manually seeded source definition."""

    id: str = Field(min_length=1)
    enabled: bool
    region: str
    authority: str = Field(min_length=1)
    procedure_types: list[str] = Field(min_length=1)
    source_type: SourceType
    url: str = Field(min_length=1)
    language: str = Field(min_length=1)
    local_filename: str = Field(min_length=1)
    discovery_enabled: bool
    title: str | None = None
    expected_content_type: str | None = None
    css_content_selector: str | None = None
    css_link_selector: str | None = None
    include_url_patterns: list[str] = Field(default_factory=list)
    exclude_url_patterns: list[str] = Field(default_factory=list)
    notes: str | None = None
    priority: int | None = None
    expected_update_frequency: str | None = None
    replacement_group: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in REGIONS:
            raise ValueError(f"Unsupported region: {value}")
        return normalized

    @field_validator("local_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or path.name != value:
            raise ValueError("local_filename must be a safe filename")
        if not value.strip():
            raise ValueError("local_filename must not be empty")
        return value

    @model_validator(mode="after")
    def validate_url(self) -> SourceDefinition:
        if self.source_type == "local_only":
            if not self.url.startswith("local://"):
                raise ValueError("local_only sources must use local:// URLs")
            return self

        parsed = urlparse(self.url)
        if parsed.scheme != "https":
            raise ValueError("remote sources must use HTTPS")
        if not is_approved_url(self.url, region=self.region):
            raise ValueError("source URL is outside the approved domain allowlist")
        return self


class SourceRegistry(BaseModel):
    """Validated source registry."""

    version: int
    sources: list[SourceDefinition] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_unique_sources(self) -> SourceRegistry:
        ids: set[str] = set()
        active_url_region: set[tuple[str, str]] = set()
        for source in self.sources:
            if source.id in ids:
                raise ValueError(f"Duplicate source id: {source.id}")
            ids.add(source.id)
            if source.enabled and source.source_type != "local_only":
                key = (source.url, source.region)
                if key in active_url_region:
                    raise ValueError(f"Duplicate active source URL and region: {source.url}")
                active_url_region.add(key)
        return self


def load_source_registry(path: Path) -> SourceRegistry:
    """Load and validate a YAML source registry."""

    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return SourceRegistry(version=1, sources=[])
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SourceRegistry.model_validate(payload)


def write_source_registry(path: Path, registry: SourceRegistry) -> None:
    """Write a registry as YAML."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = registry.model_dump(exclude_none=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
