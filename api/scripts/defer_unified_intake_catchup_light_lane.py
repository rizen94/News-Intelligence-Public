#!/usr/bin/env python3
"""Bulk defer unified intake for catch-up: tier_3 articles below quality threshold (no LLM)."""

from __future__ import annotations

import argparse

from shared.database.connection import get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs
from shared.pipeline_pass_marker import (
    TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
    bulk_record_article_phase_pass,
    sql_article_pass_null,
)
from shared.unified_intake_backlog import sql_actionable_unified_intake


def defer_tier3_below_quality(
    *,
    min_quality: float = 0.55,
    per_domain: int = 10_000,
    dry_run: bool = False,
) -> dict[str, int]:
    """Mark pass without LLM for tier_3 backlog rows under min_quality."""
    counts: dict[str, int] = {}
    pass_clause = f" AND ({sql_article_pass_null('unified_intake_extraction', 'a')}) "
    tier_sql = "COALESCE(a.metadata #>> '{source_credibility,tier}', 'tier_3') = 'tier_3'"

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for domain_key, schema in pipeline_url_schema_pairs():
                act = sql_actionable_unified_intake(schema, "a")
                cur.execute(
                    f"""
                    SELECT a.id
                    FROM {schema}.articles a
                    WHERE ({act})
                      AND ({tier_sql})
                      AND COALESCE(a.quality_score, 0) < %s
                      {pass_clause}
                    ORDER BY COALESCE(a.quality_score, 0) ASC, a.created_at ASC
                    LIMIT %s
                    """,
                    (min_quality, per_domain),
                )
                ids = [int(r[0]) for r in cur.fetchall()]
                if ids and not dry_run:
                    bulk_record_article_phase_pass(
                        schema,
                        ids,
                        "unified_intake_extraction",
                        "signal_deferred_catchup_tier3",
                        TERMINAL_PROCESSED_EMPTY_LEGITIMATE,
                    )
                counts[domain_key] = len(ids)

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-quality", type=float, default=0.55)
    parser.add_argument("--per-domain", type=int, default=10_000)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    counts = defer_tier3_below_quality(
        min_quality=args.min_quality,
        per_domain=args.per_domain,
        dry_run=args.dry_run,
    )
    total = sum(counts.values())
    mode = "would defer" if args.dry_run else "deferred"
    print(f"{mode} {total} unified intake rows (tier_3, quality < {args.min_quality})")
    for dk, n in sorted(counts.items()):
        if n:
            print(f"  {dk}: {n}")


if __name__ == "__main__":
    main()
