"""Single-paper deep analysis using Claude tool use."""
from __future__ import annotations

from pydantic import ValidationError

from src.analysis.claude_client import ClaudeAnalysisClient
from src.analysis.exceptions import EmptyAbstractError, SchemaValidationError
from src.analysis.prompts import EXTRACTOR_USER_PROMPT, FULL_SYSTEM_PROMPT
from src.analysis.schemas import PaperAnalysis, pydantic_to_claude_tool_schema
from src.storage.schemas import PaperCreate

_TOOL_NAME = "record_paper_analysis"
_TOOL_DESCRIPTION = (
    "Record a structured analysis of a biomedical paper for citation evaluation."
)
_TOOL_SCHEMA: dict | None = None


def _get_tool_schema() -> dict:
    global _TOOL_SCHEMA
    if _TOOL_SCHEMA is None:
        _TOOL_SCHEMA = pydantic_to_claude_tool_schema(PaperAnalysis)
    return _TOOL_SCHEMA


class PaperExtractor:
    def __init__(self, client: ClaudeAnalysisClient | None = None) -> None:
        self.client = client or ClaudeAnalysisClient()

    def analyze(
        self,
        paper: PaperCreate,
        user_topic: str,
    ) -> tuple[PaperAnalysis, dict]:
        """Analyze a single paper and return (analysis, usage).

        Raises:
            EmptyAbstractError: abstract is None or shorter than 50 chars.
            SchemaValidationError: schema validation failed after all retries.
            ClaudeAPIError: unrecoverable API error.
        """
        if not paper.abstract or len(paper.abstract.strip()) < 50:
            raise EmptyAbstractError(
                f"Abstract is too short to analyze (len={len(paper.abstract or '')})"
            )

        user_prompt = EXTRACTOR_USER_PROMPT(user_topic, paper)
        tool_schema = _get_tool_schema()

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
                analysis = PaperAnalysis.model_validate(tool_input)
                return analysis, usage
            except SchemaValidationError as e:
                last_error = e
            except ValidationError as e:
                last_error = SchemaValidationError(
                    f"Output schema mismatch on attempt {attempt + 1}: {e}"
                )
            # ClaudeAPIError propagates immediately (no retry)

        raise SchemaValidationError(
            f"Analysis failed after {self.client.max_retries + 1} attempt(s)"
        ) from last_error
