"""Deterministic StakesGate (v12 THIN — no LLM).

Pass when package evidence has: identity actor + act-verb + citeable quote/URL.
Compose must also emit reader sections; else thin_no_stakes.

Canonical reader sections:
  ## What's new
  ## Why this matters
  ## Timeline
  ## What to watch

Aliases keep existing briefs and nut-graf/walkaway manuscripts valid.

VOCABULARY (do not confuse):
  This module is the *editorial package publish gate* only.
  It is NOT the planned L1 four-feature *intake stakes modulator*
  (arousal / targeted_threat / source_surprise / frame_prior).
  See docs/STAKES_VOCABULARY.md.
"""

from __future__ import annotations

import re
from typing import Any

from shared.act_verb_lexicon import ACT_VERB_RE, text_has_act_verb
from shared.editorial_package_vocab import provenance_has_citeable_source

# Canonical headings plus accepted equivalents (briefs, v12 nut-graf/walkaway).
_WHATS_NEW_RE = re.compile(
    r"(^\s*##\s*what'?s new\s*$)|"
    r"(^\s*##\s*what we know\s*$)|"
    r"(^\s*##\s*case briefs\s*$)",
    re.I | re.M,
)
_WHY_MATTERS_RE = re.compile(
    r"(^\s*##\s*why this matters(?:\s*\(nut graf\))?\s*$)|"
    r"(^\s*\*\*nut graf\*\*\s*:)|"
    r"(^\s*nut graf\s*:)",
    re.I | re.M,
)
_TIMELINE_RE = re.compile(
    r"(^\s*##\s*timeline\s*$)|"
    r"(^\s*##\s*supporting evidence\s*$)",
    re.I | re.M,
)
_WATCH_RE = re.compile(
    r"(^\s*##\s*what to watch\s*$)|"
    r"(^\s*##\s*open questions\s*$)|"
    r"(^\s*##\s*walkaway\s*$)|"
    r"(^\s*walkaway\s*:)|"
    r"(^\s*\*\*walkaway\*\*\s*:)",
    re.I | re.M,
)

# Back-compat aliases used by tests and older call sites.
_NUT_GRAF_RE = _WHY_MATTERS_RE
_WALKAWAY_RE = _WATCH_RE


_TITLE_CASE_ACTOR_RE = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")


def package_has_identity_actor(pkg: dict[str, Any] | None) -> bool:
    """True if any active member looks like a named person/org actor."""
    if not pkg:
        return False
    saw_active = False
    for m in pkg.get("members") or []:
        if (m.get("status") or "active") != "active":
            continue
        saw_active = True
        prov = m.get("provenance") or {}
        actors = (
            m.get("parties")
            or prov.get("actors")
            or prov.get("identity_actors")
            or prov.get("key_actors")
            or prov.get("parties")
            or []
        )
        if actors:
            return True
        label = str(
            m.get("label")
            or m.get("title")
            or prov.get("label")
            or prov.get("title")
            or ""
        ).strip()
        mt = str(m.get("member_type") or "").lower()
        if mt in {"chronological_event", "article", "extracted_claim", "context"} and len(
            label
        ) >= 3:
            if _TITLE_CASE_ACTOR_RE.search(label):
                return True
        if mt in {"entity", "person", "organization"}:
            return True
    if saw_active and _TITLE_CASE_ACTOR_RE.search(str(pkg.get("working_title") or "")):
        return True
    return False


def package_has_act_verb(pkg: dict[str, Any] | None) -> bool:
    if not pkg:
        return False
    chunks: list[str] = [
        str(pkg.get("working_title") or ""),
        str(pkg.get("summary_stub") or ""),
        str(pkg.get("title") or ""),
    ]
    for m in pkg.get("members") or []:
        if (m.get("status") or "active") != "active":
            continue
        for key in ("label", "title", "excerpt", "quote", "summary"):
            val = m.get(key)
            if val:
                chunks.append(str(val))
        for key in ("facts", "claims"):
            val = m.get(key)
            if isinstance(val, list):
                chunks.extend(str(x) for x in val if x)
            elif val:
                chunks.append(str(val))
        prov = m.get("provenance") or {}
        for key in (
            "quote",
            "excerpt",
            "title",
            "label",
            "summary",
            "holding",
            "outcome",
            "event_type",
        ):
            if prov.get(key):
                chunks.append(str(prov[key]))
    return text_has_act_verb(" ".join(chunks))


def package_has_citeable_evidence(pkg: dict[str, Any] | None) -> bool:
    if not pkg:
        return False
    for m in pkg.get("members") or []:
        if (m.get("status") or "active") != "active":
            continue
        if provenance_has_citeable_source(m.get("provenance") or {}, for_publish=True):
            return True
        url = (m.get("url") or (m.get("provenance") or {}).get("url") or "").strip()
        quote = (
            m.get("quote")
            or m.get("excerpt")
            or (m.get("provenance") or {}).get("quote")
            or ""
        ).strip()
        if url.startswith("http") or len(quote) >= 24:
            return True
    return False


def manuscript_has_whats_new(text: str | None) -> bool:
    return bool(_WHATS_NEW_RE.search(text or ""))


def manuscript_has_why_matters(text: str | None) -> bool:
    return bool(_WHY_MATTERS_RE.search(text or ""))


def manuscript_has_timeline(text: str | None) -> bool:
    return bool(_TIMELINE_RE.search(text or ""))


def manuscript_has_what_to_watch(text: str | None) -> bool:
    return bool(_WATCH_RE.search(text or ""))


def manuscript_has_nut_graf(text: str | None) -> bool:
    """Back-compat: nut graf == Why this matters."""
    return manuscript_has_why_matters(text)


def manuscript_has_walkaway(text: str | None) -> bool:
    """Back-compat: walkaway == What to watch."""
    return manuscript_has_what_to_watch(text)


def _first_sentence(text: str, *, limit: int = 280) -> str:
    blob = re.sub(r"\s+", " ", (text or "").strip())
    if not blob:
        return ""
    for sep in (". ", "! ", "? "):
        idx = blob.find(sep)
        if 24 <= idx <= limit:
            return blob[: idx + 1].strip()
    return blob[:limit].strip()


def ensure_reader_sections(body_md: str, payload: dict[str, Any] | None = None) -> str:
    """Append missing canonical reader sections from package material. No LLM."""
    payload = payload or {}
    body = (body_md or "").rstrip()
    brief = payload.get("evidence_brief") if isinstance(payload.get("evidence_brief"), dict) else {}
    stub = str(payload.get("summary_stub") or payload.get("working_title") or "").strip()
    lede = str(brief.get("lede") or "").strip()
    questions = brief.get("open_questions") or payload.get("open_questions") or []
    if isinstance(questions, str):
        q_text = questions.strip()
    elif isinstance(questions, list):
        q_text = "; ".join(str(q).strip() for q in questions if str(q).strip())[:400]
    else:
        q_text = ""
    extras: list[str] = []
    if not manuscript_has_whats_new(body):
        extras.append("## What's new\n" + (_first_sentence(lede or stub) or stub or "Developments continue."))
    if not manuscript_has_why_matters(body):
        extras.append(
            "## Why this matters\n"
            + (_first_sentence(stub or lede) or "This development changes who is affected and what happens next.")
        )
    if not manuscript_has_timeline(body):
        dated = []
        for m in payload.get("members") or []:
            ed = m.get("event_date") or (m.get("provenance") or {}).get("event_date")
            label = str(m.get("label") or m.get("title") or "").strip()
            if ed and label:
                dated.append(f"- {ed}: {label}")
            if len(dated) >= 6:
                break
        extras.append("## Timeline\n" + ("\n".join(dated) if dated else "- See cited sources in this report."))
    if not manuscript_has_what_to_watch(body):
        extras.append(
            "## What to watch\n"
            + (q_text or "Watch for the next official filing, ruling, or on-record statement.")
        )
    if not extras:
        return body
    return (body + "\n\n" + "\n\n".join(extras)).strip()


def evaluate_stakes_gate(
    pkg: dict[str, Any] | None,
    *,
    body_md: str | None = None,
    require_sections: bool = True,
) -> dict[str, Any]:
    """
    Deterministic stakes check.

    Returns {ok, reason, checks{...}}. reason is thin_no_stakes when failing.
    """
    checks = {
        "identity_actor": package_has_identity_actor(pkg),
        "act_verb": package_has_act_verb(pkg),
        "citeable": package_has_citeable_evidence(pkg),
        "whats_new": True,
        "why_matters": True,
        "timeline": True,
        "what_to_watch": True,
        # Back-compat keys used by older tests/callers
        "nut_graf": True,
        "walkaway": True,
    }
    if require_sections:
        blob = body_md or ""
        checks["whats_new"] = manuscript_has_whats_new(blob)
        checks["why_matters"] = manuscript_has_why_matters(blob)
        checks["timeline"] = manuscript_has_timeline(blob)
        checks["what_to_watch"] = manuscript_has_what_to_watch(blob)
        checks["nut_graf"] = checks["why_matters"]
        checks["walkaway"] = checks["what_to_watch"]
        if not checks["act_verb"] and text_has_act_verb(blob):
            checks["act_verb"] = True

    required = (
        "identity_actor",
        "act_verb",
        "citeable",
        "whats_new",
        "why_matters",
        "timeline",
        "what_to_watch",
    )
    ok = all(checks[k] for k in required)
    return {
        "ok": ok,
        "reason": None if ok else "thin_no_stakes",
        "checks": checks,
        "act_verb_pattern": ACT_VERB_RE.pattern,
    }
