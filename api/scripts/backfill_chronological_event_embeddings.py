#!/usr/bin/env python3
"""Backfill NULL embeddings on chronological_events rows using Ollama nomic-embed-text.

Run **once** after deploying Path A so the dedup service can match against historical
rows (the ~57k unmerged backlog).

Examples:
    # All events (any extraction_method):
      PYTHONPATH=api uv run python api/scripts/backfill_chronological_event_embeddings.py

    # GDELT-sourced events only (default -- narrowest scope):
      PYTHONPATH=api uv run python api/scripts/backfill_chronological_event_embeddings.py --gdelt-only

    # Custom batch sizes / safety cap:
      PYTHONPATH=api uv run python api/scripts/backfill_chronological_event_embeddings.py --batch-size 500 --max-batches 120

"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
ROOT = API_DIR.parent
sys.path.insert(0, str(API_DIR))
sys.path.insert(0, str(ROOT))
import contextlib

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("backfill_event_embeddings")


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / "configs" / ".env", override=False)
        load_dotenv(ROOT / ".env", override=False)
        load_dotenv(API_DIR / ".env", override=False)
    except Exception:
        pass
    if not os.environ.get("DB_PASSWORD"):
        for candidate in (ROOT / ".db_password_widow", Path.home() / ".db_password_widow"):
            if candidate.is_file():
                os.environ["DB_PASSWORD"] = candidate.read_text().strip()
                break


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill NULL embeddings on chronological_events rows.",
    )
    parser.add_argument("--gdelt-only", action="store_true", help="Only backfill GDELT-sourced events")
    parser.add_argument("--batch-size", type=int, default=200, help="Rows per batch (default: 200)")
    parser.add_argument("--max-batches", type=int, default=50, help="Safety cap on batches (default: 50)")
    args = parser.parse_args()

    _load_env()

    logger.info(
        "Starting backfill  scope=%s batch_size=%d max_batches=%d",
        "GDELT-only" if args.gdelt_only else "all events",
        args.batch_size,
        args.max_batches,
    )

    from services.event_embedding_service import (
        fill_missing_chronological_embeddings,
        fill_missing_gdelt_events_embeddings,
    )

    with contextlib.nullcontext() as conn:
        from api.shared.database import get_db_connection_context

        with get_db_connection_context() as conn:
            if args.gdelt_only:
                total = fill_missing_gdelt_events_embeddings(
                    conn, batch_size=args.batch_size, max_batches=args.max_batches
                )
            else:
                total = fill_missing_chronological_embeddings(
                    conn, batch_size=args.batch_size, max_batches=args.max_batches
                )

    logger.info("Backfill complete — %d rows updated with embeddings.", total)


if __name__ == "__main__":
    main()