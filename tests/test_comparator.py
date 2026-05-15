"""Tests for PaperComparator — all Claude API calls mocked."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")
os.environ.setdefault("CONTACT_EMAIL", "test@example.com")

from src.analysis.claude_client import ClaudeAnalysisClient
from src.analysis.comparator import PaperComparator
from src.analysis.exceptions import SchemaValidationError
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
)
from src.storage.schemas import Author, PaperCreate


# ── Helpers ───────────────────────────────────────────────────────────────────


def _paper(title: str = "Paper A", abstract: str = "Abstract " * 10) -> PaperCreate:
    return PaperCreate(
        title=title,
        authors=[Author(name="Test Author")],
        year=2023,
        abstract=abstract,
        source_api="semantic_scholar",
    )


def _analysis(title: str = "Paper A") -> PaperAnalysis:
    return PaperAnalysis(
        research_question=GroundedField(
            value="Is nurse burnout increasing?",
            evidence=Citation(text="This study examined nurse burnout during COVID-19."),
            confidence="grounded",
        ),
        study_design=GroundedField(
            value=StudyDesign(type="cross-sectional", sample_size=200, population="nurses"),
            evidence=Citation(text="A cross-sectional survey was conducted."),
            confidence="grounded",
        ),
        key_findings=[
            KeyFinding(
                statement="Burnout increased significantly.",
                evidence=Citation(text="Burnout scores increased significantly during the pandemic."),
            )
        ],
        why_relevant=InferredField(
            value="Directly relevant to burnout topic.",
            reasoning="Matches the target population and outcome.",
            confidence="high",
        ),
        citation_contexts=[
            CitationContext(
                context_type="background",
                description="Background on burnout prevalence.",
                example_sentence="護理師職業倦怠盛行率持續上升（Author, 2023）。",
            )
        ],
        abstract_quality="complete",
    )


def _valid_comparison_dict(n_papers: int = 2) -> dict:
    return {
        "common_themes": ["nurse burnout", "COVID-19 impact"],
        "contrasts": ["different sample sizes"],
        "research_gaps": ["longitudinal studies needed"],
        "suggested_synthesis": "Combine findings to demonstrate temporal trend in burnout.",
        "cross_relations": [
            {
                "relation_type": "similar_topic",
                "target_paper_index": 1,
                "description": "Both papers study ICU nurse burnout.",
            }
        ],
    }


def _make_client() -> ClaudeAnalysisClient:
    return ClaudeAnalysisClient(model="claude-sonnet-4-6")


# ── ValueError on too few papers ──────────────────────────────────────────────


def test_fewer_than_2_papers_raises_value_error():
    comparator = PaperComparator(client=_make_client())
    with pytest.raises(ValueError, match="at least 2"):
        comparator.compare([_paper()], [_analysis()], "topic")


def test_empty_papers_raises_value_error():
    comparator = PaperComparator(client=_make_client())
    with pytest.raises(ValueError):
        comparator.compare([], [], "topic")


# ── Normal multi-paper comparison ─────────────────────────────────────────────


def test_normal_comparison_returns_analysis(monkeypatch):
    client = _make_client()
    usage = {"input_tokens": 2000, "output_tokens": 800, "estimated_cost_usd": 0.018}
    monkeypatch.setattr(
        client, "call_with_tool", lambda **kw: (_valid_comparison_dict(2), usage)
    )

    comparator = PaperComparator(client=client)
    papers = [_paper("A"), _paper("B")]
    analyses = [_analysis("A"), _analysis("B")]

    result, returned_usage = comparator.compare(papers, analyses, "護理職業倦怠")

    assert isinstance(result, ComparisonAnalysis)
    assert len(result.common_themes) == 2
    assert len(result.research_gaps) == 1
    assert returned_usage["input_tokens"] == 2000


def test_three_papers_comparison(monkeypatch):
    client = _make_client()
    comparison_dict = _valid_comparison_dict(3)
    comparison_dict["cross_relations"] = [
        {"relation_type": "similar_topic", "target_paper_index": 1, "description": "Related."},
        {"relation_type": "extends", "target_paper_index": 2, "description": "Extends."},
    ]
    usage = {"input_tokens": 3000, "output_tokens": 1000, "estimated_cost_usd": 0.024}

    monkeypatch.setattr(
        client, "call_with_tool", lambda **kw: (comparison_dict, usage)
    )

    comparator = PaperComparator(client=client)
    papers = [_paper(f"P{i}") for i in range(3)]
    analyses = [_analysis(f"P{i}") for i in range(3)]

    result, _ = comparator.compare(papers, analyses, "topic")
    assert isinstance(result, ComparisonAnalysis)
    assert len(result.cross_relations) == 2


# ── cross_relations index validation ─────────────────────────────────────────


def test_cross_relations_out_of_bounds_index_filtered(monkeypatch):
    client = _make_client()
    comparison_dict = _valid_comparison_dict(2)
    comparison_dict["cross_relations"] = [
        {"relation_type": "similar_topic", "target_paper_index": 0, "description": "valid"},
        {"relation_type": "extends", "target_paper_index": 99, "description": "invalid index"},
    ]
    usage = {"input_tokens": 100, "output_tokens": 50, "estimated_cost_usd": 0.001}

    monkeypatch.setattr(
        client, "call_with_tool", lambda **kw: (comparison_dict, usage)
    )

    comparator = PaperComparator(client=client)
    result, _ = comparator.compare([_paper("A"), _paper("B")], [_analysis(), _analysis()], "topic")

    # index 99 should be filtered out, index 0 should remain
    assert all(r.target_paper_index < 2 for r in result.cross_relations)
    assert len(result.cross_relations) == 1


# ── Schema validation failure ─────────────────────────────────────────────────


def test_bad_schema_raises_after_retries(monkeypatch):
    client = ClaudeAnalysisClient(model="claude-sonnet-4-6", max_retries=1)
    call_count = 0

    def mock_call(**kw):
        nonlocal call_count
        call_count += 1
        return {"bad_field": "value"}, {"input_tokens": 10, "output_tokens": 10, "estimated_cost_usd": 0.0}

    monkeypatch.setattr(client, "call_with_tool", mock_call)

    comparator = PaperComparator(client=client)
    with pytest.raises(SchemaValidationError):
        comparator.compare([_paper("A"), _paper("B")], [_analysis(), _analysis()], "topic")

    assert call_count == 2  # 1 initial + 1 retry
