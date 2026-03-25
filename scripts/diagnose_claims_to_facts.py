#!/usr/bin/env python3
"""Diagnose claims_to_facts backlog: pending counts, resolution sample, gap catalog, entity coverage."""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    try:
        with open(os.path.join(ROOT, ".db_password_widow")) as f:
            os.environ.setdefault("DB_PASSWORD", f.read().strip())
    except OSError:
        pass

from shared.database.connection import get_db_connection
from shared.domain_registry import get_active_domain_keys, resolve_domain_schema


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare promoted vs unresolved (resolution sample), gap catalog, and coverage."
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=500,
        help="Rows to run resolver on (dry-run, no inserts); max 5000 (default 500).",
    )
    parser.add_argument(
        "--skip-sample",
        action="store_true",
        help="Skip dry-run resolution (faster; counts and catalog only).",
    )
    args = parser.parse_args()

    from services.claim_extraction_service import (
        CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL,
        get_claims_to_facts_batch_limit,
        get_claims_to_facts_min_confidence,
        sample_unpromoted_claim_resolution_stats,
    )

    min_conf = get_claims_to_facts_min_confidence()
    batch_lim = get_claims_to_facts_batch_limit()

    conn = get_db_connection()
    if not conn:
        print("ERROR: no DB connection")
        return 1
    try:
        conn.rollback()
    except Exception:
        pass

    cur = conn.cursor()

    print("=== Promotion thresholds (must match backlog + promote) ===")
    print(f"  CLAIMS_TO_FACTS_MIN_CONFIDENCE (effective): {min_conf}")
    print(f"  CLAIMS_TO_FACTS_BATCH_LIMIT (per run):       {batch_lim:,}")

    print("\n=== extracted_claims / versioned_facts ===")
    cur.execute("SELECT COUNT(*) FROM intelligence.extracted_claims")
    total = cur.fetchone()[0]
    print(f"Total extracted_claims: {total:,}")

    cur.execute(
        """
        SELECT COUNT(*) FROM intelligence.extracted_claims ec
        WHERE ec.confidence >= %s
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.versioned_facts vf
              WHERE vf.metadata->>'source_claim_id' = ec.id::text
          )
        """
        + CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL,
        (min_conf,),
    )
    unpromoted = cur.fetchone()[0]
    print(
        f"Unpromoted (confidence >= {min_conf}, excluding gap-catalog ignored pairs): {unpromoted:,}"
    )

    cur.execute("SELECT COUNT(*) FROM intelligence.versioned_facts WHERE metadata->>'source_claim_id' IS NOT NULL")
    promoted_vf = cur.fetchone()[0]
    print(f"versioned_facts from claims (has source_claim_id): {promoted_vf:,}")

    if not args.skip_sample:
        print("\n=== Dry-run resolution sample (same resolver as promote; no inserts) ===")
        stats = sample_unpromoted_claim_resolution_stats(limit=args.sample_limit, min_confidence=min_conf)
        if stats.get("error"):
            print(f"  error: {stats['error']}")
        else:
            c = int(stats.get("candidates", 0))
            r = int(stats.get("resolved", 0))
            u = int(stats.get("unresolved", 0))
            rate = stats.get("resolve_rate", 0.0)
            print(f"  sample size:     {c:,}")
            print(f"  resolved:        {r:,}  (would promote)")
            print(f"  unresolved:      {u:,}  (subject → entity_profiles failed)")
            print(f"  resolve_rate:    {rate}  (higher is better — invest in entities/aliases if low)")
            if c > 0 and rate < 0.15:
                print(
                    "\n  Hint: Low resolve rate — prioritize claim_subject_gaps seed/refresh, "
                    "entity_profile_sync, and aliases (see docs/CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md)."
                )

    print("\n=== claim_subject_gap_catalog (research snapshot; refresh via API or refresh_claim_subject_gaps.py) ===")
    try:
        cur.execute(
            """
            SELECT COALESCE(status, '(null)'), COUNT(*)
            FROM intelligence.claim_subject_gap_catalog
            GROUP BY 1 ORDER BY 2 DESC
            """
        )
        rows = cur.fetchall()
        if not rows:
            print("  (empty — run POST /api/context_centric/claim_subject_gaps/refresh)")
        else:
            for st, cnt in rows:
                print(f"  status {st}: {cnt:,}")
        cur.execute(
            """
            SELECT domain_key, sample_subject, unpromoted_claim_count, status
            FROM intelligence.claim_subject_gap_catalog
            WHERE COALESCE(status, '') <> 'ignored'
            ORDER BY unpromoted_claim_count DESC NULLS LAST
            LIMIT 8
            """
        )
        top = cur.fetchall()
        if top:
            print("\n  Top gap subjects (by unpromoted_claim_count):")
            for dk, subj, cnt, st in top:
                print(f"    [{dk}] {cnt:,} claims — {st!r} — { (subj or '')[:80]!r}")
    except Exception as e:
        print(f"  (skip: {e})")

    print("\n=== Per-domain entity pool (coverage for resolution) ===")
    for dk in get_active_domain_keys():
        try:
            sch = resolve_domain_schema(dk)
        except Exception:
            continue
        try:
            cur.execute(f"SELECT COUNT(*) FROM {sch}.entity_canonical")
            n_can = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {sch}.article_entities WHERE canonical_entity_id IS NULL")
            n_unl = cur.fetchone()[0]
            cur.execute(f"SELECT COUNT(*) FROM {sch}.article_entities")
            n_ae = cur.fetchone()[0]
            print(f"  {dk}: entity_canonical={n_can:,} article_entities={n_ae:,} unlinked_ae={n_unl:,}")
        except Exception as e:
            print(f"  {dk}: (skip: {e})")

    print("\n=== context_entity_mentions coverage ===")
    try:
        cur.execute("SELECT COUNT(*) FROM intelligence.contexts")
        tot_ctx = cur.fetchone()[0]
        cur.execute("SELECT COUNT(DISTINCT context_id) FROM intelligence.context_entity_mentions")
        with_m = cur.fetchone()[0]
        pct = round(100.0 * with_m / tot_ctx, 1) if tot_ctx else 0.0
        print(
            f"  contexts={tot_ctx:,} with mention row(s)={with_m:,} (~{pct}%)\n"
            "  Improve via entity_profile_sync + backfill_context_entity_mentions (see AGENTS.md / CLAIMS doc)."
        )
    except Exception as e:
        print(f"  (unavailable: {e})")
        try:
            conn.rollback()
        except Exception:
            pass

    print("\n=== Sample unpromoted claim lines (for eyeball) ===")
    cur.execute(
        """
        SELECT ec.id, ec.subject_text, ec.predicate_text, ec.confidence
        FROM intelligence.extracted_claims ec
        WHERE ec.confidence >= %s
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.versioned_facts vf
              WHERE vf.metadata->>'source_claim_id' = ec.id::text
          )
        """
        + CLAIM_PROMOTION_GAP_IGNORED_EXCLUDE_SQL
        + """
        ORDER BY ec.confidence DESC
        LIMIT 5
        """,
        (min_conf,),
    )
    for row in cur.fetchall():
        print(f"  ID {row[0]}: {row[1]!r} / {row[2]!r} (conf={row[3]:.2f})")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
