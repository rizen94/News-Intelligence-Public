#!/usr/bin/env python3
"""Fill Situation hub blanks from non-RSS APIs + activate AI RSS.

1) Activate probed-OK artificial_intelligence.rss_feeds (leave dead Anthropic/MS off)
2) Refresh FRED macro for hub series (if FRED_API_KEY set)
3) Patch Situation hubs with ## Non-RSS evidence (API) from macro + sanctions + Federal Register
4) Finance hubs also get Quiver / EIA / macro-history finance section
5) Optional: run sanctions_refresh if table empty

Usage:
  PYTHONPATH=api python3 api/scripts/fill_situation_api_evidence.py --force --sync
  PYTHONPATH=api python3 api/scripts/fill_situation_api_evidence.py --force --sync \\
    --hubs-only resource_movements market_trends --skip-ai-rss
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fill_situation_api_evidence")

# Probed OK 2026-10-05 (exclude Anthropic 404, MS blog 410)
AI_ACTIVATE_IDS = (
    106, 107, 108, 109, 110,  # arxiv family
    112, 114, 116, 120, 121,  # openai, google, hf, mit, deepmind
    153, 154, 156, 160, 163, 165, 169, 186, 187,  # labs + commentators
)
AI_DELETE_DEAD_IDS = (113, 115)  # anthropic 404, ms blog 410


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def activate_ai_feeds(*, dry_run: bool) -> dict:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            if dry_run:
                cur.execute(
                    """
                    SELECT count(*) FROM artificial_intelligence.rss_feeds
                    WHERE id = ANY(%s) AND NOT is_active
                    """,
                    (list(AI_ACTIVATE_IDS),),
                )
                would = cur.fetchone()[0]
                return {"dry_run": True, "would_activate": would}
            cur.execute(
                """
                UPDATE artificial_intelligence.rss_feeds
                SET is_active = true, status = 'active'
                WHERE id = ANY(%s)
                RETURNING id, feed_name
                """,
                (list(AI_ACTIVATE_IDS),),
            )
            activated = [{"id": r[0], "name": r[1]} for r in (cur.fetchall() or [])]
            # Soft-delete dead rows (null article feed_ids then delete)
            cur.execute(
                """
                UPDATE artificial_intelligence.articles
                SET feed_id = NULL WHERE feed_id = ANY(%s)
                """,
                (list(AI_DELETE_DEAD_IDS),),
            )
            cur.execute(
                """
                DELETE FROM artificial_intelligence.rss_feeds
                WHERE id = ANY(%s)
                RETURNING id, feed_name
                """,
                (list(AI_DELETE_DEAD_IDS),),
            )
            deleted = [{"id": r[0], "name": r[1]} for r in (cur.fetchall() or [])]
            cur.execute(
                """
                SELECT count(*) FILTER (WHERE is_active), count(*)
                FROM artificial_intelligence.rss_feeds
                """
            )
            a, t = cur.fetchone()
        conn.commit()
    return {"activated": activated, "deleted_dead": deleted, "active_total": [a, t]}


def ensure_sanctions(*, dry_run: bool) -> dict:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM intelligence.sanctions_actions")
            n = int(cur.fetchone()[0] or 0)
    if n > 0 or dry_run:
        return {"rows": n, "refreshed": False}
    try:
        from services.sanctions_ingest_service import run_sanctions_refresh

        out = run_sanctions_refresh(limit=400)
        return {"rows_before": 0, "refreshed": True, "result": out}
    except Exception as e:
        logger.warning("sanctions refresh failed: %s", e)
        return {"rows": 0, "refreshed": False, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Reserved; evidence always rewritten")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--skip-ai-rss", action="store_true")
    parser.add_argument("--skip-evidence", action="store_true")
    parser.add_argument("--no-macro-refresh", action="store_true")
    parser.add_argument(
        "--hubs-only",
        nargs="+",
        metavar="CLUSTER_KEY",
        help="Limit evidence patch to these cluster_keys (e.g. resource_movements market_trends)",
    )
    parser.add_argument(
        "--skip-finance-api",
        action="store_true",
        help="Do not write Quiver/EIA/macro finance section on resource_movements/market_trends",
    )
    args = parser.parse_args()

    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("NI_VAULT_NOTES_ENABLED", "true")

    stats: dict = {"ok": True, "started_at": _now()}

    if not args.skip_ai_rss:
        stats["ai_rss"] = activate_ai_feeds(dry_run=args.dry_run)

    stats["sanctions"] = ensure_sanctions(dry_run=args.dry_run)

    if not args.skip_evidence:
        from services.situation_api_evidence_service import apply_evidence_batch

        stats["evidence"] = apply_evidence_batch(
            cluster_keys=args.hubs_only,
            refresh_macro=not args.no_macro_refresh,
            dry_run=args.dry_run,
            include_finance_api=not args.skip_finance_api,
        )

    if args.sync and not args.dry_run:
        try:
            from pathlib import Path

            from scripts.vault_quality_cleanup import write_reading_mocs
            from services.vault_bridge_service import vault_root
            from services.vault_tag_link_sync_service import sync_vault_file

            root = vault_root()
            paths = []
            for r in (stats.get("evidence") or {}).get("results") or []:
                if r.get("path"):
                    paths.append(r["path"])
            for p in paths:
                sync_vault_file(root / p)
            write_reading_mocs()
            stats["sync"] = {"n": len(paths)}
        except Exception as e:
            logger.exception("sync")
            stats["sync_error"] = str(e)

    print(json.dumps(stats, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
