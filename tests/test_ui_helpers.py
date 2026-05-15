"""Tests for pure-logic helper functions in src/ui/components.py."""
import pytest

from src.ui.components import estimate_analysis_cost, fmt_authors


class TestEstimateAnalysisCost:
    def test_single_paper(self):
        cost = estimate_analysis_cost(1)
        assert cost == pytest.approx(0.018 + 0.06, rel=1e-4)

    def test_two_papers(self):
        cost = estimate_analysis_cost(2)
        assert cost == pytest.approx(2 * 0.018 + 0.06, rel=1e-4)

    def test_five_papers(self):
        cost = estimate_analysis_cost(5)
        assert cost == pytest.approx(5 * 0.018 + 0.06, rel=1e-4)

    def test_zero_papers(self):
        cost = estimate_analysis_cost(0)
        assert cost == pytest.approx(0.06, rel=1e-4)

    def test_returns_float(self):
        assert isinstance(estimate_analysis_cost(3), float)

    def test_cost_increases_with_n(self):
        assert estimate_analysis_cost(3) < estimate_analysis_cost(4)


class TestFmtAuthors:
    def test_empty(self):
        assert fmt_authors([]) == "Unknown"

    def test_single_dict(self):
        result = fmt_authors([{"name": "Alice"}])
        assert result == "Alice"

    def test_two_dicts(self):
        result = fmt_authors([{"name": "Alice"}, {"name": "Bob"}])
        assert "Alice" in result
        assert "Bob" in result

    def test_truncates_at_max(self):
        authors = [{"name": f"Author{i}"} for i in range(5)]
        result = fmt_authors(authors, max_shown=3)
        assert "et al." in result
        assert "Author0" in result
        assert "Author3" not in result

    def test_no_truncation_when_within_limit(self):
        authors = [{"name": "A"}, {"name": "B"}]
        result = fmt_authors(authors, max_shown=3)
        assert "et al." not in result

    def test_handles_missing_name(self):
        result = fmt_authors([{"name": ""}, {"name": "Bob"}])
        assert "Bob" in result

    def test_handles_object_with_name_attr(self):
        class FakeAuthor:
            name = "Charlie"
        result = fmt_authors([FakeAuthor()])
        assert result == "Charlie"
