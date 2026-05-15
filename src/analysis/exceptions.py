class AnalysisError(Exception):
    """Base exception for analysis module."""


class SchemaValidationError(AnalysisError):
    """Claude tool use output did not match expected schema."""


class EmptyAbstractError(AnalysisError):
    """Paper abstract is missing or too short to analyze."""


class ClaudeAPIError(AnalysisError):
    """Claude API call failed."""
