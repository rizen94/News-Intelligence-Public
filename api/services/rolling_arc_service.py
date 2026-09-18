"""Phase B: rolling 12-month arcs + temporal planner + latent embedding proposals."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_THEMES: dict[str, list[tuple[str, str]]] = {
    "finance": [
        ("markets_macro", "Markets & macro"),
        ("commodities_energy", "Commodities & energy"),
    ],
    "politics": [
        ("governance_policy", "Governance & policy"),
        ("geopolitics_conflict", "Geopolitics & conflict"),
    ],
}


def list_rolling_arcs(
    *,
    domain_key: str | None = None,
    status: str = "active",
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses = ["status = %s"]
    params: list[Any] = [status]
    if domain_key:
        clauses.append("domain_key = %s")
        params.append(domain_key)
    params.append(max(1, min(int(limit), 200)))
    sql = f"""
        SELECT id, created_at, material_updated_at, domain_key, theme_key, title,
               arc_type, window_days, strength, summary, chapters, storyline_ids,
               chronological_event_ids, status, metadata
        FROM intelligence.rolling_arcs
        WHERE {' AND '.join(clauses)}
        ORDER BY material_updated_at DESC
        LIMIT %s
    """
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("list_rolling_arcs: %s", e)
        return []


def get_rolling_arc(arc_id: int) -> dict[str, Any] | None:
    rows = list_rolling_arcs(limit=500)
    for r in rows:
        if int(r.get("id") or 0) == int(arc_id):
            return r
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM intelligence.rolling_arcs WHERE id = %s",
                    (int(arc_id),),
                )
                row = cur.fetchone()
                return dict(row) if row else None
    except Exception as e:
        logger.debug("get_rolling_arc: %s", e)
        return None


def _schema_for_domain(domain_key: str) -> str:
    try:
        from shared.domain_registry import resolve_domain_schema

        return resolve_domain_schema(domain_key)
    except Exception:
        return domain_key.replace("-", "_")


def _fetch_window_atoms(domain_key: str, window_days: int = 365) -> dict[str, Any]:
    schema = _schema_for_domain(domain_key)
    storylines: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT id, title, COALESCE(material_updated_at, updated_at, created_at) AS ts
                    FROM {schema}.storylines
                    WHERE COALESCE(material_updated_at, updated_at, created_at)
                          >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY ts DESC
                    LIMIT 80
                    """,
                    (window_days,),
                )
                storylines = [dict(r) for r in (cur.fetchall() or [])]
                cur.execute(
                    """
                    SELECT ce.id, COALESCE(ce.title, '') AS title,
                           COALESCE(ce.actual_event_date, ce.created_at) AS ts
                    FROM public.chronological_events ce
                    WHERE COALESCE(ce.actual_event_date, ce.created_at)
                          >= NOW() - (%s * INTERVAL '1 day')
                      AND (
                        ce.storyline_id IN (
                          SELECT s.id FROM {schema}.storylines s
                          WHERE COALESCE(s.material_updated_at, s.updated_at, s.created_at)
                                >= NOW() - (%s * INTERVAL '1 day')
                          LIMIT 200
                        )
                        OR ce.storyline_id IS NULL
                      )
                    ORDER BY ts DESC
                    LIMIT 120
                    """.format(schema=schema),
                    (window_days, window_days),
                )
                events = [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("_fetch_window_atoms %s: %s", domain_key, e)
    return {"storylines": storylines, "events": events}


def _chapterize(atoms: dict[str, Any], window_days: int = 365) -> list[dict[str, Any]]:
    """Bucket atoms into ~quarter chapters over the rolling window."""
    chapters: list[dict[str, Any]] = []
    bucket_days = max(30, window_days // 4)
    now = datetime.now(timezone.utc)
    for i in range(4):
        end_offset = i * bucket_days
        start_offset = (i + 1) * bucket_days
        label = f"T-{start_offset}d→T-{end_offset}d"
        chapter_sl: list[int] = []
        chapter_ev: list[int] = []
        for s in atoms.get("storylines") or []:
            ts = s.get("ts")
            if not ts:
                continue
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
            age = (now - ts).total_seconds() / 86400.0
            if end_offset <= age < start_offset:
                chapter_sl.append(int(s["id"]))
        for e in atoms.get("events") or []:
            ts = e.get("ts")
            if not ts:
                continue
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
            age = (now - ts).total_seconds() / 86400.0
            if end_offset <= age < start_offset:
                chapter_ev.append(int(e["id"]))
        chapters.append(
            {
                "label": label,
                "storyline_ids": chapter_sl[:40],
                "chronological_event_ids": chapter_ev[:60],
            }
        )
    return list(reversed(chapters))


def refresh_rolling_arc(
    domain_key: str,
    theme_key: str,
    title: str,
    *,
    window_days: int = 365,
) -> int | None:
    atoms = _fetch_window_atoms(domain_key, window_days)
    chapters = _chapterize(atoms, window_days)
    sl_ids = [int(s["id"]) for s in atoms.get("storylines") or []]
    ev_ids = [int(e["id"]) for e in atoms.get("events") or []]
    strength = min(1.0, (len(sl_ids) + len(ev_ids) * 0.5) / 50.0)
    summary = (
        f"Rolling {window_days}d arc for {domain_key}/{theme_key}: "
        f"{len(sl_ids)} storylines, {len(ev_ids)} timeline atoms."
    )
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.rolling_arcs (
                        domain_key, theme_key, title, arc_type, window_days,
                        strength, summary, chapters, storyline_ids,
                        chronological_event_ids, status, material_updated_at
                    ) VALUES (
                        %s, %s, %s, 'rolling_12m', %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s::jsonb, 'active', NOW()
                    )
                    ON CONFLICT (domain_key, theme_key, arc_type) DO UPDATE SET
                        title = EXCLUDED.title,
                        window_days = EXCLUDED.window_days,
                        strength = EXCLUDED.strength,
                        summary = EXCLUDED.summary,
                        chapters = EXCLUDED.chapters,
                        storyline_ids = EXCLUDED.storyline_ids,
                        chronological_event_ids = EXCLUDED.chronological_event_ids,
                        material_updated_at = NOW(),
                        status = 'active'
                    RETURNING id
                    """,
                    (
                        domain_key,
                        theme_key,
                        title,
                        window_days,
                        strength,
                        summary,
                        json.dumps(chapters),
                        json.dumps(sl_ids[:80]),
                        json.dumps(ev_ids[:120]),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning("refresh_rolling_arc failed: %s", e)
        return None


def refresh_default_rolling_arcs() -> dict[str, Any]:
    """Nightly planner entry: ensure finance + politics rolling arcs exist."""
    refreshed: list[int] = []
    for domain, themes in _DEFAULT_THEMES.items():
        for theme_key, title in themes:
            aid = refresh_rolling_arc(domain, theme_key, title)
            if aid:
                refreshed.append(aid)
    latent = propose_latent_co_arc_links(limit=20)
    return {"refreshed_arc_ids": refreshed, "latent_proposals": latent}


def propose_latent_co_arc_links(*, limit: int = 20) -> int:
    """Enqueue latent co-arc associate proposals into graph_connection_proposals."""
    written = 0
    try:
        from shared.database.connection import get_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, domain_key, theme_key, title
                    FROM intelligence.rolling_arcs
                    WHERE status = 'active'
                    ORDER BY material_updated_at DESC
                    LIMIT 10
                    """
                )
                arcs = [dict(r) for r in (cur.fetchall() or [])]
                if len(arcs) < 2:
                    return 0
                for i in range(min(len(arcs) - 1, limit)):
                    a, b = arcs[i], arcs[i + 1]
                    if a.get("domain_key") != b.get("domain_key"):
                        continue
                    ids = sorted([int(a["id"]), int(b["id"])])
                    dedupe = f"latent_co_arc:{a['domain_key']}:{ids[0]}:{ids[1]}"
                    endpoints = {
                        "rolling_arc_ids": ids,
                        "theme_keys": [a.get("theme_key"), b.get("theme_key")],
                    }
                    try:
                        cur.execute(
                            """
                            INSERT INTO intelligence.graph_connection_proposals (
                                status, proposal_kind, domain_key, confidence,
                                source, subject_summary, endpoints, evidence, dedupe_key
                            ) VALUES (
                                'pending', 'associate', %s, 0.35,
                                'rolling_arc_latent', %s, %s::jsonb, %s::jsonb, %s
                            )
                            ON CONFLICT (dedupe_key) DO NOTHING
                            """,
                            (
                                a["domain_key"],
                                f"Latent co-arc: {a.get('theme_key')} ↔ {b.get('theme_key')}",
                                json.dumps(endpoints),
                                json.dumps({"method": "rolling_arc_adjacency"}),
                                dedupe,
                            ),
                        )
                        if cur.rowcount:
                            written += 1
                    except Exception as ie:
                        logger.debug("latent proposal insert skip: %s", ie)
            conn.commit()
    except Exception as e:
        logger.debug("propose_latent_co_arc_links: %s", e)
    return written
