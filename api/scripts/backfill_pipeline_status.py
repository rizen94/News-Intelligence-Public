#!/usr/bin/env python3
"""Backfill intelligence.pipeline_status from articles.metadata.pipeline (v10.1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_schema_names_active

PHASES = (
    "unified_intake_extraction",
    "content_enrichment",
    "entity_extraction",
    "topic_clustering",
    "link_indexer",
)


def main() -> int:
    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for schema in get_schema_names_active():
                for phase in PHASES:
                    try:
                        cur.execute(
                            f"""
                            INSERT INTO intelligence.pipeline_status (
                                schema_name, article_id, phase_name, outcome, terminal_state, updated_at, metadata
                            )
                            SELECT
                                %s,
                                a.id,
                                %s,
                                a.metadata->'pipeline'->%s->>'last_outcome',
                                a.metadata->'pipeline'->%s->>'last_terminal_state',
                                COALESCE(
                                    NULLIF(a.metadata->'pipeline'->%s->>'last_pass_at', '')::timestamptz,
                                    NOW()
                                ),
                                '{{"backfilled": true}}'::jsonb
                            FROM {schema}.articles a
                            WHERE (a.metadata->'pipeline'->%s->>'last_pass_at') IS NOT NULL
                              AND NOT EXISTS (
                                  SELECT 1 FROM intelligence.pipeline_status ps
                                  WHERE ps.schema_name = %s AND ps.article_id = a.id AND ps.phase_name = %s
                              )
                            LIMIT 50000
                            """,
                            (schema, phase, phase, phase, phase, phase, schema, phase),
                        )
                        n += cur.rowcount or 0
                    except Exception as exc:
                        print(f"skip {schema}.{phase}: {exc}", file=sys.stderr)
            conn.commit()
    print(f"backfilled rows: {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
