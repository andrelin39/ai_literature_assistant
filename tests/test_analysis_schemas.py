"""Tests for analysis schemas and pydantic_to_claude_tool_schema."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.analysis.schemas import (
    Citation,
    CitationContext,
    ComparisonAnalysis,
    CrossPaperRelation,
    GroundedField,
    InferredField,
    KeyFinding,
    PaperAnalysis,
    StudyDesign,
    pydantic_to_claude_tool_schema,
)


# ── Citation ──────────────────────────────────────────────────────────────────


def test_citation_text_min_length():
    with pytest.raises(ValidationError):
        Citation(text="short")  # < 10 chars


def test_citation_text_max_length():
    with pytest.raises(ValidationError):
        Citation(text="x" * 301)  # > 300 chars


def test_citation_text_valid():
    c = Citation(text="This is a valid abstract sentence spanning ten chars.")
    assert len(c.text) >= 10


def test_citation_strips_whitespace():
    c = Citation(text="  This is valid text.  ")
    assert c.text == "This is valid text."


# ── GroundedField ─────────────────────────────────────────────────────────────


def test_grounded_field_null_value_not_found():
    gf: GroundedField[str] = GroundedField(value=None, confidence="not_found")
    assert gf.value is None
    assert gf.confidence == "not_found"


def test_grounded_field_with_value_and_evidence():
    gf: GroundedField[str] = GroundedField(
        value="Cross-sectional study",
        evidence=Citation(text="This cross-sectional study enrolled 200 nurses."),
        confidence="grounded",
    )
    assert gf.value == "Cross-sectional study"
    assert gf.evidence is not None


# ── PaperAnalysis ─────────────────────────────────────────────────────────────


def _make_valid_paper_analysis_dict() -> dict:
    return {
        "research_question": {
            "value": "Does burnout increase among ICU nurses during COVID-19?",
            "evidence": {"text": "This study investigated burnout among ICU nurses during the COVID-19 pandemic."},
            "confidence": "grounded",
        },
        "study_design": {
            "value": {"type": "cross-sectional", "sample_size": 300, "population": "ICU nurses"},
            "evidence": {"text": "A cross-sectional survey was administered to 300 ICU nurses."},
            "confidence": "grounded",
        },
        "key_findings": [
            {
                "statement": "Burnout scores increased significantly during the pandemic.",
                "evidence": {"text": "Burnout scores increased significantly during the COVID-19 pandemic period."},
            }
        ],
        "why_relevant": {
            "value": "Provides direct evidence of COVID-19 impact on nurse burnout.",
            "reasoning": "The study directly measures burnout in ICU nurses during COVID-19, matching the research topic.",
            "confidence": "high",
        },
        "citation_contexts": [
            {
                "context_type": "background",
                "description": "Provides epidemiological baseline for burnout prevalence.",
                "example_sentence": "研究顯示 COVID-19 期間加護病房護理師的職業倦怠顯著增加（Author et al., 2023）。",
            }
        ],
        "abstract_quality": "complete",
        "limitations_or_gaps": None,
        "cannot_analyze_reason": None,
    }


def test_paper_analysis_valid():
    analysis = PaperAnalysis.model_validate(_make_valid_paper_analysis_dict())
    assert analysis.abstract_quality == "complete"
    assert len(analysis.key_findings) == 1


def test_paper_analysis_key_findings_minimum():
    data = _make_valid_paper_analysis_dict()
    data["key_findings"] = []
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate(data)


def test_paper_analysis_key_findings_maximum():
    finding = {
        "statement": "Finding X",
        "evidence": {"text": "Abstract states finding X clearly here."},
    }
    data = _make_valid_paper_analysis_dict()
    data["key_findings"] = [finding] * 6
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate(data)


def test_paper_analysis_citation_contexts_minimum():
    data = _make_valid_paper_analysis_dict()
    data["citation_contexts"] = []
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate(data)


def test_paper_analysis_citation_contexts_maximum():
    ctx = {
        "context_type": "background",
        "description": "desc",
        "example_sentence": "example",
    }
    data = _make_valid_paper_analysis_dict()
    data["citation_contexts"] = [ctx] * 5
    with pytest.raises(ValidationError):
        PaperAnalysis.model_validate(data)


# ── ComparisonAnalysis ────────────────────────────────────────────────────────


def test_comparison_analysis_valid():
    comp = ComparisonAnalysis(
        common_themes=["burnout", "COVID-19"],
        contrasts=["different sample sizes"],
        research_gaps=["long-term follow-up needed"],
        suggested_synthesis="Combine studies to show temporal trend.",
        cross_relations=[
            CrossPaperRelation(
                relation_type="similar_topic",
                target_paper_index=1,
                description="Both study ICU nurse burnout.",
            )
        ],
    )
    assert len(comp.common_themes) == 2


def test_comparison_analysis_common_themes_minimum():
    with pytest.raises(ValidationError):
        ComparisonAnalysis(
            common_themes=[],
            research_gaps=["gap"],
            suggested_synthesis="synthesis",
        )


def test_comparison_analysis_research_gaps_maximum():
    with pytest.raises(ValidationError):
        ComparisonAnalysis(
            common_themes=["theme"],
            research_gaps=["g1", "g2", "g3", "g4"],
            suggested_synthesis="synthesis",
        )


# ── pydantic_to_claude_tool_schema ────────────────────────────────────────────


def test_schema_no_defs():
    schema = pydantic_to_claude_tool_schema(PaperAnalysis)
    schema_str = json.dumps(schema)
    assert "$defs" not in schema
    assert "$ref" not in schema_str


def test_schema_is_object():
    schema = pydantic_to_claude_tool_schema(PaperAnalysis)
    assert schema.get("type") == "object"
    assert "properties" in schema


def test_schema_has_required_fields():
    schema = pydantic_to_claude_tool_schema(PaperAnalysis)
    props = schema["properties"]
    assert "research_question" in props
    assert "study_design" in props
    assert "key_findings" in props
    assert "why_relevant" in props
    assert "citation_contexts" in props
    assert "abstract_quality" in props


def test_comparison_schema_no_defs():
    schema = pydantic_to_claude_tool_schema(ComparisonAnalysis)
    assert "$defs" not in schema
    assert "$ref" not in json.dumps(schema)
