"""Cross-paper relational analysis using Claude tool use."""
from __future__ import annotations

from pydantic import ValidationError

from src.analysis.claude_client import ClaudeAnalysisClient
from src.analysis.exceptions import SchemaValidationError
from src.analysis.prompts import COMPARATOR_USER_PROMPT, FULL_SYSTEM_PROMPT
from src.analysis.schemas import (
    ComparisonAnalysis,
    PaperAnalysis,
    pydantic_to_claude_tool_schema,
)
from src.storage.schemas import PaperCreate

_TOOL_NAME = "record_comparison_analysis"
_TOOL_DESCRIPTION = (
    "Record a structured cross-paper comparison analysis for literature review."
)
_TOOL_SCHEMA: dict | None = None


def _get_tool_schema() -> dict:
    global _TOOL_SCHEMA
    if _TOOL_SCHEMA is None:
        _TOOL_SCHEMA = pydantic_to_claude_tool_schema(ComparisonAnalysis)
    return _TOOL_SCHEMA


class PaperComparator:
    def __init__(self, client: ClaudeAnalysisClient | None = None) -> None:
        self.client = client or ClaudeAnalysisClient()

    def compare(
        self,
        papers: list[PaperCreate],
        individual_analyses: list[PaperAnalysis],
        user_topic: str,
    ) -> tuple[ComparisonAnalysis, dict]:
        """Cross-paper relational analysis.

        Raises:
            ValueError: fewer than 2 papers provided.
            SchemaValidationError: schema validation failed after all retries.
            ClaudeAPIError: unrecoverable API error.
        """
        if len(papers) < 2:
            raise ValueError(
                f"Comparison requires at least 2 papers, got {len(papers)}"
            )

        user_prompt = COMPARATOR_USER_PROMPT(user_topic, papers, individual_analyses)
        tool_schema = _get_tool_schema()
        n_papers = len(papers)

        last_error: Exception | None = None
        for attempt in range(self.client.max_retries + 1):
            try:
                tool_input, usage = self.client.call_with_tool(
                    system_prompt=FULL_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    tool_name=_TOOL_NAME,
                    tool_description=_TOOL_DESCRIPTION,
                    tool_input_schema=tool_schema,
                )
                comparison = ComparisonAnalysis.model_validate(tool_input)
                # Filter cross_relations with out-of-bounds indices
                comparison.cross_relations = [
                    r
                    for r in comparison.cross_relations
                    if 0 <= r.target_paper_index < n_papers
                ]
                return comparison, usage
            except SchemaValidationError as e:
                last_error = e
            except ValidationError as e:
                last_error = SchemaValidationError(
                    f"Output schema mismatch on attempt {attempt + 1}: {e}"
                )

        raise SchemaValidationError(
            f"Comparison failed after {self.client.max_retries + 1} attempt(s)"
        ) from last_error
