#!/usr/bin/env python3
"""Seed spine work queues from current scan-based pending articles (v10.1)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.database.connection import get_db_connection_context
from shared.domain_registry import pipeline_url_schema_pairs
from services.spine_work_queue_service import enqueue_article


def main() -> int:
    enriched = 0
    intake = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for _dk, schema in pipeline_url_schema_pairs():
                try:
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.articles
                        WHERE (enrichment_status IS NULL OR enrichment_status IN ('pending', 'failed'))
                          AND COALESCE(enrichment_attempts, 0) < 3
                          AND url IS NOT NULL AND url != ''
                        LIMIT 5000
                        """
                    )
                    for (aid,) in cur.fetchall():
                        if enqueue_article(schema, int(aid), "content_enrichment"):
                            enriched += 1
                except Exception:
                    pass
    print(f"enqueued content_enrichment={enriched} unified_intake={intake}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
