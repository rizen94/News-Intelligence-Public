#!/usr/bin/env python3
"""Reset signal-gated claim_extraction contexts stuck on processed_empty_legitimate.

Bug: defer_signal_light_claim_contexts_batch recorded `processed_empty_legitimate` as the
terminal state for signal-deferred contexts (article_signal_gate.py lines 450-454).
This caused them to be permanently excluded from retry_pending — claim_extraction never
runs on them even when new full-lane articles arrive later.

Fix: clear last_terminal_state and last_outcome on affected contexts so defer_cycle can
re-mark them (they'll stay in retry_pending until signal-gate is lifted).

Runs against the NI database on Widow (news_intel, :5432).
"""

import json
import sys
from datetime import datetime, timezone

# Minimal inline psycopg2 — no project dependencies needed for migration.
try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 is required. Install on Widow or run via `python scripts/ni_reset_stuck_contexts.py`.")
    sys.exit(1)


def get_db_uri():
    """Read NEWS_INTEL_DATABASE_URI from environment, same as api code."""
    from config.runtime import env_str

    uri = env_str("NEWS_INTEL_DATABASE_URI", "")
    if not uri:
        # Fallback for local dev — connect to widow
        return "postgresql://newsapp@localhost:5432/news_intel"
    return uri


def main():
    print("=" * 70)
    print("signal_deferred stuck-context reset (processed_empty_legitimate)")
    print("=" * 70)

    # ---- Step 1: count affected contexts ----
    conn = psycopg2.connect(get_db_uri())
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM intelligence.contexts c
        WHERE c.metadata::jsonb->'pipeline'->>'claim_extraction_last_pass_at' IS NOT NULL
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' = 'processed_empty_legitimate'
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_outcome'      = 'signal_deferred'
        """
    )
    total = cur.fetchone()[0]
    print(f"\n[1/3] Affected contexts: {total}")
    if total == 0:
        print("Nothing to do — no stuck contexts found.")
        conn.close()
        sys.exit(0)

    # Also show breakdown by context status (active / inactive) and when they were last marked
    cur.execute(
        """
        SELECT
            c.status,
            count(*),
            min(c.metadata::jsonb->>'pipeline') as oldest_marked,
            max(c.metadata::jsonb->>'pipeline') as newest_marked
        FROM intelligence.contexts c
        WHERE c.metadata::jsonb->'pipeline'->>'claim_extraction_last_pass_at' IS NOT NULL
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' = 'processed_empty_legitimate'
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_outcome'      = 'signal_deferred'
        GROUP BY c.status
        ORDER BY c.status;
        """
    )
    for row in cur.fetchall():
        status, cnt, oldest, newest = row
        print(f"       {status}: {cnt} (oldest={oldest}, newest={newest})")

    # ---- Step 2: reset the markers ----
    print(f"\n[2/3] Resetting ...", end=" ")
    sys.stdout.flush()

    cur.execute(
        """
        UPDATE intelligence.contexts
        SET metadata = jsonb_set(
                coalesce(metadata, '{}'::jsonb),
                '{pipeline,claim_extraction_last_pass_at}',
                NULL
              )
            -- also clear terminal_state and outcome
          , metadata = jsonb_set(
                metadata,
                '{pipeline,claim_extraction_last_terminal_state}',
                NULL
              )
          , metadata = jsonb_set(
                metadata,
                '{pipeline,claim_extraction_last_outcome}',
                NULL
              )
        WHERE metadata::jsonb->'pipeline'->>'claim_extraction_last_pass_at' IS NOT NULL
          AND metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' = 'processed_empty_legitimate'
          AND metadata::jsonb->'pipeline'->>'claim_extraction_last_outcome'      = 'signal_deferred'
        """
    )
    updated = cur.rowcount
    conn.commit()
    print(f"OK ({updated} rows)")

    # ---- Step 3: verify ----
    print(f"\n[3/3] Verifying ...", end=" ")
    sys.stdout.flush()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM intelligence.contexts c
        WHERE c.metadata::jsonb->'pipeline'->>'claim_extraction_last_pass_at' IS NOT NULL
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' = 'processed_empty_legitimate'
          AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_outcome'      = 'signal_deferred'
        """
    )
    remaining = cur.fetchone()[0]

    if remaining == 0:
        print("All clear — no stuck contexts remain.")
    else:
        print(f"WARNING: {remaining} still stuck (check SQL)")

    # Show pending count after reset
    cur.execute(
        """
        SELECT COUNT(*)
        FROM intelligence.contexts c
        WHERE c.metadata::jsonb->'pipeline' IS NOT NULL
          AND (
               c.metadata::jsonb->'pipeline'->>'claim_extraction_last_pass_at' IS NULL
            OR c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' = 'failed_needs_retry'
               -- legacy: outcome without terminal_state
            OR (c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state') IS NOT NULL
               AND c.metadata::jsonb->'pipeline'->>'claim_extraction_last_terminal_state' NOT IN ('processed_with_output', 'processed_empty_legitimate')
          )
        """
    )
    pending_after = cur.fetchone()[0]
    print(f"\n  claim_extraction retry_pending after reset: {pending_after}")

    conn.close()
    print("\nDone. Next defer_cycle will re-mark these contexts (they'll stay in pipeline until signal-gate lifts).")


if __name__ == "__main__":
    main()
