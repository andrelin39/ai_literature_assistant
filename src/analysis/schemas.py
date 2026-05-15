"""Pydantic schemas for AI analysis output — grounded facts and inferred reasoning."""
from __future__ import annotations

import copy
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class Citation(BaseModel):
    """Abstract 原文證據片段，用於支撐 grounded fact"""

    text: str = Field(
        ...,
        description="從 abstract 中擷取的原句（10-300 字元）",
        min_length=10,
        max_length=300,
    )

    @field_validator("text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class GroundedField(BaseModel, Generic[T]):
    """Grounded 事實：值 + 證據 + 信心度"""

    value: T | None = Field(..., description="提取的值，若 abstract 未提及則為 null")
    evidence: Citation | None = Field(None, description="abstract 中的支撐原句")
    confidence: Literal["grounded", "uncertain", "not_found"] = "grounded"


class InferredField(BaseModel, Generic[T]):
    """Inferred 推論：明確標記為 AI 推論"""

    value: T
    reasoning: str = Field(..., description="推論依據（基於哪些 abstract 資訊推論）")
    confidence: Literal["high", "medium", "low"] = "medium"


class StudyDesign(BaseModel):
    type: str | None = None
    sample_size: int | None = None
    population: str | None = None


class KeyFinding(BaseModel):
    statement: str
    evidence: Citation


class CitationContext(BaseModel):
    context_type: Literal["background", "method", "comparison", "support", "contrast", "gap"]
    description: str
    example_sentence: str


class CrossPaperRelation(BaseModel):
    relation_type: Literal[
        "similar_topic",
        "opposing_view",
        "methodological_parallel",
        "extends",
        "contradicted_by",
    ]
    target_paper_index: int
    description: str


class PaperAnalysis(BaseModel):
    # === Grounded（必須有 abstract 證據）===
    research_question: GroundedField[str]
    study_design: GroundedField[StudyDesign]
    key_findings: list[KeyFinding] = Field(..., min_length=1, max_length=5)

    # === Inferred（AI 推論，明確標記）===
    why_relevant: InferredField[str] = Field(
        ..., description="為何此文獻可能對使用者主題有用"
    )
    citation_contexts: list[CitationContext] = Field(..., min_length=1, max_length=4)
    limitations_or_gaps: InferredField[str] | None = None

    # === Meta ===
    abstract_quality: Literal["complete", "partial", "minimal"] = Field(
        ..., description="abstract 資訊完整度"
    )
    cannot_analyze_reason: str | None = None


class ComparisonAnalysis(BaseModel):
    """跨文獻關聯性分析"""

    common_themes: list[str] = Field(..., min_length=1, max_length=5)
    contrasts: list[str] = Field(default_factory=list)
    research_gaps: list[str] = Field(..., min_length=1, max_length=3)
    suggested_synthesis: str = Field(...)
    cross_relations: list[CrossPaperRelation] = Field(default_factory=list)


def pydantic_to_claude_tool_schema(model: type[BaseModel]) -> dict:
    """Convert a Pydantic model to Claude tool use input_schema format.

    Expands all $ref/$defs so the output is a self-contained JSON Schema.
    """
    schema = model.model_json_schema(mode="serialization")
    defs = schema.pop("$defs", {})

    # Remove top-level 'title' that Pydantic adds (cosmetic, but Claude ignores it)
    schema.pop("title", None)

    def resolve(obj: object) -> object:
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref_key = obj["$ref"].rsplit("/", 1)[-1]
                if ref_key in defs:
                    resolved = resolve(copy.deepcopy(defs[ref_key]))
                    # Merge any sibling keys (e.g. description alongside $ref)
                    extras = {k: v for k, v in obj.items() if k != "$ref"}
                    if extras and isinstance(resolved, dict):
                        resolved = {**resolved, **extras}
                    return resolved
            return {k: resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [resolve(item) for item in obj]
        return obj

    return resolve(schema)
