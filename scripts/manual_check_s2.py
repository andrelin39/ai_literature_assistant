"""Manual verification script for SemanticScholarClient.

Run:  uv run python scripts/manual_check_s2.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Ensure project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

# Provide a dummy value so Settings validation doesn't fail when
# ANTHROPIC_API_KEY isn't set in the shell (only S2 key is needed here).
os.environ.setdefault("ANTHROPIC_API_KEY", "dummy-for-manual-check")
os.environ.setdefault("CONTACT_EMAIL", "dummy@example.com")

from src.search import SearchFilters, SemanticScholarClient
from src.search.exceptions import SearchError

QUERY = "nursing burnout COVID-19"
STRATEGIES = ["relevance", "recent", "highly_cited", "review"]
LIMIT = 5


def _banner(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def _print_paper(i: int, paper) -> None:
    title = (paper.title or "(no title)")[:80]
    doi = paper.doi or "(no DOI)"
    year = paper.year or "n/a"
    cites = paper.citation_count if paper.citation_count is not None else "n/a"
    print(f"  [{i + 1}] {title}")
    print(f"       year={year}  citations={cites}  doi={doi}")


def main() -> None:
    client = SemanticScholarClient()
    rate = 0.8 if client.auth_mode == "authenticated" else 0.3
    print(f"\nMode: {client.auth_mode} ({rate} req/s)")
    print(f"Query: {QUERY!r}")

    # Shorter sleep is safe in authenticated mode
    sleep_between = 1.0 if client.auth_mode == "authenticated" else 5.0

    total_start = time.monotonic()
    api_call_count = 0
    found_doi: str | None = None

    for idx, strategy in enumerate(STRATEGIES):
        if idx > 0:
            print(f"\n  (waiting {sleep_between}s between strategies...)")
            time.sleep(sleep_between)

        _banner(f"Strategy: {strategy}  (limit={LIMIT})")
        t0 = time.monotonic()
        try:
            results = client.search(QUERY, limit=LIMIT, strategy=strategy)
            api_call_count += 1
        except SearchError as exc:
            print(f"  ERROR: {exc}")
            continue
        elapsed = time.monotonic() - t0

        print(f"  Returned: {len(results)} paper(s)  [{elapsed:.2f}s]")
        for i, p in enumerate(results):
            _print_paper(i, p)
            if found_doi is None and p.doi:
                found_doi = p.doi

    # Test get_paper_by_doi with a DOI from search results (or fallback)
    _banner("get_paper_by_doi")
    if found_doi:
        test_doi = found_doi
    else:
        test_doi = "10.1016/j.nepr.2023.103643"  # known S2 paper

    print(f"  DOI: {test_doi}")
    print(f"  (waiting {sleep_between}s before fetch...)")
    time.sleep(sleep_between)
    t0 = time.monotonic()
    try:
        paper = client.get_paper_by_doi(test_doi)
        api_call_count += 1
    except SearchError as exc:
        print(f"  ERROR: {exc}")
        paper = None
    elapsed = time.monotonic() - t0

    if paper:
        title_safe = paper.title[:80].encode("ascii", errors="replace").decode("ascii")
        print(f"  Found: {title_safe!r}  [{elapsed:.2f}s]")
        names = [a.name.encode("ascii", errors="replace").decode("ascii") for a in paper.authors[:3]]
        print(f"  authors: {names}")
    else:
        print(f"  Not found [{elapsed:.2f}s]")

    total_elapsed = time.monotonic() - total_start
    _banner("Summary")
    print(f"  Total elapsed : {total_elapsed:.2f}s")
    print(f"  API calls made: {api_call_count}")
    avg = total_elapsed / api_call_count if api_call_count else 0
    print(f"  Avg per call  : {avg:.2f}s  (includes rate limiter + inter-strategy sleep)")


if __name__ == "__main__":
    main()
