"""Official webpage extraction and link parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from backend.synchronizer.hashing import sha256_bytes

BOILERPLATE_TAGS = {"script", "style", "nav", "header", "footer", "noscript", "form"}
CONTENT_TAGS = {"h1", "h2", "h3", "h4", "p", "li", "td", "th", "caption", "a"}


@dataclass(frozen=True)
class ExtractedWebpage:
    """Normalized webpage content."""

    title: str | None
    content: str
    sections: list[str]
    content_sha256: str


class _ContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title: str | None = None
        self._in_title = False
        self._skip_depth = 0
        self._active_tag: str | None = None
        self._current: list[str] = []
        self.sections: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        if tag in BOILERPLATE_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in CONTENT_TAGS:
            self._flush()
            self._active_tag = tag

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in BOILERPLATE_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._skip_depth and tag == self._active_tag:
            self._flush()
            self._active_tag = None

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = _normalize_whitespace(text)
            return
        if self._active_tag:
            self._current.append(text)

    def close(self) -> None:
        self._flush()
        super().close()

    def _flush(self) -> None:
        text = _normalize_whitespace(" ".join(self._current))
        if text:
            self.sections.append(text)
        self._current = []


class _LinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        if href:
            self._href = href
            self._label = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._label.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((urljoin(self.base_url, self._href), _normalize_whitespace(" ".join(self._label))))
            self._href = None
            self._label = []


def extract_webpage(html: str) -> ExtractedWebpage:
    """Extract normalized official content from HTML."""

    parser = _ContentParser()
    parser.feed(html)
    parser.close()
    sections = [section for section in parser.sections if not _is_cookie_or_menu(section)]
    content = _normalize_whitespace("\n".join(sections))
    return ExtractedWebpage(
        title=parser.title,
        content=content,
        sections=sections,
        content_sha256=sha256_bytes(content.encode("utf-8")),
    )


def extract_links(html: str, *, base_url: str) -> list[tuple[str, str]]:
    """Extract absolute links and visible labels from HTML."""

    parser = _LinkParser(base_url)
    parser.feed(html)
    parser.close()
    return parser.links


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _is_cookie_or_menu(text: str) -> bool:
    lowered = text.lower()
    markers = ["cookie", "privacy settings", "navigation", "menu"]
    return len(text) < 4 or any(marker in lowered for marker in markers)
