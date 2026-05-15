from datetime import datetime
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import Paper, Project, ProjectPaper
from .schemas import (
    PaperCreate,
    ProjectCreate,
    ProjectPaperCreate,
    ProjectPaperUpdate,
    ProjectUpdate,
)


# ── Projects ──────────────────────────────────────────────────────────────────

def create_project(session: Session, data: ProjectCreate) -> Project:
    """새 연구 프로젝트를 생성한다.

    Args:
        session: SQLAlchemy session.
        data: ProjectCreate schema with project details.

    Returns:
        Newly created Project ORM instance.
    """
    project = Project(**data.model_dump())
    session.add(project)
    session.flush()
    return project


def get_project(session: Session, project_id: int) -> Project | None:
    """ID로 프로젝트를 조회한다.

    Args:
        session: SQLAlchemy session.
        project_id: Primary key of the project.

    Returns:
        Project instance or None if not found.
    """
    return session.get(Project, project_id)


def get_project_by_name(session: Session, name: str) -> Project | None:
    """이름으로 프로젝트를 조회한다.

    Args:
        session: SQLAlchemy session.
        name: Exact project name.

    Returns:
        Project instance or None if not found.
    """
    return session.execute(
        select(Project).where(Project.name == name)
    ).scalar_one_or_none()


def list_projects(session: Session, limit: int = 100) -> list[Project]:
    """전체 프로젝트 목록을 반환한다.

    Args:
        session: SQLAlchemy session.
        limit: Maximum number of results.

    Returns:
        List of Project instances ordered by creation time (newest first).
    """
    return list(
        session.execute(
            select(Project).order_by(Project.created_at.desc()).limit(limit)
        ).scalars().all()
    )


def update_project(
    session: Session, project_id: int, data: ProjectUpdate
) -> Project | None:
    """프로젝트 필드를 부분 업데이트한다.

    Args:
        session: SQLAlchemy session.
        project_id: Primary key of the project.
        data: ProjectUpdate schema; only explicitly set fields are applied.

    Returns:
        Updated Project instance or None if not found.
    """
    project = get_project(session, project_id)
    if project is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(project, key, value)
    session.flush()
    return project


def delete_project(session: Session, project_id: int) -> bool:
    """프로젝트를 삭제한다 (관련 ProjectPaper 레코드도 cascade 삭제).

    Args:
        session: SQLAlchemy session.
        project_id: Primary key of the project.

    Returns:
        True if deleted, False if not found.
    """
    project = get_project(session, project_id)
    if project is None:
        return False
    session.delete(project)
    session.flush()
    return True


# ── Papers ────────────────────────────────────────────────────────────────────

def create_paper(session: Session, data: PaperCreate) -> Paper:
    """새 문헌 레코드를 생성한다.

    Args:
        session: SQLAlchemy session.
        data: PaperCreate schema.

    Returns:
        Newly created Paper ORM instance.
    """
    paper = Paper(
        doi=data.doi,
        title=data.title,
        authors=[a.model_dump() for a in data.authors],
        year=data.year,
        venue=data.venue,
        abstract=data.abstract,
        citation_count=data.citation_count,
        source_api=data.source_api,
        semantic_scholar_id=data.semantic_scholar_id,
        openalex_id=data.openalex_id,
        url=data.url,
        raw_metadata=data.raw_metadata,
    )
    session.add(paper)
    session.flush()
    return paper


def get_paper(session: Session, paper_id: int) -> Paper | None:
    """ID로 문헌을 조회한다.

    Args:
        session: SQLAlchemy session.
        paper_id: Primary key of the paper.

    Returns:
        Paper instance or None if not found.
    """
    return session.get(Paper, paper_id)


def get_paper_by_doi(session: Session, doi: str) -> Paper | None:
    """DOI로 문헌을 조회한다.

    Args:
        session: SQLAlchemy session.
        doi: DOI string (e.g. "10.1234/example").

    Returns:
        Paper instance or None if not found.
    """
    return session.execute(
        select(Paper).where(Paper.doi == doi)
    ).scalar_one_or_none()


def upsert_paper(session: Session, data: PaperCreate) -> Paper:
    """문헌을 insert-or-return한다.

    조회 우선순위:
    1. DOI가 있으면 DOI로 조회 → 존재하면 citation_count / url 업데이트 후 반환.
    2. DOI가 없으면 semantic_scholar_id → openalex_id 순으로 조회.
    3. 어느 것도 일치하지 않으면 새로 생성한다.

    Args:
        session: SQLAlchemy session.
        data: PaperCreate schema.

    Returns:
        Existing or newly created Paper instance.
    """
    if data.doi:
        existing = get_paper_by_doi(session, data.doi)
        if existing:
            _apply_mutable_updates(existing, data)
            session.flush()
            return existing
    else:
        if data.semantic_scholar_id:
            existing = session.execute(
                select(Paper).where(Paper.semantic_scholar_id == data.semantic_scholar_id)
            ).scalar_one_or_none()
            if existing:
                _apply_mutable_updates(existing, data)
                session.flush()
                return existing

        if data.openalex_id:
            existing = session.execute(
                select(Paper).where(Paper.openalex_id == data.openalex_id)
            ).scalar_one_or_none()
            if existing:
                _apply_mutable_updates(existing, data)
                session.flush()
                return existing

    return create_paper(session, data)


def _apply_mutable_updates(paper: Paper, data: PaperCreate) -> None:
    if data.citation_count is not None:
        paper.citation_count = data.citation_count
    if data.url and not paper.url:
        paper.url = data.url


def search_papers(session: Session, keyword: str, limit: int = 50) -> list[Paper]:
    """title 또는 abstract에서 키워드를 대소문자 무관하게 검색한다.

    Args:
        session: SQLAlchemy session.
        keyword: Search term (partial match).
        limit: Maximum number of results.

    Returns:
        List of matching Paper instances.
    """
    pattern = f"%{keyword}%"
    return list(
        session.execute(
            select(Paper)
            .where(
                or_(
                    Paper.title.ilike(pattern),
                    Paper.abstract.ilike(pattern),
                )
            )
            .limit(limit)
        ).scalars().all()
    )


# ── ProjectPapers ─────────────────────────────────────────────────────────────

def add_paper_to_project(
    session: Session,
    project_id: int,
    paper_id: int,
    data: ProjectPaperCreate | None = None,
) -> ProjectPaper:
    """문헌을 프로젝트에 연결한다. 이미 존재하면 기존 레코드를 반환한다.

    Args:
        session: SQLAlchemy session.
        project_id: Target project ID.
        paper_id: Paper ID to associate.
        data: Optional metadata for the association.

    Returns:
        Existing or newly created ProjectPaper instance.
    """
    existing = session.execute(
        select(ProjectPaper).where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()

    if existing:
        return existing

    kwargs = data.model_dump(exclude_none=True) if data else {}
    pp = ProjectPaper(project_id=project_id, paper_id=paper_id, **kwargs)
    session.add(pp)
    session.flush()
    return pp


def update_project_paper(
    session: Session, pp_id: int, data: ProjectPaperUpdate
) -> ProjectPaper | None:
    """ProjectPaper 레코드를 부분 업데이트한다.

    Args:
        session: SQLAlchemy session.
        pp_id: Primary key of the ProjectPaper record.
        data: ProjectPaperUpdate schema; only explicitly set fields are applied.

    Returns:
        Updated ProjectPaper instance or None if not found.
    """
    pp = session.get(ProjectPaper, pp_id)
    if pp is None:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(pp, key, value)
    session.flush()
    return pp


def confirm_paper(session: Session, project_id: int, paper_id: int) -> ProjectPaper | None:
    """ProjectPaper 상태를 'confirmed'로 변경한다.

    Args:
        session: SQLAlchemy session.
        project_id: Project ID.
        paper_id: Paper ID.

    Returns:
        Updated ProjectPaper instance or None if association not found.
    """
    pp = session.execute(
        select(ProjectPaper).where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()
    if pp is None:
        return None
    pp.status = "confirmed"
    session.flush()
    return pp


def reject_paper(session: Session, project_id: int, paper_id: int) -> ProjectPaper | None:
    """ProjectPaper 상태를 'rejected'로 변경한다.

    Args:
        session: SQLAlchemy session.
        project_id: Project ID.
        paper_id: Paper ID.

    Returns:
        Updated ProjectPaper instance or None if association not found.
    """
    pp = session.execute(
        select(ProjectPaper).where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()
    if pp is None:
        return None
    pp.status = "rejected"
    session.flush()
    return pp


def list_project_papers(
    session: Session,
    project_id: int,
    status: str | None = None,
) -> list[ProjectPaper]:
    """프로젝트에 연결된 문헌 목록을 반환한다.

    Args:
        session: SQLAlchemy session.
        project_id: Project ID to filter by.
        status: Optional status filter ("suggested", "confirmed", "rejected").

    Returns:
        List of ProjectPaper instances.
    """
    stmt = select(ProjectPaper).where(ProjectPaper.project_id == project_id)
    if status is not None:
        stmt = stmt.where(ProjectPaper.status == status)
    return list(session.execute(stmt).scalars().all())


def remove_paper_from_project(
    session: Session, project_id: int, paper_id: int
) -> bool:
    """프로젝트에서 문헌 연결을 제거한다 (Paper 레코드 자체는 삭제하지 않음)."""
    pp = session.execute(
        select(ProjectPaper).where(
            ProjectPaper.project_id == project_id,
            ProjectPaper.paper_id == paper_id,
        )
    ).scalar_one_or_none()
    if pp is None:
        return False
    session.delete(pp)
    session.flush()
    return True


# ── Aggregate / Dashboard helpers ─────────────────────────────────────────────

def count_project_papers(
    session: Session, project_id: int, status: str | None = None
) -> int:
    stmt = (
        select(func.count())
        .select_from(ProjectPaper)
        .where(ProjectPaper.project_id == project_id)
    )
    if status is not None:
        stmt = stmt.where(ProjectPaper.status == status)
    return session.execute(stmt).scalar_one()


def count_all_papers(session: Session) -> int:
    return session.execute(select(func.count()).select_from(Paper)).scalar_one()


def count_all_projects(session: Session) -> int:
    return session.execute(select(func.count()).select_from(Project)).scalar_one()


def count_papers_this_month(session: Session) -> int:
    now = datetime.now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return session.execute(
        select(func.count()).select_from(Paper).where(Paper.added_at >= start)
    ).scalar_one()


def get_recent_projects(session: Session, limit: int = 5) -> list[Project]:
    return list(
        session.execute(
            select(Project).order_by(Project.updated_at.desc()).limit(limit)
        ).scalars().all()
    )


def get_distinct_tags(session: Session, project_id: int) -> list[str]:
    pps = list_project_papers(session, project_id)
    tags: set[str] = set()
    for pp in pps:
        if pp.tags:
            tags.update(pp.tags)
    return sorted(tags)


def list_project_papers_with_filters(
    session: Session,
    project_id: int,
    status: str | None = None,
    tags: list[str] | None = None,
    sort_by: str = "added_at",
    sort_desc: bool = True,
) -> list[ProjectPaper]:
    from sqlalchemy.orm import joinedload

    stmt = (
        select(ProjectPaper)
        .options(joinedload(ProjectPaper.paper))
        .where(ProjectPaper.project_id == project_id)
    )
    if status is not None:
        stmt = stmt.where(ProjectPaper.status == status)
    results = list(session.execute(stmt).scalars().all())

    if tags:
        results = [
            pp for pp in results
            if pp.tags and any(t in pp.tags for t in tags)
        ]

    def _key(pp: ProjectPaper):
        if sort_by == "year":
            return pp.paper.year or 0
        if sort_by == "citation_count":
            return pp.paper.citation_count or 0
        if sort_by == "title":
            return (pp.paper.title or "").lower()
        return pp.added_at

    results.sort(key=_key, reverse=sort_desc)
    return results
