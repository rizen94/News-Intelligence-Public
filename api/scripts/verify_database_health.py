#!/usr/bin/env python3
"""
CI/operator health checks for news_intel data–pipeline alignment.

Usage:
  PYTHONPATH=. python3 scripts/verify_database_health.py
  PYTHONPATH=. python3 scripts/verify_database_health.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from config.runtime import env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

DEFAULT_MAX_ENTITY_RELATIONSHIPS = env_int("ENTITY_RELATIONSHIPS_MAX_ROWS", 5_000_000)
DEFAULT_MAX_CLAIMS_FACTS_RATIO = env_int("DB_HEALTH_MAX_CLAIMS_FACTS_RATIO", 20)
DEFAULT_MAX_CONTEXT_ORPHAN_PCT = env_int("DB_HEALTH_MAX_CONTEXT_ORPHAN_PCT", 5)


def _estimate_entity_relationships(cur) -> int:
    cur.execute(
        """
        SELECT reltuples::bigint FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'intelligence' AND c.relname = 'entity_relationships'
        """
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def collect_checks() -> tuple[list[dict], bool]:
    checks: list[dict] = []
    ok = True

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            er_est = _estimate_entity_relationships(cur)
            checks.append(
                {
                    "name": "entity_relationships_row_estimate",
                    "value": er_est,
                    "threshold": DEFAULT_MAX_ENTITY_RELATIONSHIPS,
                    "ok": er_est <= DEFAULT_MAX_ENTITY_RELATIONSHIPS,
                }
            )
            if er_est > DEFAULT_MAX_ENTITY_RELATIONSHIPS:
                ok = False

            cur.execute("SELECT COUNT(*)::bigint FROM intelligence.extracted_claims")
            claims = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*)::bigint FROM intelligence.versioned_facts")
            facts = int(cur.fetchone()[0] or 0)
            ratio = (claims / facts) if facts else (claims if claims else 0)
            checks.append(
                {
                    "name": "claims_to_facts_ratio",
                    "value": round(ratio, 2),
                    "claims": claims,
                    "facts": facts,
                    "threshold": DEFAULT_MAX_CLAIMS_FACTS_RATIO,
                    "ok": facts > 0 and ratio <= DEFAULT_MAX_CLAIMS_FACTS_RATIO,
                }
            )
            if facts == 0 or ratio > DEFAULT_MAX_CLAIMS_FACTS_RATIO:
                ok = False

            for domain_key in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(domain_key)
                cur.execute(f"SELECT COUNT(*)::int FROM {schema}.articles")
                articles = int(cur.fetchone()[0] or 0)
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT atc.article_id)::int
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE c.domain_key = %s
                    """,
                    (domain_key,),
                )
                linked = int(cur.fetchone()[0] or 0)
                orphan_pct = ((articles - linked) / articles * 100) if articles else 0
                domain_ok = orphan_pct <= DEFAULT_MAX_CONTEXT_ORPHAN_PCT
                checks.append(
                    {
                        "name": f"context_orphan_pct_{domain_key}",
                        "value": round(orphan_pct, 2),
                        "articles": articles,
                        "linked": linked,
                        "threshold": DEFAULT_MAX_CONTEXT_ORPHAN_PCT,
                        "ok": domain_ok,
                    }
                )
                if not domain_ok:
                    ok = False

                cur.execute(
                    f"""
                    SELECT COUNT(*)::int FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND s.article_count IS DISTINCT FROM (
                        SELECT COUNT(*)::int FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = s.id
                      )
                    """
                )
                mismatched = int(cur.fetchone()[0] or 0)
                checks.append(
                    {
                        "name": f"storyline_count_mismatch_{domain_key}",
                        "value": mismatched,
                        "threshold": 0,
                        "ok": mismatched == 0,
                    }
                )
                if mismatched:
                    ok = False

    return checks, ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify database health thresholds")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    checks, ok = collect_checks()
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    else:
        for c in checks:
            status = "OK" if c["ok"] else "FAIL"
            print(f"{status} {c['name']}: {c.get('value')} (threshold {c.get('threshold')})")
        print("OVERALL:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
