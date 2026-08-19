#!/usr/bin/env python3
"""Snapshot enrichment/quality for recent articles (watch feed rebuild)."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
os.chdir(ROOT / "api")

from shared.database.connection import get_db_connection_context  # noqa: E402

SCHEMAS = ["finance", "politics", "legal", "medicine", "artificial_intelligence"]
OUT_DIR = ROOT / "logs" / "quality_watch"


def main() -> None:
    label = (sys.argv[1] if len(sys.argv) > 1 else "snapshot").strip() or "snapshot"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = OUT_DIR / f"{label}_{stamp}.txt"
    lines = [f"{label} at {datetime.now(timezone.utc).isoformat()}"]

    with get_db_connection_context() as conn:
        cur = conn.cursor()
        for s in SCHEMAS:
            cur.execute(
                f"""
                SELECT
                  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '6 hours') AS created_6h,
                  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '6 hours'
                    AND enrichment_status = 'enriched') AS enriched_6h,
                  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '6 hours'
                    AND enrichment_status IN ('failed','inaccessible')) AS bad_6h,
                  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '6 hours'
                    AND enrichment_status = 'pending') AS pending_6h,
                  ROUND(AVG(quality_score) FILTER (
                    WHERE created_at > NOW() - INTERVAL '6 hours'
                      AND enrichment_status = 'enriched'
                      AND quality_score IS NOT NULL)::numeric, 3) AS avg_q,
                  ROUND(AVG(LENGTH(COALESCE(content,''))) FILTER (
                    WHERE created_at > NOW() - INTERVAL '6 hours'
                      AND enrichment_status = 'enriched')::numeric, 0) AS avg_len,
                  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY quality_score) FILTER (
                    WHERE created_at > NOW() - INTERVAL '6 hours'
                      AND enrichment_status = 'enriched'
                      AND quality_score IS NOT NULL)::numeric, 3) AS med_q
                FROM {s}.articles
                """
            )
            r = cur.fetchone()
            lines.append(
                f"{s}: created_6h={r[0]} enriched={r[1]} bad={r[2]} pending={r[3]} "
                f"avg_q={r[4]} med_q={r[6]} avg_len={r[5]}"
            )

            # Per-feed quality for feeds touched in rebuild window
            cur.execute(
                f"""
                SELECT f.id, f.feed_name,
                       COUNT(a.id) AS n,
                       COUNT(*) FILTER (WHERE a.enrichment_status = 'enriched') AS enr,
                       COUNT(*) FILTER (WHERE a.enrichment_status IN ('failed','inaccessible')) AS bad,
                       ROUND(AVG(a.quality_score) FILTER (
                         WHERE a.enrichment_status = 'enriched' AND a.quality_score IS NOT NULL
                       )::numeric, 3) AS avg_q,
                       ROUND(AVG(LENGTH(COALESCE(a.content,''))) FILTER (
                         WHERE a.enrichment_status = 'enriched'
                       )::numeric, 0) AS avg_len
                FROM {s}.rss_feeds f
                LEFT JOIN {s}.articles a
                  ON a.feed_id = f.id
                 AND a.created_at > NOW() - INTERVAL '6 hours'
                WHERE f.is_active
                GROUP BY f.id, f.feed_name
                HAVING COUNT(a.id) > 0
                ORDER BY COUNT(a.id) DESC
                """
            )
            for row in cur.fetchall():
                lines.append(
                    f"  feed {row[0]} {row[1]}: n={row[2]} enr={row[3]} bad={row[4]} "
                    f"avg_q={row[5]} avg_len={row[6]}"
                )

    path.write_text("\n".join(lines) + "\n")
    print(path.read_text())
    print(f"wrote {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
