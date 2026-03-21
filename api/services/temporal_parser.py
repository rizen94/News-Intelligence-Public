"""
Temporal Parser for News Intelligence v5.0
Resolves relative date expressions against article publication dates.
Handles phrases like "yesterday", "last Tuesday", "three months ago",
"early 2024", and "following last month's ruling".
"""

import logging
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "a": 1,
    "an": 1,
    "several": 3,
    "few": 3,
}


def _parse_number(text: str) -> int | None:
    """Parse a number from text, supporting both digits and words."""
    text = text.strip().lower()
    if text.isdigit():
        return int(text)
    return WORD_NUMBERS.get(text)


def _most_recent_weekday(anchor: date, weekday: int) -> date:
    """Return the most recent occurrence of *weekday* before *anchor*."""
    days_back = (anchor.weekday() - weekday) % 7
    if days_back == 0:
        days_back = 7
    return anchor - timedelta(days=days_back)


def resolve_date(expression: str, anchor: datetime) -> tuple[date | None, str]:
    """
    Resolve a date expression relative to an anchor (article publication date).

    Returns (resolved_date, date_precision).
    Precision is one of: exact, week, month, quarter, year, unknown.
    """
    if not expression:
        return None, "unknown"

    expr = expression.strip().lower()
    anchor_date = anchor.date() if isinstance(anchor, datetime) else anchor

    # --- absolute ISO-style dates ---
    iso = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", expr)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))), "exact"
        except ValueError:
            pass

    # "January 5, 2024" / "5 January 2024" / "Jan 2024"
    m = re.match(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")[,.]?\s+(\d{4})", expr)
    if m:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))), "exact"
        except ValueError:
            pass

    m = re.match(r"(" + "|".join(MONTHS) + r")\s+(\d{1,2})[,.]?\s+(\d{4})", expr)
    if m:
        try:
            return date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))), "exact"
        except ValueError:
            pass

    m = re.match(r"(" + "|".join(MONTHS) + r")\s+(\d{4})", expr)
    if m:
        try:
            return date(int(m.group(2)), MONTHS[m.group(1)], 1), "month"
        except ValueError:
            pass

    # --- simple relative tokens ---
    if expr in ("today", "this morning", "this afternoon", "this evening", "tonight"):
        return anchor_date, "exact"

    if expr == "yesterday":
        return anchor_date - timedelta(days=1), "exact"

    if expr in ("the day before yesterday", "two days ago"):
        return anchor_date - timedelta(days=2), "exact"

    if expr == "tomorrow":
        return anchor_date + timedelta(days=1), "exact"

    # "last week" / "this week"
    if expr == "last week":
        return anchor_date - timedelta(weeks=1), "week"
    if expr == "this week":
        return anchor_date, "week"

    # "last month" / "this month"
    if expr == "last month":
        first = anchor_date.replace(day=1)
        prev = first - timedelta(days=1)
        return prev.replace(day=1), "month"
    if expr == "this month":
        return anchor_date.replace(day=1), "month"

    # "last year" / "this year"
    if expr == "last year":
        return date(anchor_date.year - 1, 1, 1), "year"
    if expr == "this year":
        return date(anchor_date.year, 1, 1), "year"

    # "last <weekday>" / "on <weekday>"
    for day_name, day_num in WEEKDAYS.items():
        if re.match(rf"(last|on|this past)\s+{day_name}", expr):
            return _most_recent_weekday(anchor_date, day_num), "exact"

    # "N days/weeks/months/years ago"
    m = re.match(r"(\w+)\s+(days?|weeks?|months?|years?)\s+ago", expr)
    if m:
        n = _parse_number(m.group(1))
        unit = m.group(2).rstrip("s")
        if n is not None:
            if unit == "day":
                return anchor_date - timedelta(days=n), "exact"
            if unit == "week":
                return anchor_date - timedelta(weeks=n), "week"
            if unit == "month":
                month = anchor_date.month - n
                year = anchor_date.year
                while month < 1:
                    month += 12
                    year -= 1
                return date(year, month, 1), "month"
            if unit == "year":
                return date(anchor_date.year - n, 1, 1), "year"

    # "earlier this month" / "earlier this year"
    if "earlier this month" in expr:
        return anchor_date.replace(day=1), "month"
    if "earlier this year" in expr:
        return date(anchor_date.year, 1, 1), "year"

    # "early/mid/late <year>"
    m = re.match(r"(early|mid|late)\s+(\d{4})", expr)
    if m:
        year = int(m.group(2))
        period = m.group(1)
        if period == "early":
            return date(year, 1, 1), "quarter"
        if period == "mid":
            return date(year, 6, 1), "quarter"
        return date(year, 10, 1), "quarter"

    # "Q1/Q2/Q3/Q4 <year>"
    m = re.match(r"q([1-4])\s+(\d{4})", expr)
    if m:
        q = int(m.group(1))
        year = int(m.group(2))
        return date(year, (q - 1) * 3 + 1, 1), "quarter"

    # bare year "2024" / "in 2024"
    m = re.match(r"(?:in\s+)?(\d{4})$", expr)
    if m:
        return date(int(m.group(1)), 1, 1), "year"

    logger.debug(f"Could not resolve temporal expression: '{expression}'")
    return None, "unknown"


def extract_temporal_expressions(text: str) -> list[str]:
    """
    Pull candidate temporal expressions out of raw text.
    Returns a list of raw expression strings for further resolution.
    """
    patterns = [
        r"\b(?:yesterday|today|tomorrow|tonight|this (?:morning|afternoon|evening))\b",
        r"\b(?:the day before yesterday)\b",
        r"\blast\s+(?:" + "|".join(WEEKDAYS) + r")\b",
        r"\b(?:last|this)\s+(?:week|month|year)\b",
        r"\b\w+\s+(?:days?|weeks?|months?|years?)\s+ago\b",
        r"\b(?:early|mid|late)\s+\d{4}\b",
        r"\b[Qq][1-4]\s+\d{4}\b",
        r"\b(?:"
        + "|".join(m.capitalize() for m in MONTHS if len(m) > 3)
        + r")\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}\s+(?:"
        + "|".join(m.capitalize() for m in MONTHS if len(m) > 3)
        + r"),?\s+\d{4}\b",
        r"\b(?:" + "|".join(m.capitalize() for m in MONTHS if len(m) > 3) + r")\s+\d{4}\b",
        r"\b\d{4}-\d{1,2}-\d{1,2}\b",
        r"\bearlier this (?:month|year)\b",
    ]

    found: list[str] = []
    for pat in patterns:
        for match in re.finditer(pat, text, re.IGNORECASE):
            found.append(match.group(0))
    return found
