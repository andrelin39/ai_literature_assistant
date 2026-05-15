import pytest

from src.storage import crud
from src.storage.schemas import (
    PaperCreate,
    ProjectCreate,
    ProjectPaperCreate,
    ProjectPaperUpdate,
    ProjectUpdate,
)


# ── Projects ──────────────────────────────────────────────────────────────────

def test_create_and_get_project(db_session):
    proj = crud.create_project(db_session, ProjectCreate(name="CRUD Project A"))
    assert proj.id is not None

    fetched = crud.get_project(db_session, proj.id)
    assert fetched is not None
    assert fetched.name == "CRUD Project A"


def test_get_project_by_name(db_session):
    crud.create_project(db_session, ProjectCreate(name="Named Project"))
    found = crud.get_project_by_name(db_session, "Named Project")
    assert found is not None
    assert found.name == "Named Project"


def test_get_project_not_found(db_session):
    assert crud.get_project(db_session, 999999) is None


def test_list_projects(db_session):
    crud.create_project(db_session, ProjectCreate(name="List Project 1"))
    crud.create_project(db_session, ProjectCreate(name="List Project 2"))
    projects = crud.list_projects(db_session)
    names = [p.name for p in projects]
    assert "List Project 1" in names
    assert "List Project 2" in names


def test_update_project(db_session):
    proj = crud.create_project(db_session, ProjectCreate(name="Before Update"))
    updated = crud.update_project(
        db_session, proj.id, ProjectUpdate(name="After Update", description="New desc")
    )
    assert updated is not None
    assert updated.name == "After Update"
    assert updated.description == "New desc"


def test_update_project_partial(db_session):
    proj = crud.create_project(
        db_session,
        ProjectCreate(name="Partial Update Project", description="Original"),
    )
    updated = crud.update_project(
        db_session, proj.id, ProjectUpdate(description="Changed")
    )
    assert updated.name == "Partial Update Project"
    assert updated.description == "Changed"


def test_update_project_not_found(db_session):
    result = crud.update_project(db_session, 999999, ProjectUpdate(name="X"))
    assert result is None


def test_delete_project(db_session):
    proj = crud.create_project(db_session, ProjectCreate(name="To Delete"))
    assert crud.delete_project(db_session, proj.id) is True
    assert crud.get_project(db_session, proj.id) is None


def test_delete_project_not_found(db_session):
    assert crud.delete_project(db_session, 999999) is False


# ── Papers ────────────────────────────────────────────────────────────────────

def test_create_paper_with_doi(db_session):
    paper = crud.create_paper(
        db_session,
        PaperCreate(
            doi="10.1111/crud.test.001",
            title="CRUD Test Paper",
            authors=[{"name": "Author X"}],
            year=2024,
            source_api="semantic_scholar",
        ),
    )
    assert paper.id is not None
    assert paper.doi == "10.1111/crud.test.001"
    assert paper.authors[0]["name"] == "Author X"


def test_create_paper_without_doi(db_session):
    paper = crud.create_paper(
        db_session,
        PaperCreate(
            title="No DOI CRUD Paper",
            authors=[],
            source_api="manual",
            semantic_scholar_id="SS-crud-999",
        ),
    )
    assert paper.id is not None
    assert paper.doi is None
    assert paper.semantic_scholar_id == "SS-crud-999"


def test_get_paper_by_doi(db_session, sample_paper):
    found = crud.get_paper_by_doi(db_session, sample_paper.doi)
    assert found is not None
    assert found.id == sample_paper.id


def test_upsert_paper_same_doi_no_duplicate(db_session):
    data = PaperCreate(
        doi="10.2222/upsert.001",
        title="Upsert Paper",
        authors=[],
        source_api="manual",
        citation_count=10,
    )
    p1 = crud.upsert_paper(db_session, data)

    data2 = PaperCreate(
        doi="10.2222/upsert.001",
        title="Upsert Paper (dup attempt)",
        authors=[],
        source_api="crossref",
        citation_count=42,
    )
    p2 = crud.upsert_paper(db_session, data2)

    assert p1.id == p2.id
    assert p2.citation_count == 42  # mutable field updated


def test_upsert_paper_same_semantic_scholar_id(db_session):
    data = PaperCreate(
        title="SS Paper Original",
        authors=[],
        source_api="semantic_scholar",
        semantic_scholar_id="SS-upsert-unique-001",
        citation_count=5,
    )
    p1 = crud.upsert_paper(db_session, data)

    data2 = PaperCreate(
        title="SS Paper Duplicate Attempt",
        authors=[],
        source_api="semantic_scholar",
        semantic_scholar_id="SS-upsert-unique-001",
        citation_count=99,
    )
    p2 = crud.upsert_paper(db_session, data2)

    assert p1.id == p2.id
    assert p2.citation_count == 99


def test_upsert_paper_new_paper_created(db_session):
    data = PaperCreate(
        doi="10.3333/brand.new.001",
        title="Brand New Paper",
        authors=[],
        source_api="openalex",
    )
    paper = crud.upsert_paper(db_session, data)
    assert paper.id is not None
    assert paper.doi == "10.3333/brand.new.001"


def test_search_papers_by_title(db_session):
    crud.create_paper(
        db_session,
        PaperCreate(
            title="Machine Learning in Healthcare",
            authors=[],
            source_api="manual",
        ),
    )
    crud.create_paper(
        db_session,
        PaperCreate(
            title="Deep Learning for NLP",
            authors=[],
            source_api="manual",
        ),
    )
    results = crud.search_papers(db_session, "learning")
    titles = [p.title for p in results]
    assert "Machine Learning in Healthcare" in titles
    assert "Deep Learning for NLP" in titles


def test_search_papers_by_abstract(db_session):
    crud.create_paper(
        db_session,
        PaperCreate(
            title="Abstract Search Test",
            abstract="This study investigates systematic review methodology.",
            authors=[],
            source_api="manual",
        ),
    )
    results = crud.search_papers(db_session, "systematic review")
    assert any(p.title == "Abstract Search Test" for p in results)


def test_search_papers_case_insensitive(db_session):
    crud.create_paper(
        db_session,
        PaperCreate(title="COVID-19 Outcomes Study", authors=[], source_api="manual"),
    )
    results = crud.search_papers(db_session, "covid")
    assert any("COVID-19" in p.title for p in results)


# ── ProjectPapers ─────────────────────────────────────────────────────────────

def test_add_paper_to_project(db_session, sample_project, sample_paper):
    pp = crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    assert pp.id is not None
    assert pp.status == "suggested"
    assert pp.project_id == sample_project.id
    assert pp.paper_id == sample_paper.id


def test_add_paper_to_project_no_duplicate(db_session, sample_project, sample_paper):
    pp1 = crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    pp2 = crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    assert pp1.id == pp2.id


def test_add_paper_to_project_with_metadata(db_session, sample_project, sample_paper):
    pp = crud.add_paper_to_project(
        db_session,
        sample_project.id,
        sample_paper.id,
        data=ProjectPaperCreate(
            status="confirmed",
            key_points=["key finding A", "key finding B"],
            tags=["RCT", "meta-analysis"],
            why_cite="Strong evidence base",
        ),
    )
    assert pp.status == "confirmed"
    assert pp.key_points == ["key finding A", "key finding B"]
    assert pp.tags == ["RCT", "meta-analysis"]


def test_confirm_paper(db_session, sample_project, sample_paper):
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    pp = crud.confirm_paper(db_session, sample_project.id, sample_paper.id)
    assert pp is not None
    assert pp.status == "confirmed"


def test_reject_paper(db_session, sample_project, sample_paper):
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    pp = crud.reject_paper(db_session, sample_project.id, sample_paper.id)
    assert pp is not None
    assert pp.status == "rejected"


def test_confirm_paper_not_found(db_session, sample_project):
    result = crud.confirm_paper(db_session, sample_project.id, 999999)
    assert result is None


def test_list_project_papers_all(db_session, sample_project, sample_paper, sample_paper_no_doi):
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper_no_doi.id)
    results = crud.list_project_papers(db_session, sample_project.id)
    assert len(results) == 2


def test_list_project_papers_status_filter(db_session, sample_project, sample_paper, sample_paper_no_doi):
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    crud.add_paper_to_project(
        db_session,
        sample_project.id,
        sample_paper_no_doi.id,
        data=ProjectPaperCreate(status="confirmed"),
    )
    confirmed = crud.list_project_papers(db_session, sample_project.id, status="confirmed")
    suggested = crud.list_project_papers(db_session, sample_project.id, status="suggested")
    assert len(confirmed) == 1
    assert len(suggested) == 1
    assert confirmed[0].paper_id == sample_paper_no_doi.id


def test_update_project_paper(db_session, sample_project, sample_paper):
    pp = crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    updated = crud.update_project_paper(
        db_session,
        pp.id,
        ProjectPaperUpdate(
            why_cite="Highly relevant RCT",
            tags=["clinical-trial"],
        ),
    )
    assert updated is not None
    assert updated.why_cite == "Highly relevant RCT"
    assert updated.tags == ["clinical-trial"]
    assert updated.status == "suggested"  # unchanged


def test_remove_paper_from_project(db_session, sample_project, sample_paper):
    crud.add_paper_to_project(db_session, sample_project.id, sample_paper.id)
    removed = crud.remove_paper_from_project(db_session, sample_project.id, sample_paper.id)
    assert removed is True

    papers = crud.list_project_papers(db_session, sample_project.id)
    assert len(papers) == 0

    # Paper itself still exists
    assert crud.get_paper(db_session, sample_paper.id) is not None


def test_remove_paper_not_found(db_session, sample_project):
    result = crud.remove_paper_from_project(db_session, sample_project.id, 999999)
    assert result is False
