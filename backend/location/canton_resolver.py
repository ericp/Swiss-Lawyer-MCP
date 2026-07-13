"""Deterministic Swiss city-to-canton resolver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CantonResolution:
    """Result of resolving a Swiss city or municipality to a canton."""

    city: str
    canton: str | None
    is_resolved: bool
    needs_clarification: bool
    reason: str | None = None


class CantonResolver:
    """Resolve known Swiss cities to cantons without using an LLM."""

    CITY_TO_CANTON = {
        "zurich": "ZH",
        "zürich": "ZH",
        "geneva": "GE",
        "genève": "GE",
        "lausanne": "VD",
        "bern": "BE",
        "berne": "BE",
        "basel": "BS",
        "lugano": "TI",
    }

    AMBIGUOUS_CITIES = {"baden"}

    def resolve(self, city: str | None) -> CantonResolution:
        if city is None or not city.strip():
            return CantonResolution(
                city="",
                canton=None,
                is_resolved=False,
                needs_clarification=False,
                reason="No city supplied.",
            )

        normalized = city.strip().lower()
        if normalized in self.AMBIGUOUS_CITIES:
            return CantonResolution(
                city=city.strip(),
                canton=None,
                is_resolved=False,
                needs_clarification=True,
                reason="City is ambiguous; canton confirmation is required.",
            )

        canton = self.CITY_TO_CANTON.get(normalized)
        if canton is None:
            return CantonResolution(
                city=city.strip(),
                canton=None,
                is_resolved=False,
                needs_clarification=True,
                reason="Unknown city; canton confirmation is required.",
            )

        return CantonResolution(
            city=city.strip(),
            canton=canton,
            is_resolved=True,
            needs_clarification=False,
        )
