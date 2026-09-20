"""
Editorial package Editor compose / publish assembly (v11).

Draft compose recovers source detail into a news_stories manuscript.
Publish mode is the final assembly: cover linked active sources in a detailed
cited report, then the publish gate validates citations and marks published.

Gated by EDITORIAL_COMPOSE_ENABLED. LLM: PopOS STORYLINE_NARRATIVE_FINISH.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Literal

from config.runtime import env_bool, env_int
from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_vocab import provenance_has_citeable_source

logger = logging.getLogger(__name__)

ComposeMode = Literal["draft", "publish"]

PROMPT_VERSION = "package_compose.v1"
PROMPT_VERSION_PUBLISH = "package_publish.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "editor"
    / "package_compose.md"
)
PUBLISH_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "editor"
    / "package_publish.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_TOKEN = re.compile(r"[a-z0-9]+")
_CITATION = re.compile(r"\[@m(\d+)\]")
_SCAFFOLD_MARKERS = (
    "## Source anchors",
    "Draft pending editorial composition",
)
# Too common in news packages to count alone as on-theme.
_THEME_STOP = frozenset(
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
        "trump",
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
    }
)


def is_enabled() -> bool:
    return env_bool("EDITORIAL_COMPOSE_ENABLED", True)


def max_members(mode: ComposeMode = "draft") -> int:
    if mode == "publish":
        return max(12, min(env_int("EDITORIAL_PUBLISH_MAX_MEMBERS", 40), 60))
    return max(8, min(env_int("EDITORIAL_COMPOSE_MAX_MEMBERS", 24), 40))


def min_body_chars(mode: ComposeMode = "draft") -> int:
    if mode == "publish":
        return max(400, env_int("EDITORIAL_PUBLISH_MIN_BODY_CHARS", 900))
    return max(120, env_int("EDITORIAL_COMPOSE_MIN_BODY_CHARS", 280))


def _load_prompt(mode: ComposeMode = "draft") -> str:
    path = PUBLISH_PROMPT_PATH if mode == "publish" else PROMPT_PATH
    try:
        return path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("compose prompt missing (%s): %s", mode, e)
        if mode == "publish":
            return (
                "Write a detailed final report from linked package members. "
                "Output JSON with title, lede, body_md using [@mID] markers. "
                "Cover linked sources; no source lists."
            )
        return (
            "Write a cited news draft from package members. Output JSON with "
            "title, lede, body_md using [@mID] markers. No source lists."
        )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _clean_text(val: Any, *, limit: int = 900) -> str:
    if val is None:
        return ""
    if isinstance(val, dict):
        val = val.get("quote") or val.get("text") or val.get("summary") or ""
    text = unescape(_HTML_TAG.sub(" ", str(val)))
    # Broken/partial tags from truncated HTML excerpts
    text = re.sub(r"</?[a-zA-Z][^>\s]*", " ", text)
    text = _WS.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _tokens(text: str) -> set[str]:
    out = set()
    for t in _TOKEN.findall((text or "").lower()):
        if len(t) < 4 or t in _THEME_STOP:
            continue
        if t.isdigit():
            continue
        out.add(t)
    return out


def _focus_tokens(title: str, stub: str) -> set[str]:
    """Distinctive theme tokens; title tokens are required when present."""
    spine = _tokens(title)
    stub_toks = _tokens(stub)
    if spine:
        # Allow stub entities too, but scoring hard-gates on spine overlap.
        return spine | stub_toks
    return stub_toks


def scrub_unbound_citations(body_md: str, allowed_ids: set[int]) -> str:
    """Drop [@mID] markers that are not in the allowed (active/citeable) set."""

    def _keep(mo: re.Match[str]) -> str:
        return mo.group(0) if int(mo.group(1)) in allowed_ids else ""

    return _CITATION.sub(_keep, body_md or "")


def _citeable_active_ids(pkg: dict[str, Any], payload: dict[str, Any]) -> set[int]:
    """IDs the citation gate will accept — active members with URL/quote in DB provenance.

    Payload-only hydration is not enough; validate_prose_citations reads stored provenance.
    """
    allowed: set[int] = set()
    for m in pkg.get("members") or []:
        if (m.get("status") or "active") != "active" or m.get("id") is None:
            continue
        if provenance_has_citeable_source(m.get("provenance") or {}, for_publish=True):
            allowed.add(int(m["id"]))
    return allowed


def is_thin_scaffold_body(body_md: str | None) -> bool:
    """True when body is empty or the stub/source-list placeholder."""
    body = (body_md or "").strip()
    if not body:
        return True
    if any(m in body for m in _SCAFFOLD_MARKERS):
        return True
    prose = _CITATION.sub(" ", body)
    prose = _WS.sub(" ", prose).strip()
    # Marker dump with almost no prose
    if len(prose) < 80 and "[@m" in body:
        return True
    return False


def needs_compose(package_id: int) -> bool:
    """Draft missing, thin scaffold, or no story yet."""
    from services.editorial_package_service import get_package

    pkg = get_package(package_id, include=False)
    if not pkg:
        return False
    status = str(pkg.get("status") or "")
    if status not in ("ready_for_editor", "in_editing", "in_narrative", "in_reduction"):
        # Still allow compose for ready/in_editing primarily
        if status not in ("ready_for_editor", "in_editing"):
            return False
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT body_md, status
                FROM intelligence.news_stories
                WHERE package_id = %s
                ORDER BY CASE WHEN status = 'published' THEN 0
                              WHEN status = 'draft' THEN 1
                              ELSE 2 END, id DESC
                LIMIT 1
                """,
                (package_id,),
            )
            row = cur.fetchone()
    if not row:
        return True
    body, story_status = row[0], row[1]
    if story_status == "published" and not is_thin_scaffold_body(body):
        return False
    return is_thin_scaffold_body(body)


def _member_excerpt(member: dict[str, Any], *, mode: ComposeMode = "draft") -> dict[str, Any]:
    prov = member.get("provenance") if isinstance(member.get("provenance"), dict) else {}
    label = _clean_text(
        prov.get("label") or prov.get("title") or member.get("member_type"),
        limit=180,
    )
    quote_limit = 1600 if mode == "publish" else 900
    quote = _clean_text(
        prov.get("quote")
        or prov.get("quote_span")
        or prov.get("summary")
        or prov.get("snippet")
        or "",
        limit=quote_limit,
    )
    url = _clean_text(prov.get("source_url") or prov.get("url") or "", limit=240)
    return {
        "member_row_id": int(member["id"]),
        "member_type": member.get("member_type"),
        "member_id": member.get("member_id"),
        "domain_key": member.get("domain_key"),
        "role": member.get("role"),
        "member_family": member.get("member_family"),
        "label": label,
        "excerpt": quote,
        "url": url or None,
        "citeable": provenance_has_citeable_source(prov, for_publish=True),
        # Filled by hydrate_member_evidence for publish/draft substance.
        "parties": [],
        "claims": [],
        "holding": None,
        "outcome": None,
        "event_date": None,
        "facts": [],
    }


_JUDICIARY_ROLES = frozenset(
    {
        "judiciary",
        "supreme court justice",
        "justice",
        "justices",
        "judges",
        "judge",
        "court",
        "chief justice",
    }
)


def _parse_actor_names(raw: Any, *, skip_judiciary: bool = True) -> list[str]:
    names: list[str] = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            text = _clean_text(raw, limit=240)
            return [text] if text else []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = _clean_text(item.get("name") or item.get("label") or "", limit=120)
                role = _clean_text(item.get("role") or "", limit=80)
                if skip_judiciary and role.lower() in _JUDICIARY_ROLES:
                    continue
                if name and role:
                    names.append(f"{name} ({role})")
                elif name:
                    names.append(name)
            else:
                name = _clean_text(item, limit=120)
                if name:
                    names.append(name)
    return names[:12]


def hydrate_member_evidence(
    rows: list[dict[str, Any]],
    *,
    mode: ComposeMode = "draft",
) -> list[dict[str, Any]]:
    """Pull CE/article/claim substance from source tables into compose rows.

    Package member provenance is often label/URL-only for chronological_events.
    Publish needs defendants, holdings, and outcomes from the underlying rows.
    """
    if not rows:
        return rows

    from shared.domain_registry import resolve_domain_schema

    ce_ids = [
        int(r["member_id"])
        for r in rows
        if r.get("member_type") == "chronological_event" and r.get("member_id") is not None
    ]
    claim_ids = [
        int(r["member_id"])
        for r in rows
        if r.get("member_type")
        in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal")
        and r.get("member_id") is not None
    ]
    articles_by_schema: dict[str, list[int]] = {}
    for r in rows:
        if r.get("member_type") != "article" or r.get("member_id") is None:
            continue
        dk = str(r.get("domain_key") or "").strip()
        schema = resolve_domain_schema(dk) if dk else None
        if not schema:
            continue
        articles_by_schema.setdefault(schema, []).append(int(r["member_id"]))

    ce_by_id: dict[int, dict[str, Any]] = {}
    claim_by_id: dict[int, dict[str, Any]] = {}
    article_by_key: dict[tuple[str, int], dict[str, Any]] = {}

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if ce_ids:
                cur.execute(
                    """
                    SELECT id, title, description, outcome, key_actors, entities,
                           actual_event_date, event_date, source_text, location
                    FROM public.chronological_events
                    WHERE id = ANY(%s)
                    """,
                    (ce_ids,),
                )
                for row in _rows_from_cursor(cur):
                    ce_by_id[int(row["id"])] = row
            if claim_ids:
                cur.execute(
                    """
                    SELECT id, subject_text, predicate_text, object_text,
                           confidence, metadata
                    FROM intelligence.extracted_claims
                    WHERE id = ANY(%s)
                    """,
                    (claim_ids,),
                )
                for row in _rows_from_cursor(cur):
                    claim_by_id[int(row["id"])] = row
            for schema, ids in articles_by_schema.items():
                if not ids:
                    continue
                try:
                    cur.execute(
                        f"""
                        SELECT id, title, summary, content, url
                        FROM {schema}.articles
                        WHERE id = ANY(%s)
                        """,
                        (ids,),
                    )
                    for row in _rows_from_cursor(cur):
                        article_by_key[(schema, int(row["id"]))] = row
                except Exception as e:
                    logger.debug("hydrate articles %s failed: %s", schema, e)

    excerpt_limit = 1800 if mode == "publish" else 900
    for r in rows:
        mid = r.get("member_id")
        mt = r.get("member_type")
        if mt == "chronological_event" and mid is not None and int(mid) in ce_by_id:
            from shared.editorial_package_theme import parse_case_caption_parties

            ce = ce_by_id[int(mid)]
            description = _clean_text(ce.get("description") or "", limit=excerpt_limit)
            outcome = _clean_text(ce.get("outcome") or "", limit=600)
            source_text = _clean_text(ce.get("source_text") or "", limit=excerpt_limit)
            title = _clean_text(ce.get("title") or "", limit=200)
            # Caption "A v. B" litigants beat justice/court names as parties.
            parties = (
                parse_case_caption_parties(title)
                or parse_case_caption_parties(f"{title} {description[:400]}")
                or _parse_actor_names(ce.get("key_actors"), skip_judiciary=True)
                or _parse_actor_names(ce.get("entities"), skip_judiciary=True)
            )
            if title and not r.get("label"):
                r["label"] = title
            elif title and title.lower() not in str(r.get("label") or "").lower():
                r["label"] = title
            r["parties"] = parties
            r["outcome"] = outcome or None
            r["holding"] = outcome or None
            r["event_date"] = str(
                ce.get("actual_event_date") or ce.get("event_date") or ""
            ) or None
            facts = [x for x in (description, outcome, source_text) if x]
            r["facts"] = facts[:4]
            # Prefer real CE substance over empty provenance quotes.
            if description and (
                not r.get("excerpt")
                or len(str(r.get("excerpt") or "")) < 80
                or str(r.get("excerpt") or "").strip() == str(r.get("label") or "").strip()
            ):
                r["excerpt"] = description
            elif source_text and not r.get("excerpt"):
                r["excerpt"] = source_text
            if description:
                r["claims"] = [description]
            elif outcome:
                r["claims"] = [outcome]
            if outcome:
                # Keep holding/outcome separate; avoid duplicating into claims twice.
                pass
        elif (
            mt in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal")
            and mid is not None
            and int(mid) in claim_by_id
        ):
            cl = claim_by_id[int(mid)]
            subj = _clean_text(cl.get("subject_text") or "", limit=200)
            pred = _clean_text(cl.get("predicate_text") or "", limit=200)
            obj = _clean_text(cl.get("object_text") or "", limit=400)
            triple = " ".join(x for x in (subj, pred, obj) if x).strip()
            if triple:
                r["claims"] = [triple]
                if not r.get("excerpt") or len(str(r.get("excerpt") or "")) < 40:
                    r["excerpt"] = triple
                if subj:
                    r["parties"] = [subj]
                r["facts"] = [triple]
        elif mt == "article" and mid is not None:
            dk = str(r.get("domain_key") or "").strip()
            schema = resolve_domain_schema(dk) if dk else None
            art = article_by_key.get((schema or "", int(mid))) if schema else None
            if art:
                content = _clean_text(
                    art.get("content") or art.get("summary") or "",
                    limit=excerpt_limit,
                )
                title = _clean_text(art.get("title") or "", limit=200)
                if title and not r.get("label"):
                    r["label"] = title
                if content and (
                    not r.get("excerpt") or len(str(r.get("excerpt") or "")) < 200
                ):
                    r["excerpt"] = content
                if art.get("url") and not r.get("url"):
                    r["url"] = _clean_text(art.get("url"), limit=240)
                from shared.editorial_package_theme import parse_case_caption_parties

                caption_parties = parse_case_caption_parties(f"{title} {content[:500]}")
                if caption_parties and not r.get("parties"):
                    r["parties"] = caption_parties
                # Lightweight party/holding cues from article text for legal briefs.
                lowered = content.lower()
                facts = []
                for needle, label in (
                    ("held that", "holding cue"),
                    ("ruled that", "holding cue"),
                    ("vote of", "vote cue"),
                    ("plaintiff", "party cue"),
                    ("defendant", "party cue"),
                    ("petitioner", "party cue"),
                    ("respondent", "party cue"),
                ):
                    if needle in lowered:
                        facts.append(label)
                if facts:
                    r["facts"] = list(dict.fromkeys((r.get("facts") or []) + facts))[:6]
    return rows


def _rows_from_cursor(cur: Any) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _active_links(package: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for ln in package.get("links") or []:
        if (ln.get("status") or "active") != "active":
            continue
        try:
            out.append(
                {
                    "from_member_id": int(ln["from_member_id"]),
                    "to_member_id": int(ln["to_member_id"]),
                    "link_type": ln.get("link_type"),
                }
            )
        except (TypeError, ValueError, KeyError):
            continue
    return out


def _linked_member_ids(links: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for ln in links:
        ids.add(int(ln["from_member_id"]))
        ids.add(int(ln["to_member_id"]))
    return ids


def build_compose_payload(
    package: dict[str, Any],
    *,
    mode: ComposeMode = "draft",
) -> dict[str, Any]:
    title = str(package.get("working_title") or "").strip()
    stub = str(package.get("summary_stub") or "").strip()
    focus = _focus_tokens(title, stub)
    spine = _tokens(title)
    active = [m for m in (package.get("members") or []) if m.get("status") == "active"]
    links = _active_links(package)
    linked_ids = _linked_member_ids(links)

    rows: list[dict[str, Any]] = []
    for m in active:
        row = _member_excerpt(m, mode=mode)
        rows.append(row)
    # Hydrate before scoring so empty CE provenance still carries holdings/parties.
    rows = hydrate_member_evidence(rows, mode=mode)

    for row in rows:
        mid = int(row["member_row_id"])
        member_toks = _tokens(
            f"{row.get('label')} {row.get('excerpt')} "
            f"{' '.join(row.get('facts') or [])} "
            f"{' '.join(row.get('claims') or [])}"
        )
        overlap = len(member_toks & focus)
        spine_overlap = len(member_toks & spine) if spine else overlap
        linked = mid in linked_ids
        if mode == "publish":
            # Publish covers the kept graph — linked members win; unlinked are backup.
            score = 50 if linked else 0
            if row.get("excerpt"):
                score += 10
            if row.get("holding") or row.get("outcome"):
                score += 15
            if row.get("parties"):
                score += 8
            if row.get("claims"):
                score += 6
            if row.get("role") in ("anchor_event", "supporting", "core_claim"):
                score += 3
            if spine_overlap:
                score += spine_overlap * 2
            if not row.get("citeable"):
                score -= 5
        else:
            if spine and spine_overlap == 0:
                score = 0
            else:
                score = spine_overlap * 20 + max(0, overlap - spine_overlap) * 5
                if row.get("excerpt"):
                    score += 2
                if row.get("role") in ("anchor_event", "supporting", "core_claim"):
                    score += 1
            if not row.get("citeable"):
                score -= 3
        row["theme_score"] = score
        row["theme_overlap"] = overlap
        row["linked"] = linked

    rows.sort(
        key=lambda r: (
            -int(r.get("theme_score") or 0),
            0 if r.get("excerpt") else 1,
            0 if r.get("role") == "anchor_event" else 1,
            int(r["member_row_id"]),
        )
    )

    limit = max_members(mode)
    if mode == "publish":
        selected = [r for r in rows if r.get("linked")][:limit]
        if len(selected) < 4:
            # Sparse/no links: fall back to strongest excerpt-backed actives.
            for r in rows:
                if r in selected:
                    continue
                if r.get("excerpt") or r.get("citeable"):
                    selected.append(r)
                if len(selected) >= limit:
                    break
        elif len(selected) < limit:
            for r in rows:
                if r in selected or not r.get("excerpt"):
                    continue
                selected.append(r)
                if len(selected) >= min(limit, len(selected) + 8):
                    break
    else:
        on_theme = [r for r in rows if int(r.get("theme_score") or 0) > 0]
        selected = on_theme[: min(12, limit)]
        if not selected:
            for r in rows:
                if r.get("excerpt") or r.get("citeable"):
                    selected.append(r)
                if len(selected) >= 8:
                    break
        elif len(selected) < 3:
            theme_pool = set()
            for r in selected:
                theme_pool |= _tokens(f"{r.get('label')} {r.get('excerpt')}")
            theme_pool &= focus
            for r in rows:
                if r in selected:
                    continue
                if not r.get("excerpt"):
                    continue
                if _tokens(f"{r.get('label')} {r.get('excerpt')}") & theme_pool:
                    selected.append(r)
                if len(selected) >= 6:
                    break

    instructions = (
        "Write a case-brief style final report. Prefer expanding the provided "
        "evidence_brief (keep its section structure) with concrete parties, holdings, "
        "dates, and corroboration from members. Cite [@mMEMBER_ROW_ID]. "
        "No vague stakes language. No source-list section."
        if mode == "publish"
        else (
            "Recover concrete details from excerpts. Cite with [@mMEMBER_ROW_ID]. "
            "Ignore off-theme members. No source-list section."
        )
    )

    evidence_brief = None
    try:
        from services.package_evidence_brief_service import get_brief

        evidence_brief = get_brief(int(package["id"]))
    except Exception as e:
        logger.debug("compose load evidence brief failed: %s", e)

    return {
        "package_id": package.get("id"),
        "mode": mode,
        "working_title": title,
        "summary_stub": stub,
        "presentation_kind": package.get("presentation_kind"),
        "domain_keys": list(package.get("domain_keys") or []),
        "evidence_brief": (
            {
                "status": evidence_brief.get("status"),
                "lede": evidence_brief.get("lede"),
                "brief_md": evidence_brief.get("brief_md"),
                "open_questions": evidence_brief.get("open_questions"),
                "citation_registry": evidence_brief.get("citation_registry"),
                "density": evidence_brief.get("density"),
            }
            if evidence_brief
            else None
        ),
        "members": [
            {
                k: v
                for k, v in r.items()
                if k not in ("theme_score", "theme_overlap")
            }
            for r in selected
        ],
        "links": links[:80],
        "linked_member_count": len(linked_ids),
        "instructions": instructions,
        "required_detail_fields": [
            "parties",
            "claims",
            "holding",
            "outcome",
            "facts",
            "excerpt",
            "event_date",
        ],
    }


def _extractive_fallback(
    payload: dict[str, Any],
    *,
    mode: ComposeMode = "draft",
) -> dict[str, Any]:
    """Deterministic draft/report from excerpts when LLM is unavailable."""
    brief = payload.get("evidence_brief") if isinstance(payload.get("evidence_brief"), dict) else None
    if mode == "publish" and brief and (brief.get("brief_md") or "").strip():
        return {
            "title": payload.get("working_title") or "Untitled",
            "lede": brief.get("lede") or payload.get("summary_stub") or "",
            "body_md": brief.get("brief_md"),
            "used_member_ids": [
                int(k[1:])
                for k in (brief.get("citation_registry") or {})
                if isinstance(k, str) and k.startswith("m") and k[1:].isdigit()
            ],
            "fallback": True,
            "from_evidence_brief": True,
        }
    title = str(payload.get("working_title") or "Untitled").strip()
    stub = str(payload.get("summary_stub") or "").strip()
    members = [m for m in (payload.get("members") or []) if m.get("excerpt")]
    if not members and payload.get("members"):
        members = list(payload.get("members") or [])[:8]
    deduped: list[dict[str, Any]] = []
    seen_excerpts: set[str] = set()
    for m in members:
        key = _clean_text(m.get("excerpt") or m.get("label") or "", limit=160).lower()
        if key in seen_excerpts:
            continue
        seen_excerpts.add(key)
        deduped.append(m)
    members = deduped
    used: list[int] = []
    paras: list[str] = []

    if mode == "publish":
        if stub:
            paras.append(stub)
        paras.append("## Case briefs")
        for m in members:
            mid = int(m["member_row_id"])
            label = _clean_text(m.get("label") or "", limit=160)
            parties = m.get("parties") or []
            holding = _clean_text(m.get("holding") or m.get("outcome") or "", limit=500)
            claims = m.get("claims") or []
            facts = m.get("facts") or []
            excerpt = _clean_text(m.get("excerpt") or "", limit=500)
            event_date = m.get("event_date")
            if not any([parties, holding, claims, facts, excerpt]):
                continue
            paras.append(f"### {label or f'Member {mid}'}")
            if event_date:
                paras.append(f"- **Date:** {event_date}")
            if parties:
                paras.append(f"- **Parties / actors:** {', '.join(str(p) for p in parties)}")
            if claims:
                paras.append(
                    "- **Claims / legal question:** "
                    + "; ".join(_clean_text(c, limit=240) for c in claims[:3])
                )
            if holding:
                paras.append(f"- **Holding / outcome:** {holding}")
            detail = excerpt or (facts[0] if facts else "")
            if detail and detail != holding:
                paras.append(f"- **Detail:** {detail}")
            paras.append(f"[@m{mid}]")
            used.append(mid)
        selected_ids = {int(m["member_row_id"]) for m in members if m.get("member_row_id") is not None}
        kept_links = [
            ln
            for ln in (payload.get("links") or [])[:20]
            if int(ln["from_member_id"]) in selected_ids
            and int(ln["to_member_id"]) in selected_ids
        ]
        if kept_links:
            paras.append("## Connections")
            id_to_label = {
                int(m["member_row_id"]): _clean_text(m.get("label") or "", limit=80)
                for m in members
            }
            for ln in kept_links:
                frm = int(ln["from_member_id"])
                to = int(ln["to_member_id"])
                lt = ln.get("link_type") or "related"
                a = id_to_label.get(frm) or f"[@m{frm}]"
                b = id_to_label.get(to) or f"[@m{to}]"
                paras.append(f"- {a} —{lt}→ {b} [@m{frm}] [@m{to}]")
                used.extend([frm, to])
    else:
        if stub:
            first_ids = [int(m["member_row_id"]) for m in members[:2]]
            cites = " ".join(f"[@m{i}]" for i in first_ids)
            paras.append(f"{stub} {cites}".strip())
            used.extend(first_ids)
        for m in members[:6]:
            mid = int(m["member_row_id"])
            excerpt = _clean_text(m.get("excerpt") or m.get("label") or "", limit=420)
            if not excerpt:
                continue
            label = _clean_text(m.get("label") or "", limit=100)
            if label:
                paras.append(f"Reporting under “{label}” adds: {excerpt} [@m{mid}]")
            else:
                paras.append(f"{excerpt} [@m{mid}]")
            used.append(mid)

    body = "\n\n".join(p.strip() for p in paras if p.strip())
    lede = stub or (paras[0][:280] if paras else title)
    # Deduplicate used ids preserving order
    seen_u: set[int] = set()
    used_unique = []
    for mid in used:
        if mid not in seen_u:
            seen_u.add(mid)
            used_unique.append(mid)
    return {
        "title": title,
        "lede": lede[:400],
        "body_md": body,
        "used_member_ids": used_unique,
        "omitted_off_theme": [],
        "insufficient_evidence": len(body) < min_body_chars(mode),
        "gaps": [] if body else ["no_excerpts"],
        "fallback": "extractive",
    }


def validate_compose_payload(
    raw: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
    mode: ComposeMode = "draft",
) -> dict[str, Any]:
    allowed = {
        int(m["member_row_id"])
        for m in (payload.get("members") or [])
        if m.get("member_row_id") is not None
    }
    if not raw:
        return _extractive_fallback(payload, mode=mode)

    title = _clean_text(raw.get("title") or payload.get("working_title") or "", limit=240)
    lede = _clean_text(raw.get("lede") or "", limit=500)
    body = str(raw.get("body_md") or "").strip()
    # Strip accidental source-list sections the model may still emit
    if "## Source anchors" in body:
        body = body.split("## Source anchors", 1)[0].rstrip()

    # Reject schema-echo / placeholder bodies from weak models
    placeholder_hints = (
        "markdown body with inline",
        "no source-list section",
        "[@mid]",
        "member_row_id",
        "output schema",
        "<actual multi-section",
        "<detailed multi-section",
    )
    body_l = body.lower()
    if any(h in body_l for h in placeholder_hints) or len(body) < 80:
        return _extractive_fallback(payload, mode=mode)

    markers = [int(x) for x in _CITATION.findall(body + " " + lede)]
    bad = [m for m in markers if m not in allowed]
    if bad:
        # Drop illegal markers rather than fail entirely
        def _scrub(text: str) -> str:
            def repl(mo: re.Match[str]) -> str:
                mid = int(mo.group(1))
                return mo.group(0) if mid in allowed else ""

            return _CITATION.sub(repl, text)

        body = _scrub(body)
        lede = _scrub(lede)
        markers = [int(x) for x in _CITATION.findall(body + " " + lede)]

    insufficient = bool(raw.get("insufficient_evidence"))
    prose = _WS.sub(" ", _CITATION.sub(" ", body)).strip()
    if len(prose) < min_body_chars(mode) or is_thin_scaffold_body(body):
        fb = _extractive_fallback(payload, mode=mode)
        if len(_WS.sub(" ", _CITATION.sub(" ", fb.get("body_md") or "")).strip()) > len(
            prose
        ):
            return fb
        insufficient = True

    used = []
    for x in raw.get("used_member_ids") or markers:
        try:
            mid = int(x)
        except (TypeError, ValueError):
            continue
        if mid in allowed and mid not in used:
            used.append(mid)

    return {
        "title": title or str(payload.get("working_title") or "Untitled"),
        "lede": lede or None,
        "body_md": body,
        "used_member_ids": used,
        "omitted_off_theme": list(
            raw.get("omitted_off_theme") or raw.get("coverage_notes") or []
        )[:12],
        "insufficient_evidence": insufficient,
        "gaps": list(raw.get("gaps") or [])[:12],
        "fallback": None,
    }


async def _call_compose_llm(
    payload: dict[str, Any],
    *,
    mode: ComposeMode = "draft",
) -> tuple[dict[str, Any] | None, str | None]:
    label = "publish" if mode == "publish" else "compose"
    prompt = (
        f"{_load_prompt(mode)}\n\n"
        f"## Package to {label}\n"
        f"```json\n{json.dumps(payload, default=str)[:140_000]}\n```\n"
    )
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STORYLINE_NARRATIVE_FINISH,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return _parse_json_object(result.text), getattr(result, "model", None)
    except Exception as e:
        logger.warning(
            "%s LLM failed package_id=%s: %s",
            label,
            payload.get("package_id"),
            e,
        )
        return None, None


def _merge_package_metadata(package_id: int, patch: dict[str, Any]) -> None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(patch), package_id),
            )
            conn.commit()


async def run_compose_pass(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    mode: ComposeMode = "draft",
    story_id: int | None = None,
) -> dict[str, Any]:
    if not is_enabled() and not force:
        return {
            "skipped": True,
            "reason": "EDITORIAL_COMPOSE_ENABLED=false",
            "package_id": package_id,
        }

    from services.editorial_package_service import (
        enrich_package_cite_provenance,
        get_package,
        seed_heuristic_editor_links,
    )
    from services.news_story_service import create_or_update_draft

    enrich_package_cite_provenance(package_id)
    seed_heuristic_editor_links(package_id, actor="editor_compose")
    pkg = get_package(package_id, include=True)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    status = str(pkg.get("status") or "")
    allowed_status = ("ready_for_editor", "in_editing", "published")
    if status not in allowed_status and not force:
        return {
            "skipped": True,
            "reason": f"status={status} (expected ready_for_editor|in_editing)",
            "package_id": package_id,
        }

    # Story already published but package row lagged — finish the status migration.
    if not dry_run:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM intelligence.news_stories
                    WHERE package_id = %s AND status = 'published'
                    ORDER BY published_at DESC NULLS LAST, id DESC
                    LIMIT 1
                    """,
                    (package_id,),
                )
                published_row = cur.fetchone()
        if published_row and status != "published":
            from services.editorial_package_service import update_package

            update_package(
                package_id,
                status="published",
                primary_modal="editor",
                actor="editor_compose",
                modal="editor",
                rationale="sync package status to published story",
            )
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_published",
                "package_id": package_id,
                "published": {"published": True, "story_id": int(published_row[0])},
            }

    active_members = [
        m
        for m in (pkg.get("members") or [])
        if (m.get("status") or "active") == "active"
    ]
    if (not active_members or not (pkg.get("domain_keys") or [])) and not dry_run:
        from services.editorial_package_service import close_package_thin

        close_package_thin(
            package_id,
            actor="editor_compose",
            rationale="no active members or empty domain_keys",
            reason="no_citeable_members",
            from_modal="editor",
        )
        return {
            "ok": False,
            "blocked": True,
            "block_reason": "no_citeable_members",
            "insufficient_evidence": True,
            "package_id": package_id,
        }

    if mode == "draft" and not force and not needs_compose(package_id) and not dry_run:
        return {
            "skipped": True,
            "reason": "draft_already_composed",
            "package_id": package_id,
        }

    payload = build_compose_payload(pkg, mode=mode)

    # Publish: Narrative packages should ship from the evidence brief when required.
    brief_block: dict[str, Any] | None = None
    if mode == "publish":
        from config.runtime import env_bool as _env_bool
        from services.package_evidence_brief_service import brief_passes_publish_gate

        dks = set(pkg.get("domain_keys") or [])
        narrative_pkg = bool(dks & {"politics", "finance", "legal"})
        require_brief = _env_bool("EVIDENCE_BRIEF_REQUIRED_FOR_PUBLISH", True) and narrative_pkg
        gate = brief_passes_publish_gate(package_id)
        if require_brief and not gate.get("ok"):
            return {
                "ok": False,
                "blocked": True,
                "block_reason": "evidence_brief_gate",
                "package_id": package_id,
                "brief_gate": gate,
                "error": "evidence_brief_incomplete",
            }
        if gate.get("ok") and payload.get("evidence_brief"):
            brief_block = payload["evidence_brief"]

    if env_bool("EDITORIAL_COMPOSE_SKIP_LLM", False):
        parsed, model = None, None
    else:
        parsed, model = await _call_compose_llm(payload, mode=mode)
    used_fallback = parsed is None
    validated = validate_compose_payload(parsed, payload=payload, mode=mode)
    if validated.get("fallback"):
        used_fallback = True

    body = str(validated.get("body_md") or "").strip()
    # Prefer a density-passing evidence brief as the manuscript spine.
    if mode == "publish" and brief_block and (brief_block.get("brief_md") or "").strip():
        brief_body = str(brief_block.get("brief_md") or "").strip()
        if len(brief_body) >= max(len(body), 800) or used_fallback:
            body = brief_body
            validated["body_md"] = body
            validated["from_evidence_brief"] = True
            if brief_block.get("lede") and not validated.get("lede"):
                validated["lede"] = brief_block.get("lede")
            if not validated.get("title"):
                validated["title"] = payload.get("working_title")

    from shared.stakes_gate import ensure_reader_sections, evaluate_stakes_gate

    body = ensure_reader_sections(body, payload)
    allowed_cite_ids = _citeable_active_ids(pkg, payload)
    body = scrub_unbound_citations(body, allowed_cite_ids)
    validated["body_md"] = body

    gate_members = []
    for m in payload.get("members") or []:
        gate_members.append(
            {
                "status": "active",
                "member_type": m.get("member_type"),
                "label": m.get("label"),
                "title": m.get("label"),
                "excerpt": m.get("excerpt"),
                "quote": m.get("excerpt"),
                "url": m.get("url"),
                "facts": m.get("facts") or [],
                "claims": m.get("claims") or [],
                "parties": m.get("parties") or [],
                "provenance": {
                    "label": m.get("label"),
                    "quote": m.get("excerpt"),
                    "url": m.get("url"),
                    "source_url": m.get("url"),
                    "actors": m.get("parties") or [],
                    "key_actors": m.get("parties") or [],
                    "holding": m.get("holding"),
                    "outcome": m.get("outcome"),
                    "summary": m.get("excerpt"),
                },
            }
        )
    gate_pkg = dict(pkg)
    if gate_members:
        gate_pkg["members"] = gate_members
    stakes = evaluate_stakes_gate(
        gate_pkg,
        body_md=body,
        require_sections=True,
    )
    if not stakes.get("ok") and not dry_run:
        from services.editorial_package_service import close_package_thin

        try:
            close_package_thin(
                package_id,
                actor="editor_compose",
                rationale="deterministic stakes gate failed",
                reason=str(stakes.get("reason") or "thin_no_stakes"),
                from_modal="editor",
            )
        except Exception as e:
            logger.warning("thin close after stakes fail: %s", e)
        return {
            "ok": False,
            "blocked": True,
            "block_reason": "thin_no_stakes",
            "package_id": package_id,
            "stakes": stakes,
            "error": "thin_no_stakes",
        }

    prompt_version = PROMPT_VERSION_PUBLISH if mode == "publish" else PROMPT_VERSION

    # Publish coverage backfill: if the model omitted linked excerpt sources,
    # append an evidence section so the final report still covers the graph.
    if mode == "publish" and body and not validated.get("insufficient_evidence"):
        cited = {
            int(x) for x in _CITATION.findall(body + " " + str(validated.get("lede") or ""))
        }
        linked_with_excerpt = [
            m
            for m in (payload.get("members") or [])
            if m.get("linked") and m.get("excerpt") and int(m["member_row_id"]) not in cited
        ]
        # Also cover unlinked members that were in the publish payload and unused
        unused_payload = [
            m
            for m in (payload.get("members") or [])
            if m.get("excerpt") and int(m["member_row_id"]) not in cited
        ]
        fill_rows = linked_with_excerpt or (
            unused_payload
            if len(cited) < max(3, int(0.4 * max(1, len(payload.get("members") or []))))
            else []
        )
        if fill_rows:
            extra = ["", "## Additional linked evidence"]
            used = list(validated.get("used_member_ids") or [])
            seen = set(used)
            for m in fill_rows[:20]:
                mid = int(m["member_row_id"])
                label = _clean_text(m.get("label") or "", limit=120)
                excerpt = _clean_text(m.get("excerpt") or "", limit=420)
                if not excerpt:
                    continue
                line = f"**{label}.** {excerpt}" if label else excerpt
                extra.append(f"{line} [@m{mid}]")
                if mid not in seen:
                    used.append(mid)
                    seen.add(mid)
            if len(extra) > 2:
                body = (body.rstrip() + "\n" + "\n\n".join(extra) + "\n").strip()
                body = scrub_unbound_citations(body, allowed_cite_ids)
                validated["body_md"] = body
                validated["used_member_ids"] = used
                validated["coverage_backfill"] = len(extra) - 2

    prose = _WS.sub(" ", _CITATION.sub(" ", body)).strip()
    min_needed = min_body_chars(mode)
    if env_bool("EDITORIAL_COMPOSE_SKIP_LLM", False) and stakes.get("ok"):
        min_needed = min(min_needed, max(200, env_int("EDITORIAL_COMPOSE_MIN_BODY_CHARS", 280)))
    if body and len(prose) >= min_needed:
        validated["insufficient_evidence"] = False

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "mode": mode,
            "package_id": package_id,
            "model": model,
            "prompt_version": prompt_version,
            "used_fallback": used_fallback,
            "title": validated.get("title"),
            "lede": validated.get("lede"),
            "body_preview": body[:600],
            "body_len": len(body),
            "used_member_ids": validated.get("used_member_ids"),
            "insufficient_evidence": validated.get("insufficient_evidence"),
            "member_payload_count": len(payload.get("members") or []),
            "linked_member_count": payload.get("linked_member_count"),
        }

    if not body or validated.get("insufficient_evidence"):
        _merge_package_metadata(
            package_id,
            {
                "last_compose_at": datetime.now(timezone.utc).isoformat(),
                "last_compose_mode": mode,
                "last_compose_insufficient": True,
                "last_compose_gaps": validated.get("gaps") or [],
            },
        )
        return {
            "ok": False,
            "mode": mode,
            "package_id": package_id,
            "insufficient_evidence": True,
            "gaps": validated.get("gaps"),
            "used_fallback": used_fallback,
            "model": model,
            "prompt_version": prompt_version,
        }

    draft = create_or_update_draft(
        package_id,
        title=str(validated.get("title") or pkg.get("working_title") or "Untitled"),
        lede=validated.get("lede"),
        body_md=body,
        presentation_kind=pkg.get("presentation_kind"),
        created_by="editor_publish" if mode == "publish" else "editor_compose",
        actor="editor_publish" if mode == "publish" else "editor_compose",
        story_id=story_id,
        advance_status=False,
    )
    _merge_package_metadata(
        package_id,
        {
            "last_compose_at": datetime.now(timezone.utc).isoformat(),
            "last_compose_mode": mode,
            "last_compose_insufficient": False,
            "last_compose_model": model,
            "last_compose_prompt_version": prompt_version,
            "last_compose_used_fallback": used_fallback,
            "last_compose_member_ids": validated.get("used_member_ids") or [],
            "last_compose_linked_member_count": payload.get("linked_member_count"),
        },
    )
    published: dict[str, Any] | None = None
    story_row = draft.get("story") or {}
    cite_ok = bool((draft.get("citation_check") or {}).get("ok"))
    auto_pub = env_bool("NEWS_STORY_AUTO_PUBLISH_ON_GATE_PASS", True)
    sid = story_row.get("id")
    if auto_pub and cite_ok and sid and str(story_row.get("status") or "") != "published":
        try:
            from services.news_story_service import publish_story

            published = publish_story(int(sid), actor="editor_compose", assemble=False)
        except Exception as e:
            logger.warning("auto-publish after compose failed package=%s: %s", package_id, e)
            published = {"published": False, "error": str(e)}
    elif auto_pub and sid and not cite_ok:
        logger.info(
            "auto-publish skipped package=%s cite_ok=false refused=%s",
            package_id,
            (draft.get("citation_check") or {}).get("refused"),
        )

    return {
        "ok": True,
        "mode": mode,
        "package_id": package_id,
        "model": model,
        "prompt_version": prompt_version,
        "used_fallback": used_fallback,
        "story": (published.get("story") if published and published.get("story") else story_row),
        "citation_check": draft.get("citation_check"),
        "published": published,
        "used_member_ids": validated.get("used_member_ids"),
        "body_len": len(body),
        "omitted_off_theme": validated.get("omitted_off_theme"),
        "linked_member_count": payload.get("linked_member_count"),
        "member_payload_count": len(payload.get("members") or []),
    }


def run_compose_pass_sync(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
    mode: ComposeMode = "draft",
    story_id: int | None = None,
) -> dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    run_compose_pass(
                        package_id,
                        dry_run=dry_run,
                        force=force,
                        mode=mode,
                        story_id=story_id,
                    )
                )
            ).result()
    return asyncio.run(
        run_compose_pass(
            package_id,
            dry_run=dry_run,
            force=force,
            mode=mode,
            story_id=story_id,
        )
    )


def run_compose_batch(*, limit: int = 5, force: bool = False) -> dict[str, Any]:
    """Drain ready_for_editor packages whose drafts are missing or thin scaffolds."""
    if not is_enabled() and not force:
        return {"processed": 0, "skipped": True, "reason": "disabled"}

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id
                FROM intelligence.editorial_packages p
                LEFT JOIN LATERAL (
                    SELECT s.body_md, s.status AS story_status
                    FROM intelligence.news_stories s
                    WHERE s.package_id = p.id
                    ORDER BY CASE WHEN s.status = 'published' THEN 0
                                  WHEN s.status = 'draft' THEN 1
                                  ELSE 2 END, s.id DESC
                    LIMIT 1
                ) st ON TRUE
                WHERE p.status IN ('ready_for_editor', 'in_editing')
                  AND (
                    st.body_md IS NULL
                    OR st.body_md = ''
                    OR st.body_md ILIKE '%%Source anchors%%'
                    OR length(regexp_replace(st.body_md, '\\[\\@m[0-9]+\\]', '', 'g')) < 120
                  )
                ORDER BY p.updated_at DESC NULLS LAST, p.id DESC
                LIMIT %s
                """,
                (max(1, min(limit, 20)),),
            )
            ids = [int(r[0]) for r in cur.fetchall()]

    results = []
    for pid in ids:
        try:
            results.append(run_compose_pass_sync(pid, force=force))
        except Exception as e:
            logger.warning("compose batch package %s failed: %s", pid, e)
            results.append({"ok": False, "package_id": pid, "error": str(e)})

    return {
        "processed": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "results": results,
    }
