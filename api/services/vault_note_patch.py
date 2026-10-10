"""
Markdown patch helpers for vault notes — agent fences only; human text sacred.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from shared.vault_note_contract import (
    AUTO_BRIEF_END,
    AUTO_BRIEF_START,
    AUTO_POSTURE_END,
    AUTO_POSTURE_START,
    AUTO_SIGNIFICANCE_END,
    AUTO_SIGNIFICANCE_START,
    AUTO_TIMELINE_END,
    AUTO_TIMELINE_START,
)

_FENCE_SPECS = (
    ("posture", AUTO_POSTURE_START, AUTO_POSTURE_END),
    ("timeline", AUTO_TIMELINE_START, AUTO_TIMELINE_END),
    ("significance", AUTO_SIGNIFICANCE_START, AUTO_SIGNIFICANCE_END),
    ("brief", AUTO_BRIEF_START, AUTO_BRIEF_END),
)


def content_fingerprint(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:40]


def ensure_fences(body: str) -> str:
    """Ensure auto fence markers exist so patches have a home."""
    out = body or ""
    if AUTO_BRIEF_START not in out:
        brief_block = (
            f"\n## Current brief\n\n{AUTO_BRIEF_START}\n"
            f"_Brief updates when the situation moves._\n{AUTO_BRIEF_END}\n"
        )
        if out.lstrip().startswith("#"):
            lines = out.splitlines()
            insert_at = 1
            while insert_at < len(lines) and not lines[insert_at].strip():
                insert_at += 1
            out = "\n".join(lines[:insert_at]) + brief_block + "\n".join(lines[insert_at:])
        else:
            out = brief_block.lstrip() + "\n" + out
    if AUTO_TIMELINE_START not in out:
        out += f"\n\n## Timeline\n\n{AUTO_TIMELINE_START}\n{AUTO_TIMELINE_END}\n"
    if AUTO_POSTURE_START not in out:
        out += f"\n\n## Current posture\n\n{AUTO_POSTURE_START}\n_No automated posture yet._\n{AUTO_POSTURE_END}\n"
    if AUTO_SIGNIFICANCE_START not in out:
        out += (
            f"\n\n## Significance\n\n{AUTO_SIGNIFICANCE_START}\n"
            f"_Significance synthesised when evidence accumulates._\n{AUTO_SIGNIFICANCE_END}\n"
        )
    return out


def _replace_fence(body: str, start: str, end: str, inner: str) -> str:
    pattern = re.compile(
        re.escape(start) + r"(.*?)" + re.escape(end),
        re.DOTALL,
    )
    replacement = f"{start}\n{(inner or '').strip()}\n{end}"
    if pattern.search(body):
        return pattern.sub(replacement, body, count=1)
    return body.rstrip() + "\n\n" + replacement + "\n"


def replace_auto_section(body: str, section: str, inner: str) -> str:
    for name, start, end in _FENCE_SPECS:
        if name == section:
            return _replace_fence(body, start, end, inner)
    raise ValueError(f"unknown auto section: {section}")


def read_auto_section(body: str, section: str) -> str:
    for name, start, end in _FENCE_SPECS:
        if name != section:
            continue
        m = re.search(
            re.escape(start) + r"(.*?)" + re.escape(end),
            body or "",
            re.DOTALL,
        )
        return (m.group(1) if m else "").strip()
    return ""


def append_timeline_bullet(body: str, bullet: str) -> str:
    """Append one timeline line inside the auto fence; skip if already present."""
    body = ensure_fences(body)
    line = bullet.strip()
    if not line.startswith("-"):
        line = f"- {line}"
    current = read_auto_section(body, "timeline")
    # Idempotent: article_id or exact line already there
    if line in current:
        return body
    # Also check bare article citation
    m = re.search(r"\(article:(\d+)\)", line)
    if m and f"(article:{m.group(1)})" in current:
        return body
    new_inner = (current + "\n" + line).strip() if current else line
    return replace_auto_section(body, "timeline", new_inner)


def append_correction_block(body: str, *, date: str, text: str, article_id: int | None) -> str:
    """Human-safe correction: append dated block outside auto fences."""
    cite = f" (article:{article_id})" if article_id else ""
    block = f"\n\n### Correction — {date}{cite}\n\n{(text or '').strip()}\n"
    if block.strip() in (body or ""):
        return body
    return (body or "").rstrip() + block


def validate_patch_payload(payload: dict[str, Any]) -> tuple[bool, str]:
    """Reject empty/junk LLM proposals."""
    timeline = (payload.get("timeline_bullet") or "").strip()
    posture = (payload.get("posture") or "").strip()
    significance = (payload.get("significance") or "").strip()
    correction = (payload.get("correction") or "").strip()
    if not any([timeline, posture, significance, correction]):
        return False, "empty_patch"
    for field, val in (
        ("timeline_bullet", timeline),
        ("posture", posture),
        ("significance", significance),
    ):
        if not val:
            continue
        low = val.lower()
        if low in ("n/a", "none", "null", "todo", "tbd", "..."):
            return False, f"junk_{field}"
        if len(val) < 12 and field != "timeline_bullet":
            return False, f"too_short_{field}"
    return True, "ok"


def theme_tokens(title: str) -> set[str]:
    stop = {
        "with",
        "from",
        "that",
        "this",
        "have",
        "been",
        "will",
        "were",
        "their",
        "about",
        "after",
        "the",
        "and",
        "for",
        "into",
    }
    toks = set(re.findall(r"[a-z0-9]{4,}", (title or "").lower()))
    return {t for t in toks if t not in stop}


def on_theme(note_title: str, evidence_text: str, *, min_overlap: int = 1) -> bool:
    note_toks = theme_tokens(note_title)
    ev_toks = theme_tokens(evidence_text)
    if not note_toks or not ev_toks:
        return True  # insufficient signal — allow
    return len(note_toks & ev_toks) >= min_overlap


def patch_auto_sections(
    body: str,
    *,
    timeline_bullets: list[str] | None = None,
    significance: str | None = None,
    posture: str | None = None,
    brief: str | None = None,
) -> str:
    """Replace auto fences for hub/timeline maintenance writers."""
    out = ensure_fences(body or "")
    if brief is not None and str(brief).strip():
        out = replace_auto_section(out, "brief", str(brief).strip())
    if timeline_bullets is not None:
        inner = "\n".join(
            (b if b.strip().startswith("-") else f"- {b.strip()}")
            for b in timeline_bullets
            if b and str(b).strip()
        ) or "- _No articles._"
        out = replace_auto_section(out, "timeline", inner)
    if significance is not None and str(significance).strip():
        out = replace_auto_section(out, "significance", str(significance).strip())
    if posture is not None and str(posture).strip():
        out = replace_auto_section(out, "posture", str(posture).strip())
    return out
