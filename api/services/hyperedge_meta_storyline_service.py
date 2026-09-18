"""
Hyperedge meta-storylines (Phase 6 C7).

Render/list hyperedge graph proposals as umbrella containers with member
event timelines (extends existing graph_connection_proposals hyperedges).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def list_hyperedge_meta_storylines(
    *,
    domain_key: str | None = None,
    status: str = "pending",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """List hyperedge proposals with member storyline ids + event timeline."""
    from shared.database.connection import get_ui_db_connection_context
    from shared.domain_registry import resolve_domain_schema
    from psycopg2.extras import RealDictCursor

    clauses = ["proposal_kind = 'hyperedge'"]
    params: list[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if domain_key:
        clauses.append("domain_key = %s")
        params.append(domain_key)
    params.append(max(1, min(int(limit), 100)))
    sql = f"""
        SELECT id, created_at, domain_key, confidence, status, inference_stage,
               endpoints, evidence, subject_summary
        FROM intelligence.graph_connection_proposals
        WHERE {' AND '.join(clauses)}
        ORDER BY COALESCE(confidence, 0) DESC, id DESC
        LIMIT %s
    """
    out: list[dict[str, Any]] = []
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in (cur.fetchall() or [])]
                for row in rows:
                    ep = row.get("endpoints") if isinstance(row.get("endpoints"), dict) else {}
                    ids = [int(x) for x in (ep.get("storyline_ids") or []) if str(x).isdigit() or isinstance(x, int)]
                    dk = row.get("domain_key") or domain_key or "politics"
                    timeline = _member_event_timeline(cur, dk, ids, limit=40)
                    titles = _storyline_titles(cur, dk, ids)
                    out.append(
                        {
                            "proposal_id": int(row["id"]),
                            "domain_key": dk,
                            "confidence": float(row.get("confidence") or 0),
                            "status": row.get("status"),
                            "inference_stage": row.get("inference_stage"),
                            "subject_summary": row.get("subject_summary"),
                            "umbrella_title": row.get("subject_summary")
                            or f"Hyperedge ({len(ids)} storylines)",
                            "member_storyline_ids": ids,
                            "member_titles": titles,
                            "event_timeline": timeline,
                            "evidence": row.get("evidence") or {},
                        }
                    )
    except Exception as e:
        logger.warning("list_hyperedge_meta_storylines: %s", e)
    return out


def get_hyperedge_meta_storyline(proposal_id: int) -> dict[str, Any] | None:
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, domain_key, confidence, status, inference_stage,
                           endpoints, evidence, subject_summary
                    FROM intelligence.graph_connection_proposals
                    WHERE id = %s AND proposal_kind = 'hyperedge'
                    """,
                    (int(proposal_id),),
                )
                row = cur.fetchone()
                if not row:
                    return None
                row = dict(row)
                ep = row.get("endpoints") if isinstance(row.get("endpoints"), dict) else {}
                ids = [
                    int(x)
                    for x in (ep.get("storyline_ids") or [])
                    if str(x).isdigit() or isinstance(x, int)
                ]
                dk = row.get("domain_key") or "politics"
                return {
                    "proposal_id": int(row["id"]),
                    "domain_key": dk,
                    "confidence": float(row.get("confidence") or 0),
                    "status": row.get("status"),
                    "inference_stage": row.get("inference_stage"),
                    "subject_summary": row.get("subject_summary"),
                    "umbrella_title": row.get("subject_summary")
                    or f"Hyperedge ({len(ids)} storylines)",
                    "member_storyline_ids": ids,
                    "member_titles": _storyline_titles(cur, dk, ids),
                    "event_timeline": _member_event_timeline(cur, dk, ids, limit=60),
                    "evidence": row.get("evidence") or {},
                }
    except Exception as e:
        logger.warning("get_hyperedge_meta_storyline: %s", e)
        return None


def _storyline_titles(cur, domain_key: str, ids: list[int]) -> dict[str, str]:
    if not ids:
        return {}
    try:
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(domain_key)
        cur.execute(
            f"SELECT id, title FROM {schema}.storylines WHERE id = ANY(%s)",
            (ids,),
        )
        return {str(r[0]): (r[1] or "") for r in (cur.fetchall() or [])}
    except Exception:
        return {}


def _member_event_timeline(
    cur,
    domain_key: str,
    storyline_ids: list[int],
    *,
    limit: int = 40,
) -> list[dict[str, Any]]:
    if not storyline_ids:
        return []
    try:
        cur.execute(
            """
            SELECT id, storyline_id, title, event_type,
                   COALESCE(actual_event_date, created_at) AS ts
            FROM public.chronological_events
            WHERE storyline_id = ANY(%s)
            ORDER BY COALESCE(actual_event_date, created_at) ASC NULLS LAST
            LIMIT %s
            """,
            (storyline_ids, limit),
        )
        rows = cur.fetchall() or []
        # RealDictCursor vs tuple
        out = []
        for r in rows:
            if isinstance(r, dict):
                out.append(
                    {
                        "event_id": int(r["id"]),
                        "storyline_id": r.get("storyline_id"),
                        "title": r.get("title"),
                        "event_type": r.get("event_type"),
                        "ts": r.get("ts").isoformat() if r.get("ts") else None,
                    }
                )
            else:
                out.append(
                    {
                        "event_id": int(r[0]),
                        "storyline_id": r[1],
                        "title": r[2],
                        "event_type": r[3],
                        "ts": r[4].isoformat() if r[4] else None,
                    }
                )
        return out
    except Exception as e:
        logger.debug("_member_event_timeline: %s", e)
        return []
