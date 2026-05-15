"""Tests for PaperExtractor — all Claude API calls mocked."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-testing")
os.environ.setdefault("CONTACT_EMAIL", "test@example.com")

from src.analysis.claude_client import ClaudeAnalysisClient
from src.analysis.exceptions import ClaudeAPIError, EmptyAbstractError, SchemaValidationError
from src.analysis.extractor import PaperExtractor
from src.analysis.schemas import PaperAnalysis
from src.storage.schemas import Author, PaperCreate


# ── Helpers ───────────────────────────────────────────────────────────────────


_DEFAULT_ABSTRACT = (
    "This cross-sectional study examined burnout among 300 ICU nurses during COVID-19. "
    "Results showed 67% experienced high burnout. Night shift was a risk factor "
    "(OR=1.89). Systemic interventions are recommended."
)
_UNSET = object()


def _paper(abstract: object = _UNSET) -> PaperCreate:
    resolved = _DEFAULT_ABSTRACT if abstract is _UNSET else abstract
    return PaperCreate(
        title="Nursing Burnout During COVID-19",
        authors=[Author(name="Smith J")],
        year=2023,
        abstract=resolved,  # type: ignore[arg-type]
        source_api="semantic_scholar",
    )


def _valid_tool_input() -> dict:
    return {
        "research_question": {
            "value": "Burnout prevalence in ICU nurses during COVID-19",
            "evidence": {"text": "This cross-sectional study examined burnout among 300 ICU nurses during COVID-19."},
            "confidence": "grounded",
        },
        "study_design": {
            "value": {"type": "cross-sectional", "sample_size": 300, "population": "ICU nurses"},
            "evidence": {"text": "This cross-sectional study examined burnout among 300 ICU nurses during COVID-19."},
            "confidence": "grounded",
        },
        "key_findings": [
            {
                "statement": "67% of ICU nurses experienced high burnout.",
                "evidence": {"text": "Results showed 67% experienced high burnout."},
            }
        ],
        "why_relevant": {
            "value": "Directly measures burnout in target population.",
            "reasoning": "The study population and outcome match the research topic.",
            "confidence": "high",
        },
        "citation_contexts": [
            {
                "context_type": "background",
                "description": "Provides prevalence data for burnout.",
                "example_sentence": "COVID-19 期間 ICU 護理師的職業倦怠盛行率高達 67%（Smith, 2023）。",
            }
        ],
        "abstract_quality": "complete",
        "limitations_or_gaps": None,
        "cannot_analyze_reason": None,
    }


def _make_client(model: str = "claude-sonnet-4-6") -> ClaudeAnalysisClient:
    client = ClaudeAnalysisClient(model=model)
    return client


# ── Normal path ───────────────────────────────────────────────────────────────


def test_normal_abstract_returns_paper_analysis(monkeypatch):
    client = _make_client()
    usage = {"input_tokens": 1000, "output_tokens": 500, "estimated_cost_usd": 0.0105}

    monkeypatch.setattr(client, "call_with_tool", lambda **kw: (_valid_tool_input(), usage))

    extractor = PaperExtractor(client=client)
    result, returned_usage = extractor.analyze(_paper(), "護理職業倦怠")

    assert isinstance(result, PaperAnalysis)
    assert result.abstract_quality == "complete"
    assert returned_usage["input_tokens"] == 1000


# ── EmptyAbstractError ────────────────────────────────────────────────────────


def test_abstract_none_raises_empty_abstract_error():
    extractor = PaperExtractor(client=_make_client())
    paper = _paper(abstract=None)
    with pytest.raises(EmptyAbstractError):
        extractor.analyze(paper, "topic")


def test_abstract_too_short_raises_empty_abstract_error():
    extractor = PaperExtractor(client=_make_client())
    paper = _paper(abstract="Too short.")  # < 50 chars
    with pytest.raises(EmptyAbstractError):
        extractor.analyze(paper, "topic")


def test_abstract_exactly_50_chars_is_accepted(monkeypatch):
    client = _make_client()
    usage = {"input_tokens": 100, "output_tokens": 50, "estimated_cost_usd": 0.001}
    monkeypatch.setattr(client, "call_with_tool", lambda **kw: (_valid_tool_input(), usage))

    extractor = PaperExtractor(client=client)
    paper = _paper(abstract="x" * 50)
    result, _ = extractor.analyze(paper, "topic")
    assert isinstance(result, PaperAnalysis)


# ── Schema validation failure → retry → SchemaValidationError ─────────────────


def test_schema_validation_failure_retries_and_raises(monkeypatch):
    client = ClaudeAnalysisClient(model="claude-sonnet-4-6", max_retries=2)
    call_count = 0

    def mock_call(**kw):
        nonlocal call_count
        call_count += 1
        # Return dict missing required fields → model_validate will fail
        return {"bad_field": "bad_value"}, {"input_tokens": 10, "output_tokens": 10, "estimated_cost_usd": 0.0}

    monkeypatch.setattr(client, "call_with_tool", mock_call)

    extractor = PaperExtractor(client=client)
    with pytest.raises(SchemaValidationError):
        extractor.analyze(_paper(), "topic")

    assert call_count == 3  # 1 initial + 2 retries


# ── No tool called → retry ────────────────────────────────────────────────────


def test_no_tool_called_retries_then_succeeds(monkeypatch):
    client = ClaudeAnalysisClient(model="claude-sonnet-4-6", max_retries=2)
    usage = {"input_tokens": 200, "output_tokens": 100, "estimated_cost_usd": 0.002}
    call_count = 0

    def mock_call(**kw):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise SchemaValidationError("No tool_use block in response")
        return _valid_tool_input(), usage

    monkeypatch.setattr(client, "call_with_tool", mock_call)

    extractor = PaperExtractor(client=client)
    result, _ = extractor.analyze(_paper(), "topic")

    assert isinstance(result, PaperAnalysis)
    assert call_count == 2


# ── ClaudeAPIError is not retried ─────────────────────────────────────────────


def test_claude_api_error_propagates_immediately(monkeypatch):
    client = ClaudeAnalysisClient(model="claude-sonnet-4-6", max_retries=2)
    call_count = 0

    def mock_call(**kw):
        nonlocal call_count
        call_count += 1
        raise ClaudeAPIError("Authentication failed")

    monkeypatch.setattr(client, "call_with_tool", mock_call)

    extractor = PaperExtractor(client=client)
    with pytest.raises(ClaudeAPIError):
        extractor.analyze(_paper(), "topic")

    assert call_count == 1  # no retry for API errors


# ── Token usage ───────────────────────────────────────────────────────────────


def test_token_usage_returned_correctly(monkeypatch):
    client = _make_client()
    expected_usage = {
        "input_tokens": 1000,
        "output_tokens": 500,
        "estimated_cost_usd": 0.0105,
    }

    monkeypatch.setattr(
        client, "call_with_tool", lambda **kw: (_valid_tool_input(), expected_usage)
    )

    extractor = PaperExtractor(client=client)
    _, usage = extractor.analyze(_paper(), "topic")

    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["estimated_cost_usd"] == pytest.approx(0.0105, rel=1e-4)


# ── Cost calculation ──────────────────────────────────────────────────────────


def test_cost_calculation_sonnet_4_6():
    """input 1000 tokens, output 500 tokens, sonnet 4.6 → $0.003 + $0.0075 = $0.0105"""
    with patch("src.analysis.claude_client.anthropic.Anthropic") as MockAnthropic:
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.name = "record_paper_analysis"
        mock_block.input = _valid_tool_input()

        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "tool_use"
        mock_response.usage.input_tokens = 1000
        mock_response.usage.output_tokens = 500

        MockAnthropic.return_value.messages.create.return_value = mock_response

        client = ClaudeAnalysisClient(model="claude-sonnet-4-6")
        _, usage = client.call_with_tool(
            system_prompt="sys",
            user_prompt="user",
            tool_name="record_paper_analysis",
            tool_description="desc",
            tool_input_schema={},
        )

    assert usage["input_tokens"] == 1000
    assert usage["output_tokens"] == 500
    assert usage["estimated_cost_usd"] == pytest.approx(0.0105, rel=1e-4)
