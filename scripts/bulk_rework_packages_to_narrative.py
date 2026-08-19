#!/usr/bin/env python3
"""Bulk-rework editorial packages onto the Narrative rail.

Default: every non-published package that is not already in_narrative.
Intended for operator drains after fulltext rebuilds.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
os.chdir(ROOT / "api")

from shared.database.connection import get_db_connection_context  # noqa: E402


def _ids(*, include_statuses: list[str] | None, limit: int | None) -> list[int]:
    statuses = include_statuses or [
        "ready_for_editor",
        "draft",
        "in_research",
        "in_reduction",
        "in_editing",
    ]
    with get_db_connection_context() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id
            FROM intelligence.editorial_packages
            WHERE status = ANY(%s)
              AND status IS DISTINCT FROM 'published'
              AND status IS DISTINCT FROM 'in_narrative'
            ORDER BY id
            LIMIT %s
            """,
            (statuses, limit or 100000),
        )
        return [int(r[0]) for r in cur.fetchall()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="List package ids only; do not rework",
    )
    ap.add_argument("--limit", type=int, default=0, help="Max packages (0 = all)")
    ap.add_argument(
        "--note",
        default="bulk_rework→narrative fulltext_rebuild",
        help="Decision / handoff note",
    )
    ap.add_argument(
        "--actor",
        default="bulk_rework_narrative",
        help="Actor string for decisions",
    )
    ap.add_argument(
        "--kick-pass",
        action="store_true",
        help="After rework, run editorial_narrative_pass batch (if enabled)",
    )
    ap.add_argument(
        "--batch-limit",
        type=int,
        default=50,
        help="Max packages for --kick-pass drain",
    )
    args = ap.parse_args()
    limit = args.limit if args.limit > 0 else None
    ids = _ids(include_statuses=None, limit=limit)
    stamp = datetime.now(timezone.utc).isoformat()
    print(f"{stamp} candidates={len(ids)} dry_run={args.dry_run}")
    if not ids:
        return 0
    if args.dry_run:
        print("ids:", ",".join(str(i) for i in ids[:50]), ("..." if len(ids) > 50 else ""))
        return 0

    from services.modal_handoff_service import request_rework

    ok = 0
    err = 0
    for pid in ids:
        try:
            request_rework(
                pid,
                target_modal="narrative",
                note=args.note,
                actor=args.actor,
                source_modal="system",
            )
            ok += 1
            if ok % 50 == 0:
                print(f"  reworked {ok}/{len(ids)}...")
        except Exception as e:
            err += 1
            print(f"FAIL package_id={pid}: {e}", file=sys.stderr)
    print(f"done ok={ok} err={err}")

    if args.kick_pass:
        from services.editorial_package_narrative_service import run_narrative_batch

        result = run_narrative_batch(limit=args.batch_limit)
        print("narrative_batch:", result)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
