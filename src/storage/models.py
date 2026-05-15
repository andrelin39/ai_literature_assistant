from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now()


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    research_question: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project_papers: Mapped[list["ProjectPaper"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doi: Mapped[str | None] = mapped_column(String(500), unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    year: Mapped[int | None] = mapped_column(Integer)
    venue: Mapped[str | None] = mapped_column(String(500))
    abstract: Mapped[str | None] = mapped_column(Text)
    citation_count: Mapped[int | None] = mapped_column(Integer)
    source_api: Mapped[str] = mapped_column(String(50), nullable=False)
    semantic_scholar_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    openalex_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    url: Mapped[str | None] = mapped_column(Text)
    raw_metadata: Mapped[Any] = mapped_column(JSON, nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    project_papers: Mapped[list["ProjectPaper"]] = relationship(
        back_populates="paper",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_papers_title", "title"),
        Index("ix_papers_year", "year"),
        Index("ix_papers_citation_count", "citation_count"),
    )


class ProjectPaper(Base):
    __tablename__ = "project_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="suggested")
    key_points: Mapped[Any] = mapped_column(JSON, nullable=True)
    why_cite: Mapped[str | None] = mapped_column(Text)
    how_to_cite: Mapped[str | None] = mapped_column(Text)
    relevance_to_project: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[Any] = mapped_column(JSON, nullable=True)
    user_notes: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    project: Mapped["Project"] = relationship(back_populates="project_papers")
    paper: Mapped["Paper"] = relationship(back_populates="project_papers")

    __table_args__ = (
        UniqueConstraint("project_id", "paper_id", name="uq_project_paper"),
    )


class EvaluationHistory(Base):
    __tablename__ = "evaluation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    paragraph_text: Mapped[str] = mapped_column(Text, nullable=False)
    evaluated_paper_ids: Mapped[Any] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[Any] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class CitationNetwork(Base):
    __tablename__ = "citation_network"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    cited_paper_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("papers.id", ondelete="CASCADE"), nullable=False
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_paper_id", "cited_paper_id", "relation_type",
            name="uq_citation",
        ),
    )
