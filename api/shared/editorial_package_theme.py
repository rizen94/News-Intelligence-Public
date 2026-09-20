"""
Title-spine theme matching for editorial packages (v11).

Kitchen-sink packages accumulate SCOTUS (or other) noise because Reduction's
jaccard threshold is too loose on generic tokens (court, ruling, federal…).
Distinctive title/summary tokens (case names, parties) are the spine; members
that miss them are theme_mismatch and should be uncoupled.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"[a-z0-9]+")
_CASE_CAPTION = re.compile(
    r"\b([A-Z][A-Za-z0-9'’.\-]+(?:\s+[A-Z][A-Za-z0-9'’.\-]+){0,4})"
    r"\s+v\.?\s+"
    r"([A-Z][A-Za-z0-9'’.\-]+(?:\s+[A-Z][A-Za-z0-9'’.\-]+){0,4})\b"
)

# Too common in news packages to count alone as on-theme.
THEME_STOP: frozenset[str] = frozenset(
    {
        "supreme",
        "court",
        "courts",
        "justice",
        "justices",
        "ruling",
        "rulings",
        "case",
        "cases",
        "federal",
        "lawsuit",
        "lawsuits",
        "litigation",
        "decision",
        "order",
        "orders",
        "states",
        "united",
        "american",
        "amid",
        "high",
        "profile",
        "serial",
        "weigh",
        "from",
        "term",
        "terms",
        "continue",
        "including",
        "multiple",
        "laws",
        "challenge",
        "challenging",
        "looked",
        "different",
        "recent",
        "numbers",
        "closing",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "updated",
        "report",
        "reporting",
        "according",
        "president",
        "october",
        "november",
        "december",
        "january",
        "february",
        "march",
        "april",
        "june",
        "july",
        "august",
        "september",
        "this",
        "that",
        "with",
        "into",
        "about",
        "after",
        "before",
        "against",
        "their",
        "there",
        "which",
        "where",
        "when",
        "will",
        "would",
        "could",
        "should",
    }
)


def theme_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for t in _TOKEN.findall((text or "").lower()):
        if len(t) < 4 or t in THEME_STOP or t.isdigit():
            continue
        out.add(t)
    return out


def extract_case_party_tokens(text: str) -> set[str]:
    """Tokens from 'A v. B' captions in title/summary (strong spine cues)."""
    found: set[str] = set()
    for left, right in _CASE_CAPTION.findall(text or ""):
        found |= theme_tokens(left)
        found |= theme_tokens(right)
        # Keep short proper-name tokens (Lopez) that theme_tokens might drop if <4
        for part in (left, right):
            for t in _TOKEN.findall(part.lower()):
                if len(t) >= 3 and t not in THEME_STOP and not t.isdigit():
                    found.add(t)
    return found


def package_spine_tokens(title: str, stub: str = "") -> set[str]:
    """Distinctive theme tokens for a package; title case names win."""
    title = title or ""
    stub = stub or ""
    spine = extract_case_party_tokens(title) | theme_tokens(title)
    if spine:
        # Allow stub entities but scoring hard-gates on spine overlap.
        return spine | theme_tokens(stub) | extract_case_party_tokens(stub)
    return theme_tokens(stub) | extract_case_party_tokens(stub)


def member_theme_tokens(*parts: Any) -> set[str]:
    blob = " ".join(str(p or "") for p in parts)
    return theme_tokens(blob) | extract_case_party_tokens(blob)


def spine_overlap(member_toks: set[str], spine: set[str], title: str = "") -> int:
    title_spine = theme_tokens(title) | extract_case_party_tokens(title)
    if title_spine:
        return len(member_toks & title_spine)
    return len(member_toks & spine)


def is_theme_mismatch(
    member_text: str,
    *,
    title: str,
    stub: str = "",
    min_member_tokens: int = 2,
) -> bool:
    """
    True when the package has a distinctive title spine and the member misses it.

    Members that are too thin to score are not flagged (let other gates handle).
    """
    spine = package_spine_tokens(title, stub)
    title_spine = theme_tokens(title) | extract_case_party_tokens(title)
    gate = title_spine or spine
    if len(gate) < 1:
        return False
    member_toks = member_theme_tokens(member_text)
    if len(member_toks) < min_member_tokens:
        return False
    # Require at least one title-spine hit when title has distinctive tokens.
    if title_spine:
        return len(member_toks & title_spine) == 0
    return len(member_toks & spine) == 0


def parse_case_caption_parties(text: str) -> list[str]:
    """Return ['Petitioner', 'Respondent'] style names from first A v. B caption."""
    m = _CASE_CAPTION.search(text or "")
    if not m:
        return []
    left = re.sub(r"\s+", " ", m.group(1)).strip()
    right = re.sub(r"\s+", " ", m.group(2)).strip()
    out = []
    if left:
        out.append(f"{left} (petitioner/appellant)")
    if right:
        out.append(f"{right} (respondent/appellee)")
    return out
