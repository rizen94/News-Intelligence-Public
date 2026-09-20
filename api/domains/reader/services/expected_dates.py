"""
Expected / announced date extraction for one-off calendar surfaces.

v1: concrete calendar dates (YYYY-MM-DD, Month Day Year) and month phrases
("this July", "in March 2026") → 1st of that month. No LLM.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# ISO / numeric dates
_ISO_RE = re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b")
_US_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")
# "March 15, 2026" / "15 March 2026"
_MDY_RE = re.compile(
    r"\b("
    + "|".join(_MONTHS.keys())
    + r")\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_DMY_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+("
    + "|".join(_MONTHS.keys())
    + r")\s+,?\s*(20\d{2})\b",
    re.IGNORECASE,
)
# Month phrases → 1st of month: "this July", "in March 2026", "July 2026"
_MONTH_PHRASE_RE = re.compile(
    r"\b(?:this|next|in|during|for)?\s*("
    + "|".join(_MONTHS.keys())
    + r")(?:\s+(20\d{2}))?\b",
    re.IGNORECASE,
)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def _infer_year(month: int, explicit_year: int | None, reference: date) -> int:
    if explicit_year:
        return explicit_year
    # Prefer current/reference year; if month already passed by >1 month, roll forward
    y = reference.year
    if month < reference.month - 1:
        y += 1
    return y


def extract_expected_dates(
    text: str | None,
    *,
    reference: date | None = None,
) -> dict[str, Any]:
    """
    Return announced_on / expected_on when resolvable to a concrete day.

    announced_on: first concrete date found (often publish/announce phrasing).
    expected_on: later concrete date, or month-phrase → 1st of month.
    """
    ref = reference or date.today()
    raw = (text or "").strip()
    if not raw:
        return {"announced_on": None, "expected_on": None, "date_precision": None}

    concrete: list[date] = []

    for m in _ISO_RE.finditer(raw):
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            concrete.append(d)

    for m in _US_RE.finditer(raw):
        d = _safe_date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        if d:
            concrete.append(d)

    for m in _MDY_RE.finditer(raw):
        month = _MONTHS[m.group(1).lower()]
        d = _safe_date(int(m.group(3)), month, int(m.group(2)))
        if d:
            concrete.append(d)

    for m in _DMY_RE.finditer(raw):
        month = _MONTHS[m.group(2).lower()]
        d = _safe_date(int(m.group(3)), month, int(m.group(1)))
        if d:
            concrete.append(d)

    month_first: list[date] = []
    for m in _MONTH_PHRASE_RE.finditer(raw):
        # Skip if this match is part of a full day already captured (e.g. "March 15, 2026")
        span = raw[m.start() : m.end()]
        if re.search(r"\d{1,2}", span) and _MDY_RE.search(span):
            continue
        month = _MONTHS[m.group(1).lower()]
        year = _infer_year(month, int(m.group(2)) if m.group(2) else None, ref)
        d = _safe_date(year, month, 1)
        if d and d not in concrete:
            month_first.append(d)

    concrete = sorted(set(concrete))
    month_first = sorted(set(month_first))

    announced_on: date | None = concrete[0] if concrete else None
    expected_on: date | None = None
    precision: str | None = None

    if len(concrete) >= 2:
        expected_on = concrete[-1]
        precision = "day"
    elif len(concrete) == 1 and month_first:
        expected_on = month_first[-1]
        precision = "month"
    elif len(concrete) == 1:
        # Single concrete date — treat as expected when phrasing suggests future
        lower = raw.lower()
        if any(k in lower for k in ("expected", "scheduled", "will", "due", "launch", "release")):
            expected_on = concrete[0]
            announced_on = None
            precision = "day"
        else:
            announced_on = concrete[0]
            precision = "day"
    elif month_first:
        expected_on = month_first[-1]
        precision = "month"

    return {
        "announced_on": announced_on.isoformat() if announced_on else None,
        "expected_on": expected_on.isoformat() if expected_on else None,
        "date_precision": precision,
    }


def parse_iso_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None
