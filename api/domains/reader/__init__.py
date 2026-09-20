"""Reader APIs for the v2 broadsheet User UI (additive, non-breaking)."""

from __future__ import annotations

from typing import Any

__all__ = ["reader_router"]


def __getattr__(name: str) -> Any:
    if name == "reader_router":
        from .routes import reader_router

        return reader_router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
