"""HTTP client with domain and change-check safeguards."""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from backend.synchronizer.regions import is_approved_url


class HttpClientError(Exception):
    """HTTP synchronization error."""


class DomainValidationError(HttpClientError):
    """URL or redirect left the approved allowlist."""


class ContentTooLargeError(HttpClientError):
    """Response exceeded the configured size limit."""


@dataclass(frozen=True)
class HttpFetchResult:
    """Downloaded HTTP response data."""

    status_code: int
    final_url: str
    headers: dict[str, str]
    content: bytes
    content_type: str | None
    content_length: int | None


class SyncHttpClient:
    """Small reusable HTTP client for approved official sources."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        redirect_limit: int = 5,
        retry_count: int = 2,
        retry_backoff_seconds: float = 0.25,
        user_agent: str = "Swiss Lawyer MCP Synchronizer/0.9",
        max_response_bytes: int = 20_000_000,
        client: httpx.Client | None = None,
    ) -> None:
        self._retry_count = retry_count
        self._retry_backoff_seconds = retry_backoff_seconds
        self._max_response_bytes = max_response_bytes
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=True,
            max_redirects=redirect_limit,
            headers={"User-Agent": user_agent},
            verify=True,
        )

    def get(
        self,
        url: str,
        *,
        region: str,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> HttpFetchResult:
        """GET a source with conditional request headers."""

        if not is_approved_url(url, region=region):
            raise DomainValidationError("URL is outside the approved allowlist")
        headers: dict[str, str] = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        attempts = self._retry_count + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.get(url, headers=headers)
                self._validate_redirects(response, region=region)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < attempts - 1:
                        time.sleep(self._retry_backoff_seconds * (2**attempt))
                        continue
                content = response.content
                if len(content) > self._max_response_bytes:
                    raise ContentTooLargeError("Response exceeded maximum configured size")
                return HttpFetchResult(
                    status_code=response.status_code,
                    final_url=str(response.url),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    content=content,
                    content_type=response.headers.get("content-type"),
                    content_length=len(content),
                )
            except (httpx.TimeoutException, httpx.NetworkError) as error:
                last_error = error
                if attempt < attempts - 1:
                    time.sleep(self._retry_backoff_seconds * (2**attempt))
                    continue
                raise HttpClientError("Temporary network failure") from error
        raise HttpClientError("HTTP request failed") from last_error

    def _validate_redirects(self, response: httpx.Response, *, region: str) -> None:
        for hop in [*response.history, response]:
            if not is_approved_url(str(hop.url), region=region):
                raise DomainValidationError("Redirect left the approved allowlist")
