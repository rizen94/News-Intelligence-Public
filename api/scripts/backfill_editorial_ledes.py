#!/usr/bin/env python3
"""One-time backfill: re-sanitize editorial_document lede fields in active domain schemas.

Uses a direct Postgres session (not the API connection pools). On Widow, when ``DB_PORT=6432``
(PgBouncer), connects to ``5432`` unless ``DB_MAINTENANCE_PORT`` is set — avoids
``max_client_conn`` errors while the API is running.
"""

from __future__ import annotations

import json
import logging
import os
import sys

_API_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _maintenance_connect():
    """Direct psycopg2 session — bypasses ThreadedConnectionPool and PgBouncer when local."""
    import psycopg2

    host = os.getenv("DB_HOST", "127.0.0.1")
    env_port = os.getenv("DB_PORT", "5432")
    if os.getenv("DB_MAINTENANCE_PORT"):
        port = int(os.getenv("DB_MAINTENANCE_PORT", "5432"))
    elif host in ("127.0.0.1", "localhost") and env_port == "6432":
        port = 5432
        logger.info(
            "DB_PORT=6432 (PgBouncer); using direct Postgres :5432 for maintenance script"
        )
    else:
        port = int(env_port)

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=os.getenv("DB_NAME", "news_intel"),
        user=os.getenv("DB_USER", "newsapp"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
    )


def _pipeline_schema_names(conn) -> list[str]:
    """Active pipeline schemas from public.domains (no domain_registry import)."""
    exclude_raw = os.getenv("PIPELINE_EXCLUDE_DOMAIN_KEYS", "").strip()
    exclude = frozenset(x.strip().lower() for x in exclude_raw.split(",") if x.strip())
    include_raw = os.getenv("PIPELINE_INCLUDE_DOMAIN_KEYS", "").strip()
    include: frozenset[str] | None = None
    if include_raw:
        include = frozenset(
            x.strip().lower().replace("_", "-")
            for x in include_raw.split(",")
            if x.strip()
        )

    schemas: list[str] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT domain_key, schema_name
            FROM public.domains
            WHERE is_active IS TRUE
            ORDER BY display_order NULLS LAST, domain_key
            """
        )
        rows = cur.fetchall()

    for domain_key, schema_name in rows:
        dk = str(domain_key or "").strip().lower()
        sch = str(schema_name or "").strip()
        if not dk or not sch:
            continue
        if include is not None and dk not in include:
            continue
        if dk in exclude:
            continue
        schemas.append(sch)

    if schemas:
        return schemas

    logger.warning(
        "public.domains empty or filtered — falling back to politics, finance if present"
    )
    fallback: list[str] = []
    with conn.cursor() as cur:
        for sch in ("politics", "finance"):
            cur.execute(
                """
                SELECT 1 FROM information_schema.schemata WHERE schema_name = %s
                """,
                (sch,),
            )
            if cur.fetchone():
                fallback.append(sch)
    return fallback


def main() -> int:
    from shared.llm_text_sanitize import sanitize_briefing_lede

    conn = _maintenance_connect()
    updated = 0
    try:
        schemas = _pipeline_schema_names(conn)
        if not schemas:
            logger.error("No active domain schemas found")
            return 1

        logger.info("Backfill schemas: %s", ", ".join(schemas))
        for schema in schemas:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, editorial_document
                    FROM {schema}.storylines
                    WHERE editorial_document IS NOT NULL
                      AND editorial_document != '{{}}'::jsonb
                    """
                )
                rows = cur.fetchall()
            schema_updates = 0
            for sid, ed in rows:
                if not isinstance(ed, dict):
                    continue
                raw_lede = ed.get("lede") or ""
                clean = sanitize_briefing_lede(raw_lede, max_length=500)
                if not clean or clean == raw_lede:
                    continue
                new_ed = dict(ed)
                new_ed["lede"] = clean
                if ed.get("analysis") and ed.get("analysis") == raw_lede:
                    new_ed["analysis"] = sanitize_briefing_lede(
                        ed.get("analysis"), max_length=400
                    )
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET editorial_document = %s::jsonb
                        WHERE id = %s
                        """,
                        (json.dumps(new_ed), sid),
                    )
                schema_updates += 1
            conn.commit()
            updated += schema_updates
            logger.info(
                "Schema %s: %s storyline(s) updated (%s scanned)",
                schema,
                schema_updates,
                len(rows),
            )
    finally:
        conn.close()
    logger.info("Backfill complete — %s storylines updated", updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
