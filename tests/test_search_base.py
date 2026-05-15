"""Tests for src/search/base.py — RateLimiter, SearchFilters, BaseSearchClient."""
from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from src.search.base import RateLimiter, SearchFilters
from src.search.exceptions import SearchError
from src.storage.schemas import PaperCreate


# ── RateLimiter ───────────────────────────────────────────────────────────────


def test_rate_limiter_enforces_min_interval():
    """Two consecutive wait() calls must be >= min_interval apart."""
    limiter = RateLimiter(max_per_second=10.0)  # 100 ms between calls
    t0 = time.monotonic()
    limiter.wait()
    limiter.wait()
    elapsed = time.monotonic() - t0
    # At least one interval must have passed (allow 20 ms slop)
    assert elapsed >= 0.08, f"Expected >= 80 ms gap, got {elapsed * 1000:.1f} ms"


def test_rate_limiter_does_not_sleep_when_enough_time_passed():
    """If enough time has passed, wait() should return without extra sleep."""
    limiter = RateLimiter(max_per_second=5.0)  # 200 ms interval
    limiter.wait()
    time.sleep(0.25)  # more than one interval
    t0 = time.monotonic()
    limiter.wait()
    elapsed = time.monotonic() - t0
    # Should return almost immediately (allow 50 ms overhead)
    assert elapsed < 0.05, f"Expected < 50 ms, got {elapsed * 1000:.1f} ms"


# ── SearchFilters ─────────────────────────────────────────────────────────────


def test_search_filters_defaults():
    f = SearchFilters()
    assert f.publication_types == ["journal", "review"]
    assert f.year_from is None
    assert f.year_to is None
    assert f.min_citation_count is None
    assert f.open_access_only is False
    assert f.fields_of_study is None


def test_search_filters_custom():
    f = SearchFilters(
        year_from=2020,
        year_to=2024,
        publication_types=["journal"],
        min_citation_count=10,
        open_access_only=True,
        fields_of_study=["Medicine", "Nursing"],
    )
    assert f.year_from == 2020
    assert f.year_to == 2024
    assert f.publication_types == ["journal"]
    assert f.min_citation_count == 10
    assert f.open_access_only is True
    assert f.fields_of_study == ["Medicine", "Nursing"]


def test_search_filters_rejects_invalid_pub_type():
    with pytest.raises(Exception):
        SearchFilters(publication_types=["invalid_type"])


# ── BaseSearchClient abstract enforcement ─────────────────────────────────────


def test_base_client_cannot_be_instantiated_directly():
    """BaseSearchClient must not be instantiatable without implementing abstracts."""
    from src.search.base import BaseSearchClient

    with pytest.raises(TypeError):
        BaseSearchClient(rate_limiter=RateLimiter(1.0))  # type: ignore[abstract]


def test_base_client_concrete_subclass_works():
    """A concrete subclass implementing all abstract methods should instantiate."""
    from src.search.base import BaseSearchClient, SearchFilters, SearchStrategy

    class ConcreteClient(BaseSearchClient):
        def search(self, query, limit=10, filters=None, strategy="relevance"):
            return []

        def get_paper_by_doi(self, doi):
            return None

    client = ConcreteClient(rate_limiter=RateLimiter(1.0))
    assert client is not None
    assert client.search("test") == []
    assert client.get_paper_by_doi("10.1234/test") is None
