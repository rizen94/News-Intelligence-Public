"""
Arc analogue queries — adapt context-centric pattern/correlation tables for longitudinal UI.
"""

from __future__ import annotations

from typing import Any


def load_arc_pattern_discoveries(cur, arc_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    needle = f"%{arc_id.replace('_', ' ')}%"
    cur.execute(
        """
        SELECT id,
               pattern_type,
               confidence AS confidence_score,
               COALESCE(
                   data->>'description',
                   data->>'summary',
                   data->>'title',
                   LEFT(data::text, 500)
               ) AS description,
               data AS metadata,
               created_at AS discovered_at
        FROM intelligence.pattern_discoveries
        WHERE data->>'arc_id' = %s
           OR data::text ILIKE %s
        ORDER BY confidence DESC NULLS LAST, created_at DESC
        LIMIT %s
        """,
        (arc_id, needle, limit),
    )
    cols = [d[0] for d in cur.description]
    rows = []
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        if d.get("discovered_at") and hasattr(d["discovered_at"], "isoformat"):
            d["discovered_at"] = d["discovered_at"].isoformat()
        rows.append(d)
    return rows


def load_arc_cross_domain_correlations(cur, arc_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT correlation_id AS id,
               correlation_type,
               COALESCE(
                   metadata->>'description',
                   correlation_type || ': ' || domain_1 || ' ↔ ' || domain_2
               ) AS description,
               correlation_strength AS strength_score,
               metadata,
               discovered_at AS created_at
        FROM intelligence.cross_domain_correlations
        WHERE metadata->>'arc_id' = %s
        ORDER BY correlation_strength DESC NULLS LAST, discovered_at DESC
        LIMIT %s
        """,
        (arc_id, limit),
    )
    cols = [d[0] for d in cur.description]
    rows = []
    for row in cur.fetchall():
        d = dict(zip(cols, row))
        if d.get("created_at") and hasattr(d["created_at"], "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        rows.append(d)
    return rows


def load_arc_prior_analogues(cur, arc_id: str, *, limit: int = 10) -> list[dict[str, Any]]:
    """Merge pattern_discoveries and cross_domain_correlations for arc reports and UI."""
    patterns = [
        {**row, "source_table": "pattern_discoveries"}
        for row in load_arc_pattern_discoveries(cur, arc_id, limit=limit)
    ]
    correlations = [
        {**row, "source_table": "cross_domain_correlations"}
        for row in load_arc_cross_domain_correlations(cur, arc_id, limit=limit)
    ]
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in patterns + correlations:
        desc = (row.get("description") or "").strip()
        if not desc or desc in seen:
            continue
        seen.add(desc)
        merged.append(row)
    merged.sort(
        key=lambda r: float(r.get("confidence_score") or r.get("strength_score") or 0),
        reverse=True,
    )
    return merged[:limit]
