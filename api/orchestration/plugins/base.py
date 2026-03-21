"""
DataSource plugin interface for Newsroom Orchestrator v6.

Implementations: RSSDataSource, WebScraperSource, APIDataSource, FileWatcherSource, EmailDigestSource.
"""

from abc import ABC, abstractmethod
from typing import Any

# Placeholder for standard article format
ArticlePayload = dict[str, Any]


class DataSource(ABC):
    """Abstract interface for data sources (sync in Phase 1)."""

    @abstractmethod
    def authenticate(self) -> bool:
        """Verify credentials / connectivity. Returns True if ready."""
        pass

    @abstractmethod
    def fetch_latest(self) -> list[ArticlePayload]:
        """Fetch latest items (articles, etc.). Returns list of standardized payloads."""
        pass

    @abstractmethod
    def validate_data(self, item: ArticlePayload) -> bool:
        """Validate a single item. Returns True if valid."""
        pass

    @abstractmethod
    def transform_to_standard(self, raw: Any) -> ArticlePayload:
        """Transform raw item to standard article format."""
        pass

    def get_rate_limits(self) -> dict[str, Any] | None:
        """Return rate limit info (calls/min, remaining, etc.). Optional."""
        return None
