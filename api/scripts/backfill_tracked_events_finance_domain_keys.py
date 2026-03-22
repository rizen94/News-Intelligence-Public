#!/usr/bin/env python3
"""
One-off: append 'finance' to intelligence.tracked_events.domain_keys when text matches
macro/commodity signals (see services.commodity_event_bridge).
Safe to re-run (idempotent per row).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.commodity_event_bridge import text_suggests_macro_commodity_link  # noqa: E402
from shared.database.connection import get_db_connection  # noqa: E402


def main(limit: int = 500) -> None:
    conn = get_db_connection()
    if not conn:
        print("no db")
        sys.exit(1)
    updated = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_name, geographic_scope, editorial_briefing, domain_keys
                FROM intelligence.tracked_events
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
        for rid, name, geo, briefing, dkeys in rows:
            keys = list(dkeys) if dkeys else []
            if "finance" in [str(x).lower() for x in keys]:
                continue
            blob = f"{name or ''} {geo or ''} {briefing or ''}"
            if not text_suggests_macro_commodity_link(blob):
                continue
            new_keys = list(dict.fromkeys(keys + ["finance"]))
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.tracked_events
                    SET domain_keys = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (new_keys, rid),
                )
            updated += 1
        conn.commit()
    finally:
        conn.close()
    print(f"updated {updated} rows (scanned up to {limit})")


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    main(lim)
