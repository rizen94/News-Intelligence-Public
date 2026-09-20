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
            # Skip analysis-template labels (**Main Narrative Thread:** etc.)
            if re.fullmatch(
                r"(?:main\s+narrative\s+thread|narrative\s+thread|"
                r"key\s+developments?|storyline\s+analysis)\s*:?",
                bold.strip(),
                flags=re.I,
            ):
                continue
            if headline_from_bold is None:
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


# Structural headings LLM analysis templates stamp into storyline descriptions.
_READER_LABEL_LINE_RE = re.compile(
    r"^(?:"
    r"storyline\s+analysis(?:\s*:.*)?"
    r"|main\s+narrative\s+thread"
    r"|narrative\s+thread"
    r"|key\s+developments?"
    r"|key\s+points?"
    r"|background(?:\s+information)?"
    r"|overview"
    r"|analysis"
    r"|summary"
    r")\s*:?\s*$",
    re.I,
)
_READER_INLINE_LABEL_RE = re.compile(
    r"^(?:"
    r"storyline\s+analysis\s*:\s*"
    r"|storyline\s*:\s*"
    r"|main\s+narrative\s+thread\s*:?\s*"
    r"|the\s+main\s+narrative\s+thread\s+of\s+this\s+story\s+revolves\s+around\s+"
    r"|key\s+developments?\s*:?\s*"
    r")",
    re.I,
)
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_EMPHASIS_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)")


def _truncate_at_word(text: str, max_length: int) -> str:
    if max_length is None or len(text) <= max_length:
        return text
    cut = text[: max_length - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(",;:—- ") + "…"


def _sentence_case_start(text: str) -> str:
    """Capitalize the first alphabetic character after stripping a mid-sentence preamble."""
    if not text:
        return text
    for i, ch in enumerate(text):
        if ch.isalpha():
            if ch.islower():
                return text[:i] + ch.upper() + text[i + 1 :]
            return text
    return text


def sanitize_reader_dek(
    text: Optional[str],
    *,
    title: Optional[str] = None,
    max_length: int = 280,
) -> str:
    """
    Broadsheet standfirst cleanup.

    Storyline ``description`` / editorial blobs often look like::

        **Storyline Analysis: Title Echo**

        **Main Narrative Thread:**
        The actual prose we want…

    Strip markdown emphasis, drop structural labels and title echoes, keep prose.
    """
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw:
        return ""

    # Light fence/JSON unwrap without the bold-headline shortcut.
    s = strip_json_fence(raw)
    if s.startswith("{") and s.endswith("}"):
        try:
            obj: Any = json.loads(s)
            if isinstance(obj, dict):
                for key in ("lede", "summary", "what", "dek", "text", "content"):
                    v = obj.get(key)
                    if isinstance(v, str) and v.strip():
                        s = v.strip()
                        break
        except json.JSONDecodeError:
            pass

    title_norm = re.sub(r"\s+", " ", (title or "").strip()).casefold()
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n+", s):
        lines: list[str] = []
        for line in block.split("\n"):
            t = line.strip()
            if not t:
                continue
            t = _MD_BOLD_RE.sub(r"\1", t)
            t = _MD_EMPHASIS_RE.sub(r"\1", t)
            t = t.replace("**", "").strip()
            t = re.sub(r"\s+", " ", t).strip()
            if not t:
                continue
            label_candidate = t.rstrip(":").strip()
            if _READER_LABEL_LINE_RE.match(label_candidate):
                continue
            if title_norm and re.sub(r"\s+", " ", t).casefold() == title_norm:
                continue
            # "**Storyline Analysis: Same As Title**" after unwrap
            if title_norm and t.casefold().startswith("storyline analysis:"):
                rest = t.split(":", 1)[1].strip()
                if re.sub(r"\s+", " ", rest).casefold() == title_norm:
                    continue
                t = rest
            t = _READER_INLINE_LABEL_RE.sub("", t).strip()
            if not t or _READER_LABEL_LINE_RE.match(t.rstrip(":").strip()):
                continue
            lines.append(t)
        if lines:
            paragraphs.append(" ".join(lines))

    if not paragraphs:
        # Last resort: strip markers from original and take first sentence-ish.
        flat = _MD_BOLD_RE.sub(r"\1", s)
        flat = flat.replace("**", "")
        flat = re.sub(r"\s+", " ", flat).strip()
        flat = _READER_INLINE_LABEL_RE.sub("", flat).strip()
        if title_norm and re.sub(r"\s+", " ", flat).casefold() == title_norm:
            return ""
        return _truncate_at_word(_sentence_case_start(flat), max_length) if flat else ""

    # Prefer the first paragraph that looks like prose (not a short label leftover).
    chosen = paragraphs[0]
    for p in paragraphs:
        if len(p) >= 40:
            chosen = p
            break

    if title_norm and re.sub(r"\s+", " ", chosen).casefold() == title_norm:
        return ""

    chosen = _sentence_case_start(chosen)
    return _truncate_at_word(chosen, max_length)
