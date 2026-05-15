import pytest
from sqlalchemy.exc import IntegrityError

from src.storage.models import Paper, Project, ProjectPaper


def test_create_project(db_session):
    proj = Project(name="ORM Project")
    db_session.add(proj)
    db_session.flush()
    assert proj.id is not None
    assert proj.created_at is not None
    assert proj.updated_at is not None


def test_create_paper_with_doi(db_session):
    paper = Paper(
        doi="10.9999/orm.test.001",
        title="ORM Test Paper",
        authors=[{"name": "Jane Doe"}],
        source_api="manual",
    )
    db_session.add(paper)
    db_session.flush()
    assert paper.id is not None
    assert paper.added_at is not None


def test_paper_belongs_to_multiple_projects(db_session):
    paper = Paper(title="Shared Paper", authors=[], source_api="manual")
    proj1 = Project(name="Project Alpha ORM")
    proj2 = Project(name="Project Beta ORM")
    db_session.add_all([paper, proj1, proj2])
    db_session.flush()

    db_session.add(ProjectPaper(project_id=proj1.id, paper_id=paper.id))
    db_session.add(ProjectPaper(project_id=proj2.id, paper_id=paper.id))
    db_session.flush()

    db_session.refresh(proj1)
    db_session.refresh(proj2)
    assert len(proj1.project_papers) == 1
    assert len(proj2.project_papers) == 1
    assert proj1.project_papers[0].paper_id == paper.id
    assert proj2.project_papers[0].paper_id == paper.id


def test_project_contains_multiple_papers(db_session):
    proj = Project(name="Multi-Paper Project ORM")
    p1 = Paper(title="ORM Paper 1", authors=[], source_api="manual")
    p2 = Paper(title="ORM Paper 2", authors=[], source_api="manual")
    db_session.add_all([proj, p1, p2])
    db_session.flush()

    db_session.add_all([
        ProjectPaper(project_id=proj.id, paper_id=p1.id),
        ProjectPaper(project_id=proj.id, paper_id=p2.id),
    ])
    db_session.flush()

    db_session.refresh(proj)
    assert len(proj.project_papers) == 2


def test_unique_constraint_project_paper(db_session):
    proj = Project(name="Unique Constraint Project")
    paper = Paper(title="Unique Constraint Paper", authors=[], source_api="manual")
    db_session.add_all([proj, paper])
    db_session.flush()

    db_session.add(ProjectPaper(project_id=proj.id, paper_id=paper.id))
    db_session.flush()

    db_session.add(ProjectPaper(project_id=proj.id, paper_id=paper.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_doi_uniqueness(db_session):
    p1 = Paper(doi="10.9999/dup.doi.001", title="DOI Paper One", authors=[], source_api="manual")
    db_session.add(p1)
    db_session.flush()

    p2 = Paper(doi="10.9999/dup.doi.001", title="DOI Paper Two", authors=[], source_api="manual")
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_multiple_papers_without_doi_allowed(db_session):
    p1 = Paper(title="No DOI Paper A", authors=[], source_api="manual")
    p2 = Paper(title="No DOI Paper B", authors=[], source_api="manual")
    db_session.add_all([p1, p2])
    db_session.flush()  # should not raise
    assert p1.id is not None
    assert p2.id is not None
    assert p1.id != p2.id


def test_delete_project_cascades_project_papers_not_paper(db_session):
    proj = Project(name="Cascade Delete Project")
    paper = Paper(title="Survivor Paper ORM", authors=[], source_api="manual")
    db_session.add_all([proj, paper])
    db_session.flush()

    pp = ProjectPaper(project_id=proj.id, paper_id=paper.id)
    db_session.add(pp)
    db_session.flush()
    pp_id = pp.id
    paper_id = paper.id

    db_session.delete(proj)
    db_session.flush()

    assert db_session.get(ProjectPaper, pp_id) is None
    assert db_session.get(Paper, paper_id) is not None
