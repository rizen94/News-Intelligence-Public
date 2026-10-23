"""
Source disagreement helper (Phase 6 C4).

Summarizes claim / event title variants per canonical event cluster.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    t = re.sub(r"[^\w\s]", "", t)
    return t[:240]


def summarize_claim_variants_for_event(
    event_id: int,
    *,
    limit: int = 40,
) -> dict[str, Any]:
    """
    For a chronological event (or its cluster root), collect variant titles /
    descriptions and group near-duplicates.
    """
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, COALESCE(event_cluster_id, COALESCE(canonical_event_id, id)) AS root_id,
                           title, description, source_count,
                           COALESCE(actual_event_date, created_at) AS event_ts
                    FROM public.chronological_events
                    WHERE id = %s
                       OR event_cluster_id = %s
                       OR canonical_event_id = %s
                       OR id = (
                            SELECT COALESCE(event_cluster_id, canonical_event_id, id)
                            FROM public.chronological_events WHERE id = %s
                       )
                    ORDER BY COALESCE(actual_event_date, created_at) ASC NULLS LAST
                    LIMIT %s
                    """,
                    (event_id, event_id, event_id, event_id, limit),
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.warning("summarize_claim_variants_for_event: %s", e)
        return {"event_id": event_id, "variants": [], "error": str(e)[:200]}

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = _norm(r.get("title") or "") or f"id:{r['id']}"
        buckets[key].append(r)

    variants: list[dict[str, Any]] = []
    for key, members in buckets.items():
        titles = sorted({(m.get("title") or "").strip() for m in members if m.get("title")})
        variants.append(
            {
                "normalized_key": key[:80],
                "count": len(members),
                "titles": titles[:8],
                "member_event_ids": [int(m["id"]) for m in members],
                "disagreement": len(titles) > 1,
            }
        )
    variants.sort(key=lambda v: (-v["count"], v["normalized_key"]))
    disagreeing = [v for v in variants if v["disagreement"] or len(variants) > 1]
    return {
        "event_id": event_id,
        "member_count": len(rows),
        "variant_count": len(variants),
        "has_disagreement": len(disagreeing) > 1 or any(v["disagreement"] for v in variants),
        "variants": variants[:20],
        "summary": (
            f"{len(variants)} title variant(s) across {len(rows)} clustered event row(s)"
            if rows
            else "no members"
        ),
    }
