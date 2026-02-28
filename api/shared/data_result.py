"""
Lightweight result type to distinguish "no data" from "error".
Enables callers to branch on success and include error_type in evidence ledger.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class DataResult(Generic[T]):
    """Result from data fetch/store operations."""

    success: bool
    data: T | None = None
    error: str | None = None
    error_type: str | None = None  # "no_data", "network", "parse", "rate_limit", "auth", "storage"

    @classmethod
    def ok(cls, data: T) -> "DataResult[T]":
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str, error_type: str | None = None) -> "DataResult[T]":
        return cls(success=False, error=error, error_type=error_type or "unknown")
