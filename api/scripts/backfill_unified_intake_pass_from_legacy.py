#!/usr/bin/env python3
"""Bulk backfill unified_intake_extraction pass markers for legacy-complete articles (no LLM)."""

from __future__ import annotations

import argparse

from shared.domain_registry import pipeline_url_schema_pairs
from shared.unified_intake_backlog import (
    backfill_unified_pass_from_legacy_batch,
    get_unified_intake_backlog_stats,
    unified_intake_legacy_aware_backlog_enabled,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-domain", type=int, default=2000, help="Max rows per domain per round")
    parser.add_argument("--rounds", type=int, default=50, help="Backfill rounds (stop when idle)")
    args = parser.parse_args()

    if not unified_intake_legacy_aware_backlog_enabled():
        print("UNIFIED_INTAKE_LEGACY_AWARE_BACKLOG is disabled; nothing to do.")
        return

    stats = get_unified_intake_backlog_stats()
    print("before:", stats)

    total = 0
    for r in range(max(1, args.rounds)):
        round_n = 0
        for _dk, schema in pipeline_url_schema_pairs():
            ids = backfill_unified_pass_from_legacy_batch(
                schema_name=schema,
                limit=args.per_domain,
            )
            round_n += len(ids)
        total += round_n
        print(f"round {r + 1}: backfilled {round_n}")
        if round_n == 0:
            break

    stats_after = get_unified_intake_backlog_stats()
    print(f"backfilled total: {total}")
    print("after:", stats_after)


if __name__ == "__main__":
    main()
