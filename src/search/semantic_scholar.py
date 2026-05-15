from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import httpx

from src.config import settings
from src.search.base import BaseSearchClient, RateLimiter, SearchFilters, SearchStrategy
from src.search.exceptions import APIError
from src.storage.schemas import Author, PaperCreate

BASE_URL = "https://api.semanticscholar.org/graph/v1"

DEFAULT_FIELDS = (
    "paperId,externalIds,title,abstract,year,venue,authors,"
    "citationCount,publicationTypes,publicationDate,openAccessPdf,url,fieldsOfStudy"
)

# Maps our SearchFilters.publication_types to S2 API publicationTypes values.
# None means S2 has no direct equivalent; handled via post-filter.
PUB_TYPE_MAPPING: dict[str, str | None] = {
    "journal": "JournalArticle",
    "review": "Review",
    "conference": "ConferencePaper",
    "preprint": None,
    "book_chapter": "BookSection",
}

_PREPRINT_VENUES = {"arxiv", "biorxiv", "medrxiv", "ssrn"}


def _is_preprint(paper: dict[str, Any]) -> bool:
    external_ids = paper.get("externalIds") or {}
    if "ArXiv" in external_ids:
        return True
    venue = (paper.get("venue") or "").lower()
    return any(pv in venue for pv in _PREPRINT_VENUES)


class SemanticScholarClient(BaseSearchClient):
    """Synchronous client for the Semantic Scholar Graph API."""

    def __init__(
        self,
        api_key: str | None = None,
        contact_email: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if api_key is None:
            api_key = settings.semantic_scholar_api_key

        self.api_key = api_key.strip() if api_key else ""
        contact_email = contact_email or settings.contact_email

        if self.api_key:
            self._auth_mode = "authenticated"
            rate = 0.8
        else:
            self._auth_mode = "unauthenticated"
            rate = 0.3

        super().__init__(
            rate_limiter=RateLimiter(max_per_second=rate),
            contact_email=contact_email,
            http_client=http_client,
        )
        self._headers: dict[str, str] = {}
        if self.api_key:
            self._headers["x-api-key"] = self.api_key

    @property
    def auth_mode(self) -> str:
        return self._auth_mode

    # ── Public interface ──────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        filters: SearchFilters | None = None,
        strategy: SearchStrategy = "relevance",
    ) -> list[PaperCreate]:
        filters = filters or SearchFilters()

        if strategy == "relevance":
            return self._search_relevance(query, limit, filters)

        if strategy == "recent":
            current_year = datetime.now().year
            f = filters.model_copy(
                update={"year_from": filters.year_from or (current_year - 3)}
            )
            return self._search_relevance(query, limit, f, sort="publicationDate:desc")

        if strategy == "highly_cited":
            return self._search_relevance(query, limit, filters, sort="citationCount:desc")

        if strategy == "review":
            f = filters.model_copy(update={"publication_types": ["review"]})
            return self._search_relevance(query, limit, f)

        return self._search_relevance(query, limit, filters)

    def get_paper_by_doi(self, doi: str) -> PaperCreate | None:
        url = f"{BASE_URL}/paper/DOI:{doi}"
        try:
            data = self._get(url, params={"fields": DEFAULT_FIELDS}, headers=self._headers)
        except APIError as exc:
            if exc.status_code == 404:
                return None
            raise
        return self._to_paper_create(data)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _search_relevance(
        self,
        query: str,
        limit: int,
        filters: SearchFilters,
        sort: str | None = None,
    ) -> list[PaperCreate]:
        params: dict[str, Any] = {
            "query": query,
            "limit": min(limit, 100),
            "fields": DEFAULT_FIELDS,
        }

        # Year range
        year_str = self._build_year_filter(filters.year_from, filters.year_to)
        if year_str:
            params["year"] = year_str

        # Publication types — skip preprint (no S2 equivalent), map the rest
        wants_preprint = "preprint" in filters.publication_types
        s2_types = [
            PUB_TYPE_MAPPING[pt]
            for pt in filters.publication_types
            if PUB_TYPE_MAPPING.get(pt) is not None
        ]
        if s2_types:
            params["publicationTypes"] = ",".join(s2_types)

        if filters.min_citation_count is not None:
            params["minCitationCount"] = filters.min_citation_count

        if filters.fields_of_study:
            params["fieldsOfStudy"] = ",".join(filters.fields_of_study)

        if sort:
            params["sort"] = sort

        data = self._get(f"{BASE_URL}/paper/search", params=params, headers=self._headers)
        papers_raw: list[dict[str, Any]] = data.get("data", [])

        results: list[PaperCreate] = []
        for raw in papers_raw:
            # Post-filter: open access
            if filters.open_access_only and not raw.get("openAccessPdf"):
                continue
            # Post-filter: preprint exclusion/inclusion
            if wants_preprint and not _is_preprint(raw):
                # If user ONLY wants preprints, skip non-preprints
                if filters.publication_types == ["preprint"]:
                    continue
            paper = self._to_paper_create(raw)
            if paper is not None:
                results.append(paper)

        return results

    def _to_paper_create(self, paper: dict[str, Any]) -> PaperCreate | None:
        try:
            external_ids: dict[str, str] = paper.get("externalIds") or {}
            raw_doi = external_ids.get("DOI")
            doi = raw_doi if raw_doi and re.match(r"^10\.\d{4,}/\S+$", raw_doi) else None

            authors = [
                Author(name=a.get("name", "Unknown"))
                for a in (paper.get("authors") or [])
                if a.get("name")
            ]

            url = paper.get("url")
            if not url and doi:
                url = f"https://doi.org/{doi}"

            return PaperCreate(
                doi=doi,
                title=paper["title"],
                authors=authors,
                year=paper.get("year"),
                venue=paper.get("venue"),
                abstract=paper.get("abstract"),
                citation_count=paper.get("citationCount"),
                source_api="semantic_scholar",
                semantic_scholar_id=paper.get("paperId"),
                openalex_id=None,
                url=url,
                raw_metadata=paper,
            )
        except Exception:
            return None

    @staticmethod
    def _build_year_filter(year_from: int | None, year_to: int | None) -> str | None:
        if year_from and year_to:
            return f"{year_from}-{year_to}"
        if year_from:
            return f"{year_from}-"
        if year_to:
            return f"-{year_to}"
        return None
