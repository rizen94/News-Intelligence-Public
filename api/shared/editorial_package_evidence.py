"""
Hydrate editorial package member provenance from source rows (v11).

Chronological events often arrive with label/URL only. Attach-time hydration
fills description, outcome, parties, and quotes so Reduction and Compose see
substance before publish.
"""

from __future__ import annotations

import json
import logging
import re
from html import unescape
from typing import Any

from shared.editorial_package_theme import parse_case_caption_parties

logger = logging.getLogger(__name__)

_HTML_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(val: Any, *, limit: int = 900) -> str:
    if val is None:
        return ""
    if isinstance(val, dict):
        val = val.get("quote") or val.get("text") or val.get("summary") or ""
    text = unescape(_HTML_TAG.sub(" ", str(val)))
    text = re.sub(r"</?[a-zA-Z][^>\s]*", " ", text)
    text = _WS.sub(" ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def _actor_names(raw: Any) -> list[str]:
    names: list[str] = []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            text = _clean(raw, limit=240)
            return [text] if text else []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                name = _clean(item.get("name") or item.get("label") or "", limit=120)
                role = _clean(item.get("role") or "", limit=80)
                # Prefer litigant roles over "Judiciary" / justice names as parties.
                role_l = role.lower()
                if role_l in (
                    "judiciary",
                    "supreme court justice",
                    "justice",
                    "judges",
                    "judge",
                    "court",
                ):
                    continue
                if name and role:
                    names.append(f"{name} ({role})")
                elif name:
                    names.append(name)
            else:
                name = _clean(item, limit=120)
                if name:
                    names.append(name)
    return names[:12]


def hydrate_member_provenance(
    *,
    member_type: str,
    member_id: int,
    domain_key: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return provenance enriched from CE / article / claim source rows."""
    from shared.database.connection import get_ui_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    prov = dict(provenance or {})
    mt = (member_type or "").strip()
    mid = int(member_id)

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                if mt == "chronological_event":
                    cur.execute(
                        """
                        SELECT title, description, outcome, key_actors, entities,
                               COALESCE(actual_event_date, event_date) AS event_date,
                               left(COALESCE(source_text, ''), 1200) AS source_text
                        FROM public.chronological_events
                        WHERE id = %s
                        """,
                        (mid,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return prov
                    cols = [d[0] for d in cur.description]
                    ce = dict(zip(cols, row))
                    title = _clean(ce.get("title") or "", limit=200)
                    description = _clean(ce.get("description") or "", limit=900)
                    outcome = _clean(ce.get("outcome") or "", limit=600)
                    source_text = _clean(ce.get("source_text") or "", limit=900)
                    caption_parties = parse_case_caption_parties(title)
                    actors = _actor_names(ce.get("key_actors")) or _actor_names(
                        ce.get("entities")
                    )
                    # Caption parties beat justice/court actors for case briefs.
                    parties = caption_parties or actors
                    if title and not prov.get("label"):
                        prov["label"] = title
                    elif title:
                        prov["label"] = title
                    if description and (
                        not prov.get("quote")
                        or len(str(prov.get("quote") or "")) < 80
                        or str(prov.get("quote") or "").strip()
                        == str(prov.get("label") or "").strip()
                    ):
                        prov["quote"] = description
                    elif source_text and not prov.get("quote"):
                        prov["quote"] = source_text
                    if outcome:
                        prov["outcome"] = outcome
                        prov["holding"] = outcome
                    if parties:
                        prov["parties"] = parties
                        prov["key_actors"] = parties
                    if ce.get("event_date"):
                        prov["event_date"] = str(ce.get("event_date"))
                    if description:
                        prov["summary"] = description
                elif mt == "article":
                    dk = (domain_key or "").strip()
                    schema = resolve_domain_schema(dk) if dk else None
                    if schema:
                        cur.execute(
                            f"""
                            SELECT title, summary, content, url
                            FROM {schema}.articles
                            WHERE id = %s
                            """,
                            (mid,),
                        )
                        row = cur.fetchone()
                        if row:
                            title = _clean(row[0] or "", limit=200)
                            body = _clean(row[2] or row[1] or "", limit=1600)
                            url = _clean(row[3] or "", limit=240)
                            if title and not prov.get("label"):
                                prov["label"] = title
                            if body and (
                                not prov.get("quote")
                                or len(str(prov.get("quote") or "")) < 200
                            ):
                                prov["quote"] = body
                            if url and not (prov.get("source_url") or prov.get("url")):
                                prov["source_url"] = url
                            caption_parties = parse_case_caption_parties(
                                f"{title} {body[:400]}"
                            )
                            if caption_parties and not prov.get("parties"):
                                prov["parties"] = caption_parties
                elif mt in (
                    "extracted_claim",
                    "versioned_fact",
                    "claim_evidence_appraisal",
                    "hypothesis",
                ):
                    cur.execute(
                        """
                        SELECT subject_text, predicate_text, object_text
                        FROM intelligence.extracted_claims
                        WHERE id = %s
                        """,
                        (mid,),
                    )
                    row = cur.fetchone()
                    if row:
                        subj = _clean(row[0] or "", limit=200)
                        pred = _clean(row[1] or "", limit=200)
                        obj = _clean(row[2] or "", limit=400)
                        triple = " ".join(x for x in (subj, pred, obj) if x).strip()
                        if triple and (
                            not prov.get("quote")
                            or len(str(prov.get("quote") or "")) < 40
                        ):
                            prov["quote"] = triple
                        if subj and not prov.get("parties"):
                            prov["parties"] = [subj]
                        if not prov.get("label") and triple:
                            prov["label"] = triple[:180]
    except Exception as e:
        logger.debug(
            "hydrate_member_provenance failed type=%s id=%s: %s", mt, mid, e
        )
    return prov
