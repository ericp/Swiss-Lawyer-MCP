"""Landing-page candidate discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urldefrag, urlparse

from backend.synchronizer.html_extraction import extract_links
from backend.synchronizer.regions import is_approved_url
from backend.synchronizer.source_registry import SourceDefinition

PROCEDURE_KEYWORDS = {
    "immigration": ["immigration", "migration", "entry", "move"],
    "residence_permit": ["residence permit", "permit b", "residence"],
    "work_permit": ["work permit", "employment", "work"],
    "family_reunification": ["family reunification", "spouse", "family"],
    "municipality_registration": ["registration", "arrival", "municipality"],
    "driving_licence_exchange": ["driving licence", "driver licence", "license exchange"],
    "citizenship": ["citizenship", "naturalization", "naturalisation"],
}


@dataclass(frozen=True)
class DiscoveredCandidate:
    """Candidate link found from an approved source."""

    url: str
    canonical_url: str
    title: str | None
    inferred_procedure_types: list[str]
    relevance_score: float
    discovery_reason: str
    detected_content_type: str | None = None


def discover_candidates_from_html(
    html: str,
    *,
    source: SourceDefinition,
) -> list[DiscoveredCandidate]:
    """Extract, filter, and score candidate links from one landing page."""

    candidates: dict[str, DiscoveredCandidate] = {}
    for url, label in extract_links(html, base_url=source.url):
        canonical = canonicalize_url(url)
        if not _is_candidate_url(canonical, source=source):
            continue
        procedure_types = infer_procedure_types(f"{label} {canonical}")
        if not procedure_types:
            continue
        score = min(1.0, 0.25 + (0.15 * len(procedure_types)))
        candidates[canonical] = DiscoveredCandidate(
            url=url,
            canonical_url=canonical,
            title=label or None,
            inferred_procedure_types=procedure_types,
            relevance_score=score,
            discovery_reason="Matched curated domain and procedure keywords.",
            detected_content_type="application/pdf" if canonical.lower().endswith(".pdf") else "text/html",
        )
    return list(candidates.values())


def canonicalize_url(url: str) -> str:
    """Canonicalize a URL for deduplication."""

    without_fragment, _fragment = urldefrag(url)
    parsed = urlparse(without_fragment)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    path = re.sub(r"/+", "/", parsed.path)
    return parsed._replace(scheme=scheme, netloc=host, path=path).geturl()


def infer_procedure_types(text: str) -> list[str]:
    """Infer procedure types deterministically from keywords."""

    lowered = text.lower()
    return [
        procedure
        for procedure, keywords in PROCEDURE_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]


def _is_candidate_url(url: str, *, source: SourceDefinition) -> bool:
    if not is_approved_url(url, region=source.region):
        return False
    lowered = url.lower()
    ignored_suffixes = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".zip")
    if lowered.endswith(ignored_suffixes):
        return False
    if source.include_url_patterns and not any(
        re.search(pattern, url) for pattern in source.include_url_patterns
    ):
        return False
    if any(re.search(pattern, url) for pattern in source.exclude_url_patterns):
        return False
    return True
