"""Denylist for source-tags / non-actors that must never be episode or connection spines.

arXiv is a preprint venue (source metadata), not an entity worth following.
Ported from HomeLab AutoGen craft for NI v12.
"""

from __future__ import annotations

import re
from typing import Any

_EXACT_BLOCKED = frozenset(
    {
        "arxiv",
        "arxiv.org",
        "www.arxiv.org",
    }
)

_PATTERN_BLOCKED = (
    re.compile(r"^arxiv(\.org)?$", re.I),
    re.compile(r"^arxiv\b", re.I),
    re.compile(r"\barxiv\.org\b", re.I),
)


def normalize_entity_name(name: str | None) -> str:
    return (name or "").strip().lower()


def is_blocked_hub_name(name: str | None) -> bool:
    """True if this entity name is a banned source-tag (never track as a connection)."""
    raw = (name or "").strip()
    if not raw:
        return False
    lowered = raw.lower()
    if lowered in _EXACT_BLOCKED:
        return True
    for pat in _PATTERN_BLOCKED:
        if pat.search(raw):
            return True
    return False


def filter_blocked_entity_rows(
    rows: list[Any] | None, *, name_key: str = "entity_name"
) -> list[dict[str, Any]]:
    """Drop denylisted entity rows; keep only dicts with a usable name."""
    out: list[dict[str, Any]] = []
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        if is_blocked_hub_name(str(r.get(name_key) or "")):
            continue
        out.append(r)
    return out


def sql_entity_name_not_blocked(column: str = "ae.entity_name") -> str:
    """SQL fragment: column is not an arXiv-family source tag."""
    return (
        f"(lower(btrim({column})) NOT IN ('arxiv', 'arxiv.org', 'www.arxiv.org') "
        f"AND lower(btrim({column})) NOT LIKE 'arxiv %' "
        f"AND lower(btrim({column})) NOT LIKE 'arxiv.%')"
    )
