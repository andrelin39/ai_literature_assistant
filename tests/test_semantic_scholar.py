"""Tests for SemanticScholarClient — all HTTP mocked via pytest-httpx."""
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")

from src.search.exceptions import APIError, RateLimitError
from src.search.semantic_scholar import SemanticScholarClient
from src.search.base import RateLimiter, SearchFilters

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "s2_sample_responses.json").read_text())


def _make_client(http_client: httpx.Client) -> SemanticScholarClient:
    """Build a SemanticScholarClient with a preset httpx.Client and fast rate limiter."""
    client = SemanticScholarClient(api_key=None, http_client=http_client)
    # Override rate limiter so tests don't wait 200-333 ms per request
    client._rate_limiter = RateLimiter(max_per_second=1000.0)
    return client


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fixture_data():
    return _load_fixture()


@pytest.fixture
def search_response(fixture_data):
    return fixture_data["search_results"]


@pytest.fixture
def single_paper_response(fixture_data):
    return fixture_data["single_paper"]


# ── Basic search ──────────────────────────────────────────────────────────────


def test_search_relevance_returns_papers(httpx_mock, search_response):
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("nursing burnout COVID-19", limit=5)

    assert len(results) == 3
    assert all(hasattr(r, "title") for r in results)
    # First paper has a DOI
    assert results[0].doi == "10.1016/j.ijns.2023.104567"
    assert results[0].source_api == "semantic_scholar"
    assert results[0].semantic_scholar_id == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


def test_search_returns_paper_with_citation_count(httpx_mock, search_response):
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("nursing burnout")

    assert results[0].citation_count == 127
    assert results[2].citation_count == 412


def test_search_maps_authors_correctly(httpx_mock, search_response):
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("test")

    authors = results[0].authors
    assert len(authors) == 3
    assert authors[0].name == "Chen Wei"


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_search_empty_results(httpx_mock):
    httpx_mock.add_response(json={"total": 0, "offset": 0, "data": []})
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("xyzzy very unlikely query")

    assert results == []


def test_paper_without_doi(httpx_mock, search_response):
    """The arXiv preprint paper (index 1) should have doi=None."""
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("test")

    preprint = results[1]
    assert preprint.doi is None
    assert preprint.semantic_scholar_id == "b2c3d4e5f6a7b2c3d4e5f6a7b2c3d4e5f6a7b2c3"


def test_paper_without_abstract(httpx_mock, search_response):
    """Papers with null abstract should not crash."""
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("test")

    # Papers at index 1 and 2 have null abstract
    assert results[1].abstract is None
    assert results[2].abstract is None


def test_paper_missing_authors(httpx_mock):
    minimal_response = {
        "total": 1,
        "offset": 0,
        "data": [
            {
                "paperId": "abc123",
                "externalIds": {},
                "title": "A minimal paper",
                "abstract": None,
                "year": None,
                "venue": None,
                "authors": [],
                "citationCount": None,
                "publicationTypes": [],
                "publicationDate": None,
                "openAccessPdf": None,
                "url": "https://www.semanticscholar.org/paper/abc123",
                "fieldsOfStudy": None,
            }
        ],
    }
    httpx_mock.add_response(json=minimal_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("minimal")

    assert len(results) == 1
    assert results[0].authors == []
    assert results[0].doi is None


# ── Retry behaviour ───────────────────────────────────────────────────────────


def test_429_retried_then_success(httpx_mock, search_response):
    """Single 429 followed by success should return results."""
    httpx_mock.add_response(status_code=429)
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("retry test")

    assert len(results) == 3


def test_429_repeated_raises_rate_limit_error(httpx_mock):
    """Four consecutive 429s (exceeding 3 retries) must raise RateLimitError."""
    for _ in range(4):
        httpx_mock.add_response(status_code=429)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        with pytest.raises(RateLimitError):
            client.search("persistent rate limit")


def test_5xx_retried(httpx_mock, search_response):
    """A 500 followed by success should return results."""
    httpx_mock.add_response(status_code=500)
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        results = client.search("server error retry")

    assert len(results) > 0


def test_4xx_not_retried(httpx_mock):
    """Non-429 4xx (e.g., 403) should raise APIError immediately without retry."""
    httpx_mock.add_response(status_code=403)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        with pytest.raises(APIError) as exc_info:
            client.search("forbidden")

    assert exc_info.value.status_code == 403


# ── Year filter ───────────────────────────────────────────────────────────────


def test_year_filter_both_bounds(httpx_mock, search_response):
    """year_from=2020, year_to=2024 should send year=2020-2024 param."""
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())
    filters = SearchFilters(year_from=2020, year_to=2024)

    with patch("time.sleep"):
        client.search("test", filters=filters)

    request = httpx_mock.get_request()
    assert "year=2020-2024" in str(request.url)


def test_year_filter_from_only(httpx_mock, search_response):
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())
    filters = SearchFilters(year_from=2022)

    with patch("time.sleep"):
        client.search("test", filters=filters)

    request = httpx_mock.get_request()
    assert "year=2022-" in str(request.url)


def test_year_filter_to_only(httpx_mock, search_response):
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())
    filters = SearchFilters(year_to=2020)

    with patch("time.sleep"):
        client.search("test", filters=filters)

    request = httpx_mock.get_request()
    assert "year=-2020" in str(request.url)


# ── get_paper_by_doi ──────────────────────────────────────────────────────────


def test_get_paper_by_doi_success(httpx_mock, single_paper_response):
    httpx_mock.add_response(json=single_paper_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        paper = client.get_paper_by_doi("10.1016/j.ijns.2023.104567")

    assert paper is not None
    assert paper.doi == "10.1016/j.ijns.2023.104567"
    assert paper.title.startswith("Nursing burnout during COVID-19")


def test_get_paper_by_doi_not_found(httpx_mock):
    httpx_mock.add_response(status_code=404)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        paper = client.get_paper_by_doi("10.9999/does.not.exist")

    assert paper is None


# ── Strategy dispatch ─────────────────────────────────────────────────────────


def test_strategy_recent_adds_year_filter(httpx_mock, search_response):
    """'recent' strategy should add a year_from filter for the last 3 years."""
    from datetime import datetime
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        client.search("nursing", strategy="recent")

    request = httpx_mock.get_request()
    current_year = datetime.now().year
    expected_year_from = current_year - 3
    assert f"year={expected_year_from}-" in str(request.url)


def test_strategy_review_filters_to_review_type(httpx_mock, search_response):
    """'review' strategy should send publicationTypes=Review."""
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        client.search("burnout review", strategy="review")

    request = httpx_mock.get_request()
    assert "publicationTypes=Review" in str(request.url)


def test_strategy_highly_cited_sends_sort(httpx_mock, search_response):
    """'highly_cited' strategy should send sort=citationCount:desc."""
    httpx_mock.add_response(json=search_response)
    client = _make_client(httpx.Client())

    with patch("time.sleep"):
        client.search("burnout", strategy="highly_cited")

    request = httpx_mock.get_request()
    assert "citationCount" in str(request.url)
