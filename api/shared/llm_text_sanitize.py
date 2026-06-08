"""
Strip common LLM output noise (JSON fences, echoed keys) from strings shown as headlines or ledes.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal, Optional

FieldKind = Literal["lede", "title", "summary", "narrative", "analysis", "description"]

_FIELD_MAX_LENGTH: dict[str, int] = {
    "lede": 500,
    "title": 220,
    "summary": 600,
    "narrative": 4000,
    "analysis": 2000,
    "description": 500,
}


def strip_json_fence(text: str) -> str:
    """Remove markdown code fences from LLM output."""
    s = text.strip()
    if s.startswith("```"):
        parts = s.split("\n", 1)
        if len(parts) > 1:
            s = parts[1]
        if "```" in s:
            s = s.rsplit("```", 1)[0].strip()
    return s


def parse_llm_json_response(text: Optional[str]) -> tuple[dict[str, Any] | None, str]:
    """
    Parse LLM JSON object after fence strip.
    Returns (parsed dict or None, cleaned raw text).
    """
    if not text:
        return None, ""
    cleaned = strip_json_fence(str(text).strip())
    if not cleaned:
        return None, ""
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed, cleaned
    except json.JSONDecodeError:
        pass
    return None, cleaned


def sanitize_on_persist(
    text: Optional[str],
    field_kind: FieldKind = "lede",
    *,
    max_length: int | None = None,
) -> str:
    """Write-time cleanup for LLM strings before DB persist."""
    cap = max_length if max_length is not None else _FIELD_MAX_LENGTH.get(field_kind, 500)
    if field_kind in ("title",):
        return sanitize_briefing_title(text, max_length=cap)
    if field_kind in ("lede", "summary", "description"):
        return sanitize_briefing_lede(text, max_length=cap)
    return strip_llm_wrapping_artifacts(text, max_length=cap)

# LLM preambles echoed from generate_summary and similar prompts
_PREAMBLE_LINE_RE = re.compile(
    r"^here(?:'s|\s+is)\s+a\s+(?:professional,?\s*)?(?:journalistic\s+)?"
    r"summary\s+of\s+the(?:\s+news)?\s+article:?\s*$",
    re.I,
)
_PREAMBLE_INLINE_RE = re.compile(
    r"^here(?:'s|\s+is)\s+a\s+(?:professional,?\s*)?(?:journalistic\s+)?"
    r"summary\s+of\s+the(?:\s+news)?\s+article:?\s*",
    re.I,
)
_META_HEADER_LABELS = frozenset(
    {
        "article summary",
        "news summary",
        "summary",
        "article",
        "news article",
        "professional summary",
        "journalistic summary",
    }
)


def _unwrap_markdown_bold(line: str) -> str | None:
    m = re.fullmatch(r"\*\*(.+?)\*\*", line.strip())
    return m.group(1).strip() if m else None


def _is_meta_header_label(text: str) -> bool:
    t = re.sub(r"^\*+|\*+$", "", text.strip()).strip().lower().rstrip(":")
    if t in _META_HEADER_LABELS:
        return True
    return bool(re.fullmatch(r"(?:article|news)\s+summary", t))


def _strip_llm_prose_preamble(text: str) -> str:
    """Drop echoed prompt intros, **ARTICLE SUMMARY** labels, and unwrap **headline** lines."""
    s = _PREAMBLE_INLINE_RE.sub("", text.strip()).strip()
    lines = s.split("\n")
    kept: list[str] = []
    headline_from_bold: str | None = None

    for line in lines:
        t = line.strip()
        if not t:
            continue
        if _PREAMBLE_LINE_RE.match(t) or _PREAMBLE_INLINE_RE.match(t):
            continue
        if _is_meta_header_label(t):
            continue
        bold = _unwrap_markdown_bold(t)
        if bold:
            if _is_meta_header_label(bold):
                continue
            headline_from_bold = bold
            kept.append(bold)
            continue
        kept.append(t)

    if headline_from_bold:
        return headline_from_bold
    if kept:
        return kept[0]
    return s.strip()


def strip_llm_wrapping_artifacts(text: Optional[str], *, max_length: Optional[int] = None) -> str:
    """
    Remove markdown code fences, extract plain string from a lone JSON object when the model
    returns structured output in a field we display as prose, and drop obvious JSON key echoes.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""

    # Fenced blocks ```json ... ```
    if s.startswith("```"):
        parts = s.split("\n", 1)
        if len(parts) > 1:
            s = parts[1]
        if "```" in s:
            s = s.rsplit("```", 1)[0].strip()

    # Whole value is JSON with a single narrative field
    if s.startswith("{") and s.endswith("}"):
        try:
            obj: Any = json.loads(s)
            if isinstance(obj, dict):
                for key in ("lede", "headline", "summary", "title", "text", "content"):
                    v = obj.get(key)
                    if isinstance(v, str) and v.strip():
                        s = v.strip()
                        break
                else:
                    # Avoid dumping raw dict into UI
                    s = ""
        except json.JSONDecodeError:
            pass

    # Embedded JSON fragment: "title": "Headline here"
    frag = re.search(
        r'["\']?(?:title|headline|summary|lede|event_name)["\']?\s*:\s*["\']((?:\\.|[^"\'\\])+)["\']',
        s,
        re.I,
    )
    if frag:
        s = frag.group(1).replace('\\"', '"').replace("\\'", "'").strip()

    # Leading key echo without full JSON object (common in single-line titles)
    s = re.sub(
        r'^[\{\[\s]*["\']?(?:title|headline|summary|lede|event_name)["\']?\s*:\s*["\']?',
        "",
        s,
        flags=re.I,
    ).strip()

    # Line-by-line: drop lines that look like JSON key declarations or opening braces only
    lines_out: list[str] = []
    for line in s.split("\n"):
        t = line.strip()
        if not t:
            lines_out.append(line)
            continue
        if t in ("{", "}", "[", "]"):
            continue
        if re.match(r'^["\']?(lede|headline|summary|title|who|what|when|where)["\']?\s*:', t, re.I):
            continue
        if re.match(r"^[\{\[]\s*\"", t):
            continue
        lines_out.append(line)
    s = "\n".join(lines_out).strip()

    # Trailing JSON junk and stray quotes
    s = re.sub(r'["\']?\s*[,}\]]+\s*["\']?$', "", s).strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        s = s[1:-1].strip()
    s = re.sub(r'^["\']+', "", s)
    s = re.sub(r'["\']+$', "", s).strip()

    s = _strip_llm_prose_preamble(s)

    # Collapse repeated whitespace for single-line headlines
    if "\n" not in s:
        s = re.sub(r"\s+", " ", s).strip()

    if max_length is not None and len(s) > max_length:
        s = s[: max_length - 1].rsplit(" ", 1)[0] + "…" if " " in s[:max_length] else s[:max_length]

    return s


def sanitize_briefing_title(text: Optional[str], *, max_length: int = 220) -> str:
    """Single-line headline/title cleanup for briefing cards and section headers."""
    s = sanitize_briefing_lede(text, max_length=max_length)
    if "\n" in s:
        s = s.split("\n", 1)[0].strip()
    return s


def sanitize_briefing_lede(text: Optional[str], *, max_length: int = 500) -> str:
    """Headline/lede cleanup for briefing cards — strips prompt echo and uses first substantive line."""
    s = strip_llm_wrapping_artifacts(text, max_length=None)
    if not s:
        return ""
    if "\n\n" in s:
        s = s.split("\n\n", 1)[0].strip()
    elif "\n" in s:
        s = s.split("\n", 1)[0].strip()
    s = _strip_llm_prose_preamble(s)
    if "\n" not in s:
        s = re.sub(r"\s+", " ", s).strip()
    return strip_llm_wrapping_artifacts(s, max_length=max_length)
