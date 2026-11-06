#!/usr/bin/env python3
"""
One-time backfill of missing storyline_articles bridge rows.

Finds storylines with zero or few articles (below the pipeline's normal
membership threshold) and inserts bridge rows using the same scoring logic
that proactive_detection / membership_admit uses.

Usage:
  # Dry-run preview — what would be inserted
  PYTHONPATH=api python3 api/scripts/backfill_storyline_articles_bridge.py

  # Per-domain dry-run
  PYTHONPATH=api python3 api/scripts/backfill_storyline_articles_bridge.py --domain politics

  # Apply (actually INSERT)
  PYTHONPATH=api python3 api/scripts/backfill_storyline_articles_bridge.py --apply

  # Only specific storylines
  PYTHONPATH=api python3 api/scripts/backfill_storyline_articles_bridge.py --storyline-ids 1001 1002 --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from api.shared.database import get_db_connection_context  # noqa: E402
from api.shared.domain_registry import resolve_domain_schema  # noqa: E402
from api.shared.membership_scoring import score_article_storyline_membership  # noqa: E402
from api.shared.membership_store import MembershipIntent, admit as membership_admit  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)
logger = logging.getLogger("backfill_storyline_articles_bridge")


def find_orphaned_candidates(
    cur, schema: str, domain_key: str, min_storylines: int = 0, max_bridges: int = 50
) -> list[tuple]:
    """Find storylines with few/no article bridges."""
    cur.execute(
        f"""
        SELECT s.id, s.title, COALESCE(s.article_count, 0) AS acount
             , COUNT(sa.storyline_id)::int AS bridge_count
        FROM {schema}.storylines s
        LEFT JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
            AND sa.added_at >= NOW() - INTERVAL '180 days'
        WHERE s.merged_into_id IS NULL
          AND COALESCE(s.status, 'active') NOT IN ('archived', 'merged', 'deleted')
          AND (s.updated_at >= NOW() - INTERVAL '180 days'
               OR EXISTS (
                   SELECT 1 FROM {schema}.storyline_articles sa2
                   WHERE sa2.storyline_id = s.id
                     AND sa2.added_at >= NOW() - INTERVAL '90 days'
               ))
        GROUP BY s.id, s.title, s.article_count
        HAVING COUNT(sa.storyline_id)::int BETWEEN %s AND %s
          AND COALESCE(s.article_count, 0) > 0
        ORDER BY s.updated_at DESC NULLS LAST
        LIMIT 200
        """,
        (min_storylines, max_bridges),
    )
    return list(cur.fetchall() or [])


def _extract_tokens_from_sig(sig_str) -> list:
    """Extract entity tokens from an anchor_signature JSON string."""
    try:
        sig = json.loads(sig_str) if isinstance(sig_str, str) else sig_str
        identity = sig.get("identity", []) if isinstance(sig, dict) else []
        return [str(t).lower().strip() for t in identity[:40] if t]
    except Exception:
        return []


def _has_entity_overlap(cur, schema: str, article_id: int, tokens: list) -> bool:
    """Check if an article's entities overlap with storyline tokens."""
    cur.execute(
        f"""
        SELECT COUNT(*) FROM {schema}.article_entities ae
        WHERE ae.article_id = %s AND lower(ae.entity_name) = ANY(%s)
        """,
        (int(article_id), tokens),
    )
    return int(cur.fetchone()[0]) > 0


def backfill_for_storyline(cur, schema: str, domain_key: str, storyline_id: int, title: str, apply: bool) -> dict:
    """Score articles for a single storyline and insert missing bridges."""
    stats = {
        "storyline_id": storyline_id,
        "title": title[:80],
        "current_bridges": 0,
        "candidates_evaluated": 0,
        "bridges_inserted": 0,
        "bridges_skipped_low_score": 0,
        "errors": [],
    }

    cur.execute(
        f"""SELECT COUNT(*) FROM {schema}.storyline_articles sa
            WHERE sa.storyline_id = %s AND sa.added_at >= NOW() - INTERVAL '180 days'""",
        (storyline_id,),
    )
    stats["current_bridges"] = int(cur.fetchone()[0])

    cur.execute(f"""SELECT s.anchor_signature, s.metadata FROM {schema}.storylines s WHERE s.id = %s""", (storyline_id,))
    row = cur.fetchone()
    if not row or not row[0]:
        return stats

    identity_tokens = _extract_tokens_from_sig(row[0])
    if not identity_tokens:
        cur.execute(f"""SELECT DISTINCT ae.entity_name
            FROM {schema}.storyline_articles sa
            JOIN {schema}.article_entities ae ON sa.article_id = ae.article_id
            WHERE sa.storyline_id = %s AND sa.added_at >= NOW() - INTERVAL '180 days' LIMIT 40""", (storyline_id,))
        fallback_tokens = [r[0].lower() for r in cur.fetchall()]
        if not fallback_tokens:
            return stats
        identity_tokens = fallback_tokens

    cur.execute(f"""SELECT a.id, a.title, a.published_at, a.summary
        FROM {schema}.articles a
        WHERE COALESCE(a.published_at, a.created_at) >= NOW() - INTERVAL '180 days'
          AND NOT EXISTS (
              SELECT 1 FROM {schema}.storyline_articles sa
              WHERE sa.article_id = a.id AND sa.added_at >= NOW() - INTERVAL '90 days'
          ) LIMIT 200""")
    candidates = list(cur.fetchall() or [])

    for art_id, art_title, pub_at, summary in candidates:
        stats["candidates_evaluated"] += 1
        if not _has_entity_overlap(cur, schema, art_id, identity_tokens):
            continue

        try:
            conn = cur.connection
            ms = score_article_storyline_membership(
                conn, domain_key=domain_key, storyline_id=storyline_id,
                article_id=int(art_id), schema=schema,
            )
            if ms.rejected:
                stats["bridges_skipped_low_score"] += 1
                continue

            blend = float(ms.combined) if not ms.rejected and ms.combined > 0 else min(0.95, 0.55 + 0.05 * stats["current_bridges"])
            parts = ms.as_metadata() if not ms.rejected else {"combined": blend, "scorer": "backfill_bridge"}

            if apply:
                try:
                    membership_admit(
                        conn, domain_key=domain_key, schema=schema,
                        episode_id=storyline_id, article_id=int(art_id),
                        intent=MembershipIntent.DISCOVERY_SEED,
                        blend_score=blend, score_parts=parts,
                        added_by="backfill_bridge_script", recompute_score=False,
                    )
                    stats["bridges_inserted"] += 1
                except Exception as insert_err:
                    stats["errors"].append(f"{art_id}: {insert_err}")
            else:
                stats["bridges_inserted"] += 1
        except Exception as score_err:
            logger.debug("score failed %s/%s: %s", storyline_id, art_id, score_err)
            stats["errors"].append(f"{art_id}: {score_err}")

    return stats


def _resolve_sid_schema(cur, sid: int) -> tuple:
    """Auto-resolve schema for a given storyline_id by checking common schemas."""
    candidate_schemas = [
        "politics", "finance-markets", "science-tech", "artificial-intelligence",
        "health-medicine", "legal-regulatory", "environment-energy",
        "entertainment-sports",
    ]
    for schema in candidate_schemas:
        try:
            cur.execute(f"SELECT 1 FROM {schema}.storylines WHERE id = %s LIMIT 1", (sid,))
            if cur.fetchone():
                return schema, schema.replace("-", "_")
        except Exception:
            continue
    raise ValueError("unknown storyline_id")


def run(*, domain_key: str | None, storyline_ids: list[int] | None, apply: bool) -> dict:
    """Main entry point."""
    stats = {"domain": domain_key or "all", "apply": apply, "storylines_processed": 0,
             "total_bridges_inserted": 0, "per_storyline": [], "ts": datetime.now(timezone.utc).isoformat()}

    with get_db_connection_context() as conn:
        if storyline_ids:
            for sid in storyline_ids:
                cur = conn.cursor()
                schema, dk = _resolve_sid_schema(cur, sid)
                s = backfill_for_storyline(cur, schema, dk, sid, "", apply)
                stats["per_storyline"].append(s)
                stats["total_bridges_inserted"] += s["bridges_inserted"]
            if not apply:
                conn.rollback()
            return stats

        domains_to_scan = [domain_key] if domain_key else None
        if domains_to_scan is None:
            cur = conn.cursor()
            try:
                from api.shared.domain_registry import get_active_domain_keys
                domains_to_scan = list(get_active_domain_keys()) or []
            except Exception:
                logger.warning("Could not auto-detect domains; use --domain")
                stats["error"] = "no domains specified"
                return stats

        for dk in domains_to_scan:
            try:
                schema = resolve_domain_schema(dk)
            except Exception:
                logger.warning("Skipping unknown domain %s", dk)
                continue

            cur = conn.cursor()
            cur.execute("""SELECT EXISTS (SELECT FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'storylines')""", (schema,))
            if not int(cur.fetchone()[0]):
                logger.info("No storylines table in schema %s — skipping", schema)
                continue

            candidates = find_orphaned_candidates(cur, schema, dk, 0, 50)
            if not candidates:
                logger.info("Schema %s (%s): no orphaned storylines to backfill", schema, dk)
                continue

            logger.info("Schema %s (%s): found %d storyline(s) needing bridge fill", schema, dk, len(candidates))
            for sid, title, acount in candidates:
                s = backfill_for_storyline(cur, schema, dk, sid, title, apply)
                stats["storylines_processed"] += 1
                stats["total_bridges_inserted"] += s["bridges_inserted"]
                stats["per_storyline"].append(s)

            if not apply:
                conn.rollback()

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domain", default=None, help="Single domain_key to process")
    ap.add_argument("--storyline-ids", type=int, nargs="*", default=None,
                    help="Specific storyline IDs to backfill (auto-detects schemas)")
    ap.add_argument("--apply", action="store_true", help="Actually insert rows (default: dry-run)")
    args = ap.parse_args()

    stats = run(domain_key=args.domain, storyline_ids=args.storyline_ids, apply=bool(args.apply))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
