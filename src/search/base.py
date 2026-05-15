from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Literal

import httpx
import tenacity
from pydantic import BaseModel

from src.search.exceptions import APIError, ParseError, RateLimitError, SearchError
from src.storage.schemas import PaperCreate


class RateLimiter:
    """Token-bucket rate limiter, thread-safe."""

    def __init__(self, max_per_second: float) -> None:
        self._min_interval = 1.0 / max_per_second
        self._lock = threading.Lock()
        self._last_request_time: float = 0.0

    def wait(self) -> None:
        """Block until the next request token is available."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            sleep_time = self._min_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._last_request_time = time.monotonic()


SearchStrategy = Literal["relevance", "recent", "highly_cited", "review"]


class SearchFilters(BaseModel):
    year_from: int | None = None
    year_to: int | None = None
    publication_types: list[
        Literal["journal", "review", "conference", "preprint", "book_chapter"]
    ] = ["journal", "review"]
    min_citation_count: int | None = None
    open_access_only: bool = False
    fields_of_study: list[str] | None = None


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIError) and exc.status_code >= 500:
        return True
    return False


class BaseSearchClient(ABC):
    def __init__(
        self,
        rate_limiter: RateLimiter,
        timeout: float = 30.0,
        contact_email: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._rate_limiter = rate_limiter
        self._timeout = timeout
        self._contact_email = contact_email
        self._client = http_client or httpx.Client()

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
        filters: SearchFilters | None = None,
        strategy: SearchStrategy = "relevance",
    ) -> list[PaperCreate]:
        """Search for papers matching query."""
        ...

    @abstractmethod
    def get_paper_by_doi(self, doi: str) -> PaperCreate | None:
        """Fetch a single paper by DOI, or None if not found."""
        ...

    def _get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> dict:
        """Synchronous GET with rate limiting and tenacity retry.

        Retries on 429 (up to 3 times) and 5xx (up to 3 times) with
        exponential backoff starting at 2s. Non-retryable 4xx raises
        APIError immediately.
        """
        all_headers = dict(headers or {})

        def _do() -> dict:
            self._rate_limiter.wait()
            try:
                resp = self._client.get(
                    url, params=params, headers=all_headers, timeout=self._timeout
                )
            except httpx.RequestError as exc:
                raise APIError(f"Request failed: {exc}", status_code=0) from exc

            if resp.status_code == 429:
                raise RateLimitError("Rate limited (HTTP 429)")
            if resp.status_code >= 500:
                raise APIError(
                    f"Server error: {resp.status_code}", status_code=resp.status_code
                )
            if not resp.is_success:
                raise APIError(
                    f"Client error: {resp.status_code}", status_code=resp.status_code
                )
            try:
                return resp.json()
            except Exception as exc:
                raise ParseError(f"JSON parse failed: {exc}") from exc

        retryer = tenacity.Retrying(
            retry=tenacity.retry_if_exception(_is_retryable),
            stop=tenacity.stop_after_attempt(4),
            wait=tenacity.wait_exponential(multiplier=1, min=2, max=30),
            reraise=True,
        )
        result: dict = retryer(_do)
        return result
