"""Central Swiss region and approved-domain definitions."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RegionDefinition:
    """One supported Swiss jurisdiction."""

    code: str
    name: str
    level: str
    approved_domains: tuple[str, ...]


REGIONS: dict[str, RegionDefinition] = {
    "federal": RegionDefinition("federal", "Swiss Confederation", "federal", ("admin.ch",)),
    "ag": RegionDefinition("ag", "Aargau", "canton", ("ag.ch",)),
    "ai": RegionDefinition("ai", "Appenzell Innerrhoden", "canton", ("ai.ch",)),
    "ar": RegionDefinition("ar", "Appenzell Ausserrhoden", "canton", ("ar.ch",)),
    "be": RegionDefinition("be", "Bern", "canton", ("be.ch",)),
    "bl": RegionDefinition("bl", "Basel-Landschaft", "canton", ("bl.ch",)),
    "bs": RegionDefinition("bs", "Basel-Stadt", "canton", ("bs.ch",)),
    "fr": RegionDefinition("fr", "Fribourg", "canton", ("fr.ch",)),
    "ge": RegionDefinition("ge", "Geneva", "canton", ("ge.ch",)),
    "gl": RegionDefinition("gl", "Glarus", "canton", ("gl.ch",)),
    "gr": RegionDefinition("gr", "Graubünden", "canton", ("gr.ch",)),
    "ju": RegionDefinition("ju", "Jura", "canton", ("jura.ch",)),
    "lu": RegionDefinition("lu", "Lucerne", "canton", ("lu.ch",)),
    "ne": RegionDefinition("ne", "Neuchâtel", "canton", ("ne.ch",)),
    "nw": RegionDefinition("nw", "Nidwalden", "canton", ("nw.ch",)),
    "ow": RegionDefinition("ow", "Obwalden", "canton", ("ow.ch",)),
    "sg": RegionDefinition("sg", "St. Gallen", "canton", ("sg.ch",)),
    "sh": RegionDefinition("sh", "Schaffhausen", "canton", ("sh.ch",)),
    "so": RegionDefinition("so", "Solothurn", "canton", ("so.ch",)),
    "sz": RegionDefinition("sz", "Schwyz", "canton", ("sz.ch",)),
    "tg": RegionDefinition("tg", "Thurgau", "canton", ("tg.ch",)),
    "ti": RegionDefinition("ti", "Ticino", "canton", ("ti.ch",)),
    "ur": RegionDefinition("ur", "Uri", "canton", ("ur.ch",)),
    "vd": RegionDefinition("vd", "Vaud", "canton", ("vd.ch",)),
    "vs": RegionDefinition("vs", "Valais", "canton", ("vs.ch",)),
    "zg": RegionDefinition("zg", "Zug", "canton", ("zg.ch",)),
    "zh": RegionDefinition("zh", "Zurich", "canton", ("zh.ch",)),
}


def get_region(code: str) -> RegionDefinition:
    """Return a supported region or raise ValueError."""

    normalized = code.lower()
    if normalized not in REGIONS:
        raise ValueError(f"Unsupported Swiss region: {code}")
    return REGIONS[normalized]


def approved_domains_for_region(region: str) -> tuple[str, ...]:
    """Return approved domains for one region plus federal admin.ch."""

    region_definition = get_region(region)
    domains = set(region_definition.approved_domains)
    domains.add("admin.ch")
    return tuple(sorted(domains))


def is_approved_url(url: str, *, region: str, extra_domains: tuple[str, ...] = ()) -> bool:
    """Return whether a URL stays inside the region's approved domain allowlist."""

    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    allowed = (*approved_domains_for_region(region), *extra_domains)
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed)
