"""Discovery findings → editorial LLM candidate rows (research + narrative)."""

from __future__ import annotations

import logging
from typing import Any, Callable

from shared.database.connection import get_db_connection_context
from shared.editorial_package_vocab import (
    NARRATIVE_MEMBER_TYPES,
    RESEARCH_MEMBER_TYPES,
    provenance_has_citeable_source,
)
from shared.post_processing_modals import allowed_domains_for_modal

logger = logging.getLogger(__name__)

CandidateKeyFn = Callable[[str, int, str | None], str]


def collect_discovery_candidates(
    package: dict[str, Any],
    *,
    limit: int,
    candidate_key_fn: CandidateKeyFn,
    target_modal: str = "research",
) -> list[dict[str, Any]]:
    """Map connection_findings on this package to attachable LLM candidates."""
    meta = package.get("metadata") or {}
    if isinstance(meta, str):
        import json

        try:
            meta = json.loads(meta)
        except json.JSONDecodeError:
            meta = {}
    pkg_id = package.get("id")
    finding_ids = list(meta.get("discovery_finding_ids") or [])
    if not finding_ids and not pkg_id:
        return []

    modal = (target_modal or "research").strip().lower()
    member_family = "narrative" if modal == "narrative" else "research"
    allowed = (
        NARRATIVE_MEMBER_TYPES if modal == "narrative" else RESEARCH_MEMBER_TYPES
    )

    domain_keys = list(package.get("domain_keys") or [])
    fallback_dk = (
        str(domain_keys[0]).strip()
        if domain_keys
        else "politics"
    )
    allow = set(allowed_domains_for_modal(modal) or [])
    if allow and fallback_dk not in allow:
        fallback_dk = next(iter(allow), fallback_dk)

    out: list[dict[str, Any]] = []
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                if finding_ids:
                    cur.execute(
                        """
                        SELECT id, finding_type, title, summary, confidence, domain_keys,
                               left_kind, left_id, right_kind, right_id, evidence
                        FROM intelligence.connection_findings
                        WHERE id = ANY(%s)
                        """,
                        (finding_ids,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, finding_type, title, summary, confidence, domain_keys,
                               left_kind, left_id, right_kind, right_id, evidence
                        FROM intelligence.connection_findings
                        WHERE editorial_package_id = %s
                          AND status IN ('queued_research', 'researching')
                        ORDER BY confidence DESC NULLS LAST
                        LIMIT %s
                        """,
                        (int(pkg_id), int(limit)),
                    )
                rows = cur.fetchall() or []

                for r in rows:
                    fid = int(r[0])
                    ftype = str(r[1] or "")
                    title = str(r[2] or "")
                    summary = str(r[3] or "")
                    conf = float(r[4]) if r[4] is not None else 0.6
                    domains = list(r[5] or []) or domain_keys or [fallback_dk]
                    dk = str(domains[0] or fallback_dk).strip() or fallback_dk
                    if allow and dk not in allow:
                        dk = fallback_dk
                    evidence = r[10] if isinstance(r[10], dict) else {}

                    ctx_ids = [int(x) for x in (evidence.get("context_ids") or [])[:8]]
                    for cid in ctx_ids:
                        cur.execute(
                            """
                            SELECT id, domain_key, content
                            FROM intelligence.contexts WHERE id = %s
                            """,
                            (cid,),
                        )
                        crow = cur.fetchone()
                        if not crow:
                            continue
                        ctx_dk = str(crow[1] or dk).strip() or dk
                        if allow and ctx_dk not in allow:
                            ctx_dk = fallback_dk if fallback_dk in allow else dk
                        quote = str(crow[2] or title or summary)[:500]
                        mt = "context"
                        if mt not in allowed:
                            continue
                        key = candidate_key_fn(mt, int(crow[0]), ctx_dk)
                        out.append(
                            {
                                "candidate_key": key,
                                "member_type": mt,
                                "member_id": int(crow[0]),
                                "member_family": member_family,
                                "domain_key": ctx_dk,
                                "role": "supporting",
                                "label": (title or quote)[:120],
                                "provenance": {
                                    "quote": quote or None,
                                    "context_id": int(crow[0]),
                                    "discovery_finding_id": fid,
                                    "discovery_type": ftype,
                                    "confidence": conf,
                                },
                                "source": "discovery",
                            }
                        )

                    ev_ids: list[int] = []
                    if r[7] is not None:
                        ev_ids.append(int(r[7]))
                    if r[9] is not None:
                        ev_ids.append(int(r[9]))
                    ev_ids.extend(int(x) for x in (evidence.get("event_ids") or [])[:6])
                    seen_ev: set[int] = set()
                    for eid in ev_ids:
                        if eid in seen_ev:
                            continue
                        seen_ev.add(eid)
                        cur.execute(
                            """
                            SELECT id, title, source_text, source_article_id
                            FROM public.chronological_events WHERE id = %s
                            """,
                            (eid,),
                        )
                        erow = cur.fetchone()
                        if not erow:
                            continue
                        aid = erow[3]
                        url = ""
                        schema = dk.replace("-", "_")
                        if aid:
                            try:
                                cur.execute(
                                    f"SELECT url, title FROM {schema}.articles WHERE id = %s",
                                    (int(aid),),
                                )
                                arow = cur.fetchone()
                                if arow:
                                    url = str(arow[0] or "").strip()
                                    if not title:
                                        title = str(arow[1] or erow[1] or "")
                            except Exception:
                                pass
                        quote = str(erow[2] or erow[1] or title)[:500]
                        if modal == "narrative" and "chronological_event" in allowed:
                            ev_dk = dk if (not allow or dk in allow) else fallback_dk
                            key = candidate_key_fn("chronological_event", int(eid), ev_dk)
                            out.append(
                                {
                                    "candidate_key": key,
                                    "member_type": "chronological_event",
                                    "member_id": int(eid),
                                    "member_family": "narrative",
                                    "domain_key": ev_dk,
                                    "role": "anchor_event",
                                    "label": (title or quote)[:120],
                                    "provenance": {
                                        "quote": quote or None,
                                        "source_url": url or None,
                                        "chronological_event_id": eid,
                                        "discovery_finding_id": fid,
                                        "discovery_type": ftype,
                                    },
                                    "source": "discovery",
                                }
                            )
                        if aid and "article" in allowed:
                            art_dk = dk if (not allow or dk in allow) else fallback_dk
                            key = candidate_key_fn("article", int(aid), art_dk)
                            out.append(
                                {
                                    "candidate_key": key,
                                    "member_type": "article",
                                    "member_id": int(aid),
                                    "member_family": member_family,
                                    "domain_key": art_dk,
                                    "role": "supporting",
                                    "label": (title or quote)[:120],
                                    "provenance": {
                                        "quote": quote or None,
                                        "source_url": url or None,
                                        "article_id": int(aid),
                                        "chronological_event_id": eid,
                                        "discovery_finding_id": fid,
                                        "discovery_type": ftype,
                                    },
                                    "source": "discovery",
                                }
                            )
    except Exception as exc:
        logger.debug("collect_discovery_candidates: %s", exc)
        return []

    return out[:limit]


def tag_discovery_rejection(
    rejected: list[str],
    candidate: dict[str, Any],
    key: str,
    reason: str,
) -> None:
    """Prefix rejection with discovery finding id when source is discovery."""
    if candidate.get("source") != "discovery":
        rejected.append(f"{reason}:{key}")
        return
    fid = (candidate.get("provenance") or {}).get("discovery_finding_id")
    rejected.append(f"discovery:{fid}:{reason}:{key}")


def discovery_reject_if_not_citeable(
    candidate: dict[str, Any],
    key: str,
    rejected: list[str],
) -> bool:
    """Return True if candidate passes citeable check (research modal)."""
    prov = candidate.get("provenance") or {}
    if provenance_has_citeable_source(prov):
        return True
    tag_discovery_rejection(rejected, candidate, key, "not_citeable")
    return False
