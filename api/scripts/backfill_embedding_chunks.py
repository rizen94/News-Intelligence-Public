#!/usr/bin/env python3
"""
Backfill intelligence.embedding_chunks for contexts/articles (resumable).

  PYTHONPATH=api python3 api/scripts/backfill_embedding_chunks.py --dry-run
  PYTHONPATH=api python3 api/scripts/backfill_embedding_chunks.py --limit 500
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

CHECKPOINT = Path(__file__).resolve().parents[2] / "data" / "embedding_backfill_state.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill embedding_chunks")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--loops", type=int, default=100)
    args = parser.parse_args()

    from shared.database.connection import get_db_connection_context
    from services.embeddings_worker_service import run_embeddings_worker_batch

    state = {}
    if CHECKPOINT.is_file():
        try:
            state = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM intelligence.embedding_chunks")
            before = int(cur.fetchone()[0] or 0)

    print(f"embedding_chunks before: {before}")
    if args.dry_run:
        print(f"would run up to {args.loops} batches of {args.limit}")
        return 0

    total = 0
    for i in range(args.loops):
        n = int(run_embeddings_worker_batch(limit=args.limit) or 0)
        total += n
        print(f"  batch {i + 1}: embedded {n}")
        if n == 0:
            break

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM intelligence.embedding_chunks")
            after = int(cur.fetchone()[0] or 0)

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["chunks_before"] = before
    state["chunks_after"] = after
    state["batches_run"] = i + 1 if total else 0
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"embedding_chunks after: {after} (+{after - before})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
