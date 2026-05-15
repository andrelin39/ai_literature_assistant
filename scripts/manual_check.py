"""Manual verification script for src/storage.

Usage:
    uv run python scripts/manual_check.py

Requires ANTHROPIC_API_KEY in .env (or environment).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Allow running without a real API key; storage layer doesn't use it.
os.environ.setdefault("ANTHROPIC_API_KEY", "manual-check-placeholder")

from src.storage import crud, get_session, init_db
from src.storage.schemas import PaperCreate, ProjectCreate, ProjectPaperCreate


def main() -> None:
    print("=== manual_check.py ===\n")

    # Clean up previous run so inserts don't collide.
    try:
        from src.config import get_config
        db_path = get_config().database_path
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"0. Removed existing DB: {db_path!r}")
    except Exception:
        pass

    print("1. init_db() ...")
    init_db()
    print("   done.\n")

    with get_session() as session:
        # ── Project ──────────────────────────────────────────────────────────
        proj = crud.create_project(
            session,
            ProjectCreate(
                name="Manual Check Project",
                description="Created by manual_check.py",
                research_question="Does storage work correctly?",
            ),
        )
        session.flush()
        print(f"2. Project created  → id={proj.id}, name={proj.name!r}")

        # ── Paper with DOI ────────────────────────────────────────────────────
        paper = crud.create_paper(
            session,
            PaperCreate(
                doi="10.1234/manual.check.2024",
                title="Manual Check Test Paper",
                authors=[{"name": "Test Author", "affiliation": "Test University"}],
                year=2024,
                venue="Journal of Testing",
                abstract="This paper verifies that the storage layer works.",
                citation_count=42,
                source_api="manual",
            ),
        )
        session.flush()
        print(f"3. Paper created    → id={paper.id}, doi={paper.doi!r}, year={paper.year}")

        # ── Paper without DOI ─────────────────────────────────────────────────
        paper_no_doi = crud.create_paper(
            session,
            PaperCreate(
                title="No-DOI Test Paper",
                authors=[{"name": "Another Author"}],
                year=2023,
                source_api="semantic_scholar",
                semantic_scholar_id="SS-manual-check-001",
            ),
        )
        session.flush()
        print(f"4. Paper (no DOI)   → id={paper_no_doi.id}, SS_id={paper_no_doi.semantic_scholar_id!r}")

        # ── upsert_paper: same DOI → returns existing ─────────────────────────
        paper_again = crud.upsert_paper(
            session,
            PaperCreate(
                doi="10.1234/manual.check.2024",
                title="Should not create duplicate",
                authors=[],
                source_api="crossref",
                citation_count=99,
            ),
        )
        session.flush()
        assert paper_again.id == paper.id, "upsert should return existing paper"
        print(f"5. upsert_paper     → same id={paper_again.id}, updated citation_count={paper_again.citation_count}")

        # ── ProjectPaper ──────────────────────────────────────────────────────
        pp = crud.add_paper_to_project(
            session,
            proj.id,
            paper.id,
            data=ProjectPaperCreate(
                status="suggested",
                key_points=["storage works", "CRUD is correct"],
                tags=["test", "verification"],
            ),
        )
        session.flush()
        print(f"6. ProjectPaper     → id={pp.id}, status={pp.status!r}, tags={pp.tags}")

        confirmed = crud.confirm_paper(session, proj.id, paper.id)
        print(f"7. confirm_paper    → status={confirmed.status!r}")

        papers_in_proj = crud.list_project_papers(session, proj.id)
        print(f"8. list_project_papers → {len(papers_in_proj)} record(s)")

        found = crud.search_papers(session, "Manual Check")
        print(f"9. search_papers('Manual Check') → {len(found)} result(s): {[p.title for p in found]}")

        session.commit()

    # ── Check DB file ─────────────────────────────────────────────────────────
    print("\n--- DB file check ---")
    try:
        from src.config import get_config
        db_path = get_config().database_path
        if os.path.exists(db_path):
            size = os.path.getsize(db_path)
            print(f"  {db_path!r}  ->  {size:,} bytes  [OK]")
        else:
            print(f"  {db_path!r}  ->  NOT FOUND  [FAIL]")
    except Exception as e:
        print(f"  Could not read db path: {e}")

    print("\n=== All checks passed ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}")
        print("Tip: ensure .env has ANTHROPIC_API_KEY set.")
        sys.exit(1)
