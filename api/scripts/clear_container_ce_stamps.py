#!/usr/bin/env python3
"""
Clear chronological_events.storyline_id that point at container_index / mega
storylines, and soft-reset continuation backoff so they can rematch episodes.

  PYTHONPATH=api python3 api/scripts/clear_container_ce_stamps.py --dry-run
  PYTHONPATH=api python3 api/scripts/clear_container_ce_stamps.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("clear_container_ce_stamps")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true", default=True)
    args = ap.parse_args()
    apply = bool(args.apply)
    cleared = 0
    reset = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT ce.id
                    FROM public.chronological_events ce
                    JOIN {schema}.storylines s
                      ON ce.storyline_id ~ '^[0-9]+$'
                     AND s.id = ce.storyline_id::int
                    WHERE COALESCE(s.story_kind, '') = 'container_index'
                       OR COALESCE(s.is_mega_storyline, FALSE) = TRUE
                    """
                )
                ids = [int(r[0]) for r in (cur.fetchall() or [])]
                logger.info("[%s] ce_on_containers=%s", dk, len(ids))
                if not ids or not apply:
                    continue
                cur.execute(
                    """
                    UPDATE public.chronological_events
                    SET storyline_id = '',
                        continuation_attempts = 0,
                        continuation_checked_at = NULL
                    WHERE id = ANY(%s)
                    """,
                    (ids,),
                )
                n = cur.rowcount
                cleared += n
                reset += n
            if apply:
                conn.commit()
    print(json.dumps({"apply": apply, "cleared": cleared, "backoff_reset": reset}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
