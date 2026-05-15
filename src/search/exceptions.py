class SearchError(Exception):
    """Base exception for search errors."""


class RateLimitError(SearchError):
    """Raised when API rate limit is exceeded (HTTP 429)."""


class APIError(SearchError):
    """Raised when the API returns an error response."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class ParseError(SearchError):
    """Raised when API response cannot be parsed."""
