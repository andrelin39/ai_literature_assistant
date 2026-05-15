import os

# Must be set before any src imports so that get_config() validation passes.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")
os.environ.setdefault("CONTACT_EMAIL", "test@example.com")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.storage.database import Base
from src.storage import crud
from src.storage.schemas import PaperCreate, ProjectCreate


@pytest.fixture(scope="session")
def db_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_fk_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    session = Session(db_engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_project(db_session):
    proj = crud.create_project(
        db_session,
        ProjectCreate(
            name="Sample Project",
            description="A fixture project",
            research_question="Does X affect Y?",
        ),
    )
    db_session.flush()
    return proj


@pytest.fixture
def sample_paper(db_session):
    paper = crud.create_paper(
        db_session,
        PaperCreate(
            doi="10.1234/fixture.001",
            title="Fixture Paper with DOI",
            authors=[{"name": "Alice Smith", "affiliation": "Test University"}],
            year=2023,
            source_api="manual",
        ),
    )
    db_session.flush()
    return paper


@pytest.fixture
def sample_paper_no_doi(db_session):
    paper = crud.create_paper(
        db_session,
        PaperCreate(
            title="Fixture Paper without DOI",
            authors=[{"name": "Bob Jones"}],
            year=2022,
            source_api="manual",
            semantic_scholar_id="SS-fixture-001",
        ),
    )
    db_session.flush()
    return paper
