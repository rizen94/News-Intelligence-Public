#!/usr/bin/env python3
"""
Pass-marker orphan ``documents`` contexts for ``event_tracking`` (non-pipeline silo).

Monitor no longer counts these after the pipeline-domain backlog fix; this clears
legacy inventory so reconciliation and ad-hoc counts stay honest.

Gated by default: refuses to run while pipeline catch-up phases are above ``--floor``.

  PYTHONPATH=api uv run python api/scripts/bulk_clear_documents_event_tracking.py --dry-run
  PYTHONPATH=api uv run python api/scripts/bulk_clear_documents_event_tracking.py
  PYTHONPATH=api uv run python api/scripts/bulk_clear_documents_event_tracking.py --force
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
_PROJECT_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(_API_ROOT / ".env", override=False)
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and (_PROJECT_ROOT / ".db_password_widow").is_file():
    os.environ.setdefault("DB_PASSWORD", (_PROJECT_ROOT / ".db_password_widow").read_text().strip())

DOCUMENTS_DOMAIN = "documents"
PHASE = "event_tracking"
OUTCOME = "non_pipeline_documents_skip"


def _documents_event_tracking_pending_sql(*, pass_filter: bool) -> tuple[str, list]:
    from services.backlog_metrics import _event_tracking_scan_window_params
    from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_context_pass_null

    max_age_days, min_len = _event_tracking_scan_window_params()
    pass_sql = ""
    if pass_filter and phase_backlog_uses_pass_marker(PHASE):
        pass_sql = f" AND ({sql_context_pass_null(PHASE, 'c')}) "
    sql = f"""
        SELECT c.id
        FROM intelligence.contexts c
        WHERE c.domain_key = %s
          AND c.created_at >= NOW() - (%s * INTERVAL '1 day')
          AND LENGTH(COALESCE(c.content, '')) >= %s
          AND NOT EXISTS (
              SELECT 1 FROM intelligence.event_chronicle_contexts ecc
              WHERE ecc.context_id = c.id
          )
          {pass_sql}
        ORDER BY c.id
    """
    return sql, [DOCUMENTS_DOMAIN, max_age_days, min_len]


def count_documents_pending() -> int:
    from shared.database.connection import get_db_connection_context

    sql, params = _documents_event_tracking_pending_sql(pass_filter=True)
    with get_db_connection_context() as conn:
        if not conn:
            return 0
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM ({sql}) sub", tuple(params))
            return int(cur.fetchone()[0] or 0)


def pipeline_backlog_snapshot() -> dict[str, int]:
    from services.backlog_metrics import (
        _count_claim_extraction_backlog,
        _count_entity_profile_build_backlog,
        _count_event_tracking_backlog,
        _count_unified_intake_extraction_pending,
    )

    return {
        "unified_intake_extraction": _count_unified_intake_extraction_pending(),
        "claim_extraction": _count_claim_extraction_backlog(),
        "entity_profile_build": _count_entity_profile_build_backlog(),
        "event_tracking": _count_event_tracking_backlog(),
    }


def gate_pipeline_clear(floor: int) -> tuple[bool, dict[str, int]]:
    snap = pipeline_backlog_snapshot()
    blocked = {k: v for k, v in snap.items() if v > floor}
    return not blocked, snap


def bulk_mark_documents(*, dry_run: bool, batch_size: int) -> int:
    from shared.database.connection import get_db_connection_context
    from shared.pipeline_pass_marker import TERMINAL_PROCESSED_EMPTY_LEGITIMATE

    sql, params = _documents_event_tracking_pending_sql(pass_filter=True)
    iso = datetime.now(timezone.utc).isoformat()
    marked = 0
    with get_db_connection_context() as conn:
        if not conn:
            print("ERROR: no database connection", file=sys.stderr)
            return 0
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '300s'")
            cur.execute(sql, tuple(params))
            ids = [int(r[0]) for r in cur.fetchall()]
        if dry_run:
            return len(ids)
        if not ids:
            return 0
        for i in range(0, len(ids), batch_size):
            chunk = ids[i : i + batch_size]
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.contexts c
                    SET metadata = jsonb_set(
                            COALESCE(c.metadata::jsonb, '{}'::jsonb),
                            '{pipeline,event_tracking}',
                            jsonb_build_object(
                                'last_pass_at', %s::text,
                                'last_outcome', %s::text,
                                'last_terminal_state', %s::text
                            ),
                            true
                        ),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE c.id = ANY(%s)
                    """,
                    (iso, OUTCOME, TERMINAL_PROCESSED_EMPTY_LEGITIMATE, chunk),
                )
            conn.commit()
            marked += len(chunk)
            print(f"  marked {marked}/{len(ids)}")
    return marked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--floor",
        type=int,
        default=500,
        help="Max pipeline backlog per phase before allowing documents clear (default 500)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip pipeline backlog gate",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()

    pending = count_documents_pending()
    print(f"documents {PHASE} pending (pass-null, no chronicle): {pending}")

    ok, snap = gate_pipeline_clear(args.floor)
    print("Pipeline backlog snapshot:")
    for phase, n in snap.items():
        flag = "BLOCKED" if n > args.floor else "ok"
        print(f"  {phase}: {n} ({flag})")

    if not args.force and not ok:
        print(
            f"\nRefusing: pipeline backlogs still above floor={args.floor}. "
            "Finish catch-up first, or pass --force.",
            file=sys.stderr,
        )
        return 2

    if pending == 0:
        print("Nothing to clear.")
        return 0

    if args.dry_run:
        print(f"DRY RUN: would mark {pending} documents contexts as {OUTCOME}")
        return 0

    print(f"Marking {pending} contexts …")
    n = bulk_mark_documents(dry_run=False, batch_size=max(50, args.batch_size))
    after = count_documents_pending()
    print(f"Done: marked={n}, documents pending after={after}")
    return 0 if after == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
