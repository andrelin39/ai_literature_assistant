from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class Author(BaseModel):
    name: str
    affiliation: str | None = None


# ── Project ──────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    research_question: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    research_question: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    research_question: str | None
    created_at: datetime
    updated_at: datetime


# ── Paper ─────────────────────────────────────────────────────────────────────

class PaperCreate(BaseModel):
    doi: str | None = None
    title: str
    authors: list[Author] = []
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    citation_count: int | None = None
    source_api: str
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    url: str | None = None
    raw_metadata: dict[str, Any] | None = None

    @field_validator("doi")
    @classmethod
    def validate_doi(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^10\.\d{4,}/\S+$", v):
            raise ValueError(f"Invalid DOI format: {v!r}")
        return v


class PaperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doi: str | None
    title: str
    authors: list[Any]
    year: int | None
    venue: str | None
    abstract: str | None
    citation_count: int | None
    source_api: str
    semantic_scholar_id: str | None
    openalex_id: str | None
    url: str | None
    added_at: datetime


# ── ProjectPaper ──────────────────────────────────────────────────────────────

class ProjectPaperCreate(BaseModel):
    status: Literal["suggested", "confirmed", "rejected"] = "suggested"
    key_points: list[str] | None = None
    why_cite: str | None = None
    how_to_cite: str | None = None
    relevance_to_project: str | None = None
    tags: list[str] | None = None
    user_notes: str | None = None


class ProjectPaperUpdate(BaseModel):
    status: Literal["suggested", "confirmed", "rejected"] | None = None
    key_points: list[str] | None = None
    why_cite: str | None = None
    how_to_cite: str | None = None
    relevance_to_project: str | None = None
    tags: list[str] | None = None
    user_notes: str | None = None


class ProjectPaperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    paper_id: int
    status: str
    key_points: list[str] | None
    why_cite: str | None
    how_to_cite: str | None
    relevance_to_project: str | None
    tags: list[str] | None
    user_notes: str | None
    added_at: datetime
    updated_at: datetime
