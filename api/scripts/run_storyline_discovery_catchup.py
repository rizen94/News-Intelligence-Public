#!/usr/bin/env python3
"""
Bulk storyline discovery after entity/claim enrichment (resumable).

Gates on articles with terminal entity_extraction pass (output or legitimate empty).

  PYTHONPATH=api python3 api/scripts/run_storyline_discovery_catchup.py --dry-run
  PYTHONPATH=api python3 api/scripts/run_storyline_discovery_catchup.py --domains politics finance
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

CHECKPOINT = Path(__file__).resolve().parents[2] / "data" / "storyline_catchup_state.json"


def _eligible_article_count(schema: str) -> int:
    from shared.database.connection import get_db_connection_context
    from shared.pipeline_pass_marker import CLEARED_TERMINAL_STATES, sql_article_pass_null

    cleared = "', '".join(sorted(CLEARED_TERMINAL_STATES))
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {schema}.articles a
                WHERE NOT ({sql_article_pass_null('entity_extraction', 'a')})
                  AND NOT EXISTS (
                    SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.article_id = a.id
                  )
                  AND (
                    COALESCE(
                        a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                        ''
                    ) IN ('{cleared}')
                    OR (
                        (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at') IS NOT NULL
                        AND COALESCE(
                            a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state',
                            ''
                        ) = ''
                        AND (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_outcome')
                            IN ('entities_stored', 'skipped_short_text')
                    )
                  )
                """
            )
            return int(cur.fetchone()[0] or 0)


def main() -> int:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=True)
    parser = argparse.ArgumentParser(description="Storyline discovery catch-up")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--domains", nargs="*", default=None)
    args = parser.parse_args()

    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
    from services.ai_storyline_discovery import get_discovery_service

    domains = args.domains or list(get_pipeline_active_domain_keys())
    counts = {dk: _eligible_article_count(resolve_domain_schema(dk)) for dk in domains}
    print(json.dumps({"eligible_unlinked": counts}, indent=2))

    if args.dry_run:
        return 0

    svc = get_discovery_service()
    saved_total = 0
    for dk in domains:
        print(f"Running storyline discovery for {dk}...")
        result = svc.discover_storylines(domain=dk, hours=None, save_to_db=True)
        saved = len(result.get("saved_storylines") or [])
        saved_total += saved
        print(f"  saved_storylines: {saved}")

    state = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "domains": domains,
        "saved_total": saved_total,
        "eligible_before": counts,
    }
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT.write_text(json.dumps(state, indent=2), encoding="utf-8")
    print(f"Checkpoint: {CHECKPOINT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
