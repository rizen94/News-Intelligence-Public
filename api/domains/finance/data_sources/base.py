"""
Base class for finance data sources.
Subclasses implement fetch_observations() returning DataResult[list[dict]].
"""

import logging
from abc import ABC, abstractmethod

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


class DataSourceBase(ABC):
    """Abstract base for FRED, EDGAR, etc."""

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("name", self.__class__.__name__)
        self.rate_limit = config.get("rate_limit", {})

    @abstractmethod
    def fetch_observations(self, series_id: str, **kwargs):
        """
        Fetch time series observations.
        Returns DataResult[list[dict]] with {"date": str, "value": float, "metadata": dict}
        """
        pass

    def fetch_series_info(self, series_id: str) -> dict | None:
        """Optional: metadata for a series."""
        return None
