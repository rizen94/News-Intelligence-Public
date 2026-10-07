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

_HTML_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)
_HTML_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_HTML_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)
_HTML_BLOCK_BREAK_RE = re.compile(
    r"</\s*(?:p|div|h[1-6]|li|tr|blockquote|br)\s*>", re.IGNORECASE
)
_HTML_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)


def html_to_visible_text(text: Optional[str], *, max_length: Optional[int] = None) -> str:
    """
    Turn scraped/article HTML into readable prose for reader briefs.

    Guardian RSS often stores ``<p>…</p><ul><li>…`` in ``articles.content``;
    stubs that copy that into expansion ``body_md`` must not reach the SPA as tags.
    """
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw:
        return ""
    if "<" not in raw or not re.search(r"</?[a-zA-Z]", raw):
        out = raw
    else:
        s = _HTML_SCRIPT_RE.sub(" ", raw)
        s = _HTML_STYLE_RE.sub(" ", s)
        s = _HTML_BR_RE.sub("\n", s)
        s = _HTML_BLOCK_BREAK_RE.sub("\n", s)
        s = _HTML_TAG_RE.sub(" ", s)
        s = (
            s.replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&#39;", "'")
            .replace("&apos;", "'")
        )
        s = re.sub(r"[ \t]+\n", "\n", s)
        s = re.sub(r"\n{3,}", "\n\n", s)
        s = re.sub(r"[ \t]{2,}", " ", s)
        out = s.strip()
    if max_length is not None and max_length > 0 and len(out) > max_length:
        out = out[: max_length - 1].rstrip() + "…"
    return out


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


_JSON_TRAILER_MARKERS = (
    "\n---JSON---",
    "\n```json",
    "\n```JSON",
)


def strip_trailing_llm_json(text: Optional[str]) -> str:
    """
    Drop finisher machine trailer: ``---JSON---`` / trailing ```json blocks.

    Narrative finisher prompts require prose then a JSON appendix. Reader surfaces
    must never show that appendix. Prefer the markdown walkthrough ahead of the
    marker; if the whole blob is a JSON object with ``canonical_narrative``,
    use that field instead.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""

    # Explicit machine marker (finisher contract)
    marker = "---JSON---"
    if marker in s:
        prose, rest = s.split(marker, 1)
        prose = prose.strip()
        if prose:
            return prose
        # Marker-only / JSON-first payload — try to recover narrative from JSON.
        rest = strip_json_fence(rest.strip())
        try:
            obj = json.loads(rest)
            if isinstance(obj, dict):
                for key in (
                    "canonical_narrative",
                    "summary",
                    "narrative",
                    "text",
                    "content",
                ):
                    v = obj.get(key)
                    if isinstance(v, str) and v.strip():
                        return strip_trailing_llm_json(v.strip())
        except (json.JSONDecodeError, TypeError):
            pass
        return ""

    # Trailing fenced JSON without the ---JSON--- marker
    for m in _JSON_TRAILER_MARKERS:
        idx = s.find(m)
        if idx > 0:
            return s[:idx].rstrip()

    # Whole-value JSON object with a narrative field
    if s.startswith("{") and ("canonical_narrative" in s or '"lede"' in s):
        try:
            obj = json.loads(strip_json_fence(s))
            if isinstance(obj, dict):
                for key in (
                    "canonical_narrative",
                    "summary",
                    "narrative",
                    "lede",
                    "text",
                    "content",
                ):
                    v = obj.get(key)
                    if isinstance(v, str) and v.strip():
                        return strip_trailing_llm_json(v.strip())
        except (json.JSONDecodeError, TypeError):
            pass

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
    s = strip_trailing_llm_json(str(text).strip())
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
    r"|lede"
    r"|why\s+this\s+is\s+in\s+play"
    r"|timeline\s+of\s+events"
    r"|context"
    r"|current\s+brief(?:\s*:.*)?"
    r"|what\s+happened"
    r"|why\s+it\s+matters"
    r"|now"
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
    r"|current\s+brief\s*:?\s*"
    r"|what\s+happened\s*:?\s*"
    r"|why\s+it\s+matters\s*:?\s*"
    r"|now\s*:?\s*"
    r")",
    re.I,
)
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_EMPHASIS_RE = re.compile(r"(?<!\*)\*(?!\*)([^*]+)\*(?!\*)")
_MD_UNDERSCORE_EMPH_RE = re.compile(r"(?<!_)_([^_\n]+)_(?!_)")
_MD_UNDERSCORE_BOLD_RE = re.compile(r"__([^_]+)__")


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


_INVENTORY_SUMMARY_RE = re.compile(
    r"(?:📊\s*)?Story\s+Overview|components\s+analyzed|"
    r"different\s+outlets|Story\s+Elements\s*:|"
    r"Generated by AI-powered narrative analysis|"
    r"This storyline tracks developments across|"
    r"providing comprehensive coverage of|"
    r"##\s*📖\s*Narrative Analysis|"
    r"The coverage reveals several interconnected themes",
    re.IGNORECASE,
)

_DESK_WALKTHROUGH_RE = re.compile(
    r"(?:^|\n)##\s+(?:Lede|Update|Background|Competing views|What happened|"
    r"Why this is in play|Why it matters)",
    re.IGNORECASE,
)

_FLUFF_THEME_RE = re.compile(
    r"Multiple perspectives on the same core story|"
    r"Evolving developments over time|"
    r"Different sources providing unique angles|"
    r"A complex narrative with multiple stakeholders",
    re.IGNORECASE,
)


_EXCERPT_HEADLINE_RE = re.compile(
    r"\*\*([^*]{12,160})\*\*\s*(?:\([^)]{0,80}\))?\s*—",
)


def is_multi_topic_excerpt_mash(text: Optional[str]) -> bool:
    """
    True when summary is stitched article excerpts from unrelated headlines
    (inventory rebuild format) rather than one coherent narrative.
    """
    if text is None:
        return False
    s = str(text).strip()
    if not s:
        return False
    heads = [h.strip() for h in _EXCERPT_HEADLINE_RE.findall(s)]
    if len(heads) < 2:
        return False

    def _toks(h: str) -> set[str]:
        stop = {
            "the", "and", "for", "with", "from", "that", "this", "have", "has",
            "after", "over", "into", "as", "it", "happened", "news", "said",
            "what", "know", "amid", "near", "new", "says",
        }
        return {
            t
            for t in re.findall(r"[a-z0-9][a-z0-9'-]{3,}", h.lower())
            if t not in stop
        }

    token_sets = [_toks(h) for h in heads]
    # Pairwise: if any pair shares no tokens, treat as mash
    for i in range(len(token_sets)):
        for j in range(i + 1, len(token_sets)):
            if token_sets[i] and token_sets[j] and token_sets[i].isdisjoint(token_sets[j]):
                return True
    # Three+ distinct excerpt blocks is almost always a bag
    return len(heads) >= 3


def is_inventory_metadata_summary(text: Optional[str]) -> bool:
    """
    True when prose is ML pipeline inventory (source counts, date span, fluff themes)
    rather than article-grounded substance.
    """
    if text is None:
        return False
    s = str(text).strip()
    if not s:
        return False
    hits = len(_INVENTORY_SUMMARY_RE.findall(s))
    fluff = len(_FLUFF_THEME_RE.findall(s))
    if hits >= 2:
        return True
    if hits >= 1 and fluff >= 1:
        return True
    if "Story Overview" in s and "components analyzed" in s.casefold():
        return True
    # Pure fallback: overview header + no concrete proper nouns beyond title echo
    if hits >= 1 and len(s) < 2200 and fluff >= 2:
        return True
    return False


def is_desk_walkthrough(text: Optional[str]) -> bool:
    """Editorial walkthrough with desk section headings (not ML inventory)."""
    if not text:
        return False
    s = str(text)
    if is_inventory_metadata_summary(s):
        return False
    matches = _DESK_WALKTHROUGH_RE.findall(s)
    # At least two desk sections, or one section with enough body
    if len(matches) >= 2 and len(s) > 200:
        return True
    return bool(matches) and len(s) > 500


def strip_inventory_metadata_summary(text: Optional[str]) -> str:
    """
    Drop ML inventory wrappers. Prefer any remaining article-grounded prose;
    return empty when the blob is only metadata/fluff.
    """
    if text is None:
        return ""
    s = str(text).strip()
    if not s:
        return ""
    if not is_inventory_metadata_summary(s):
        return s

    # Try to salvage body after Narrative Analysis / after first ---
    body = s
    for marker in (
        "## 📖 Narrative Analysis",
        "## Narrative Analysis",
        "📖 Narrative Analysis",
        "\n---\n",
    ):
        idx = body.find(marker)
        if idx >= 0:
            body = body[idx + len(marker) :].strip()
            body = re.sub(r"^#+\s*", "", body).strip()
            break

    # Drop trailing generator footer
    body = re.sub(
        r"\n\*Generated by AI-powered narrative analysis[^*]*\*\s*$",
        "",
        body,
        flags=re.I,
    ).strip()

    if is_inventory_metadata_summary(body) or _FLUFF_THEME_RE.search(body or ""):
        # Body still inventory / theme boilerplate
        if _FLUFF_THEME_RE.search(body or "") and not re.search(
            r"\b(?:said|announced|voted|ruled|killed|signed|fired|met)\b",
            body or "",
            re.I,
        ):
            return ""
    if is_inventory_metadata_summary(body):
        return ""
    # Still mostly the overview template
    if re.search(r"Sources:\s*\d+\s+different", body or "", re.I):
        return ""
    return body.strip()


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
    raw = strip_inventory_metadata_summary(str(text).strip())
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
            # Drop title echo when it prefixes the line (common in expansion summaries)
            if title_norm:
                t_cf = re.sub(r"\s+", " ", t).casefold()
                if t_cf.startswith(title_norm):
                    rest = t[len(title_norm) :].lstrip(" :-—")
                    t = rest or t
            # Inline structural labels mid-line (e.g. "Title What happened: …")
            t = re.sub(
                r"(?i)\b(?:what\s+happened|why\s+it\s+matters|current\s+brief|now)\s*:\s*",
                "",
                t,
            ).strip()
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


def sanitize_reader_prose(
    text: Optional[str],
    *,
    title: Optional[str] = None,
    max_length: int = 4000,
) -> str:
    """Strip markdown emphasis / banner labels for multi-paragraph reader prose.

    Unlike ``sanitize_reader_dek`` (one standfirst), keeps paragraph breaks for
    hub CURRENT BRIEF bodies rendered as plain text.
    """
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw:
        return ""
    title_norm = re.sub(r"\s+", " ", (title or "").strip()).casefold()
    out_paras: list[str] = []
    for block in re.split(r"\n\s*\n+", raw):
        lines: list[str] = []
        for line in block.split("\n"):
            t = line.strip()
            if not t:
                continue
            # Drop ATX heading markers so "## Lede" becomes a label we can discard
            t = re.sub(r"^\s*#{1,6}\s+", "", t).strip()
            # Markdown list markers → plain bullet (avoid literal "*" in UI)
            t = re.sub(r"^\s*[\*\-•]\s+", "• ", t)
            t = _MD_BOLD_RE.sub(r"\1", t)
            t = _MD_EMPHASIS_RE.sub(r"\1", t)
            t = _MD_UNDERSCORE_BOLD_RE.sub(r"\1", t)
            t = _MD_UNDERSCORE_EMPH_RE.sub(r"\1", t)
            t = t.replace("**", "").replace("__", "").strip()
            t = re.sub(r"\s+", " ", t).strip()
            if not t:
                continue
            label_candidate = t.rstrip(":").strip()
            if _READER_LABEL_LINE_RE.match(label_candidate):
                continue
            t = _READER_INLINE_LABEL_RE.sub("", t).strip()
            t = re.sub(
                r"(?i)\b(?:what\s+happened|why\s+it\s+matters|why\s+this\s+is\s+in\s+play|current\s+brief|now|lede|context)\s*:\s*",
                "",
                t,
            ).strip()
            if not t or _READER_LABEL_LINE_RE.match(t.rstrip(":").strip()):
                continue
            if title_norm and re.sub(r"\s+", " ", t).casefold() == title_norm:
                continue
            lines.append(t)
        if lines:
            # Keep bullet lines on their own rows; join prose lines only.
            chunk: list[str] = []
            prose: list[str] = []

            def _flush_prose() -> None:
                if prose:
                    chunk.append(" ".join(prose))
                    prose.clear()

            for t in lines:
                if t.startswith("• "):
                    _flush_prose()
                    chunk.append(t)
                else:
                    prose.append(t)
            _flush_prose()
            out_paras.append("\n".join(chunk))
    joined = "\n\n".join(out_paras).strip()
    # Repair previously jammed "• a. • b." runs into real list rows
    joined = re.sub(r"\s+•\s+", "\n• ", joined)
    if not joined:
        flat = _MD_BOLD_RE.sub(r"\1", raw).replace("**", "")
        flat = _MD_UNDERSCORE_BOLD_RE.sub(r"\1", flat)
        flat = _MD_UNDERSCORE_EMPH_RE.sub(r"\1", flat)
        flat = re.sub(r"(?m)^\s*[\*\-]\s+", "• ", flat)
        flat = re.sub(r"[ \t]+", " ", flat).strip()
        flat = re.sub(r"\s+•\s+", "\n• ", flat)
        return flat[:max_length] if flat else ""
    if len(joined) <= max_length:
        return joined
    return joined[: max_length - 1].rstrip() + "…"


def sanitize_reader_note_body(
    text: Optional[str],
    *,
    title: Optional[str] = None,
    max_length: int = 8000,
) -> str:
    """Reader-facing vault note: drop YAML frontmatter / HTML comments, then prose sanitize."""
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw:
        return ""
    try:
        from shared.vault_note_contract import split_frontmatter_body

        _fm, body = split_frontmatter_body(raw)
        raw = (body or "").strip() or raw
    except Exception:
        # Inline YAML fence: --- ... ---
        raw = re.sub(r"\A---[\s\S]*?---\s*", "", raw, count=1).strip()
    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL).strip()
    # Drop markdown heading markers but keep the heading words
    raw = re.sub(r"(?m)^\s*#{1,6}\s+", "", raw)
    return sanitize_reader_prose(raw, title=title, max_length=max_length)
