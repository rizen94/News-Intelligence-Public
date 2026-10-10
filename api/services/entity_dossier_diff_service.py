"""
Entity dossier diffs (Phase 6 C6) — weekly diff from versioned_facts.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def weekly_dossier_diff(
    entity_profile_id: int,
    *,
    as_of: datetime | None = None,
    window_days: int = 7,
) -> dict[str, Any]:
    """
    Compare versioned_facts active now vs those active at (as_of - window).

    Returns added / removed / changed fact summaries for dossier UX.
    """
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    now = as_of or datetime.now(timezone.utc)
    start = now - timedelta(days=max(1, window_days))

    def _active_at(cur, when: datetime) -> dict[str, dict[str, Any]]:
        cur.execute(
            """
            SELECT id, fact_type, fact_text, confidence, valid_from, valid_to,
                   extraction_method, metadata
            FROM intelligence.versioned_facts
            WHERE entity_profile_id = %s
              AND valid_from <= %s
              AND (valid_to IS NULL OR valid_to > %s)
              AND superseded_by_id IS NULL
            ORDER BY id
            """,
            (entity_profile_id, when, when),
        )
        out: dict[str, dict[str, Any]] = {}
        for r in cur.fetchall() or []:
            d = dict(r)
            key = f"{(d.get('fact_type') or '').lower()}::{(d.get('fact_text') or '')[:200].lower()}"
            out[key] = d
        return out

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                before = _active_at(cur, start)
                after = _active_at(cur, now)
    except Exception as e:
        logger.warning("weekly_dossier_diff: %s", e)
        return {
            "entity_profile_id": entity_profile_id,
            "added": [],
            "removed": [],
            "unchanged": 0,
            "error": str(e)[:200],
        }

    added_keys = set(after) - set(before)
    removed_keys = set(before) - set(after)
    unchanged = len(set(after) & set(before))
    return {
        "entity_profile_id": entity_profile_id,
        "window_days": window_days,
        "as_of": now.isoformat(),
        "window_start": start.isoformat(),
        "added": [
            {
                "id": after[k].get("id"),
                "fact_type": after[k].get("fact_type"),
                "fact_text": after[k].get("fact_text"),
                "confidence": float(after[k].get("confidence") or 0),
            }
            for k in sorted(added_keys)
        ],
        "removed": [
            {
                "id": before[k].get("id"),
                "fact_type": before[k].get("fact_type"),
                "fact_text": before[k].get("fact_text"),
            }
            for k in sorted(removed_keys)
        ],
        "unchanged": unchanged,
        "summary": f"+{len(added_keys)} / -{len(removed_keys)} facts over {window_days}d",
    }
