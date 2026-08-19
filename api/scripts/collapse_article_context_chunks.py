#!/usr/bin/env python3
"""
Collapse intelligence.contexts article_chunk rows into a single full-body
article context per domain article.

articles / contexts already use unbounded text — chunking was a processing
choice, not a storage limit. With CONTEXT_CHUNKING_ENABLED=false (default),
new articles get one context; this script repairs historical splits.

Usage (Widow, maintenance DB port):
  cd /opt/news-intelligence && set -a && source .env && set +a
  PYTHONPATH=api DB_PORT="${DB_MAINTENANCE_PORT:-5432}" \\
    .venv/bin/python api/scripts/collapse_article_context_chunks.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection  # noqa: E402
from shared.domain_registry import resolve_domain_schema  # noqa: E402

logger = logging.getLogger(__name__)
CHUNK_SUFFIX_RE = re.compile(r"\s*\[\d+/\d+\]\s*$")


def _base_title(title: str | None) -> str:
    return CHUNK_SUFFIX_RE.sub("", (title or "").strip())


def collapse(*, dry_run: bool) -> dict[str, int]:
    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no DB connection")

    stats = {
        "chunks_seen": 0,
        "primaries_refreshed": 0,
        "chronicle_relinked": 0,
        "chunks_deleted": 0,
        "orphans_deleted": 0,
    }

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, title, metadata
                FROM intelligence.contexts
                WHERE source_type = 'article_chunk'
                ORDER BY id
                """
            )
            chunks = cur.fetchall()
            stats["chunks_seen"] = len(chunks)

            # parent_article_id from metadata when present; else resolve via title match
            by_parent: dict[tuple[str, int], list[int]] = {}
            orphan_ids: list[int] = []

            for cid, domain_key, title, metadata in chunks:
                meta = metadata
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                if not isinstance(meta, dict):
                    meta = {}
                parent = meta.get("parent_article_id")
                if parent is None:
                    # Legacy: find article context with same base title in domain
                    base = _base_title(title)
                    cur.execute(
                        """
                        SELECT atc.article_id
                        FROM intelligence.contexts c
                        JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                        WHERE c.domain_key = %s
                          AND c.source_type = 'article'
                          AND regexp_replace(c.title, '\\s*\\[\\d+/\\d+\\]\\s*$', '') = %s
                        LIMIT 1
                        """,
                        (domain_key, base),
                    )
                    row = cur.fetchone()
                    if not row:
                        orphan_ids.append(int(cid))
                        continue
                    parent = int(row[0])
                key = (str(domain_key), int(parent))
                by_parent.setdefault(key, []).append(int(cid))

            for (domain_key, article_id), chunk_ids in by_parent.items():
                schema = resolve_domain_schema(domain_key)
                cur.execute(
                    """
                    SELECT context_id FROM intelligence.article_to_context
                    WHERE domain_key = %s AND article_id = %s
                    LIMIT 1
                    """,
                    (domain_key, article_id),
                )
                link = cur.fetchone()
                if not link:
                    orphan_ids.extend(chunk_ids)
                    continue
                primary_id = int(link[0])

                cur.execute(
                    f"""
                    SELECT title, content FROM {schema}.articles
                    WHERE id = %s
                    """,
                    (article_id,),
                )
                art = cur.fetchone()
                if not art:
                    orphan_ids.extend(chunk_ids)
                    continue
                title, content = art
                title = _base_title(title)[:2000]
                content = (content or "")[:500000]

                if not dry_run:
                    cur.execute(
                        """
                        UPDATE intelligence.contexts
                        SET title = %s,
                            content = %s,
                            raw_content = %s,
                            source_type = 'article',
                            metadata = (COALESCE(metadata::jsonb, '{}'::jsonb)
                              - 'chunk_index' - 'chunk_total'),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (title, content, content, primary_id),
                    )
                stats["primaries_refreshed"] += 1

                # PK is context_id: re-point chunk chronicle rows onto primary when free
                cur.execute(
                    """
                    SELECT context_id, event_id
                    FROM intelligence.event_chronicle_contexts
                    WHERE context_id = ANY(%s)
                    """,
                    (chunk_ids,),
                )
                for ctx_id, event_id in cur.fetchall() or []:
                    if dry_run:
                        stats["chronicle_relinked"] += 1
                        continue
                    cur.execute(
                        """
                        SELECT 1 FROM intelligence.event_chronicle_contexts
                        WHERE context_id = %s
                        """,
                        (primary_id,),
                    )
                    if cur.fetchone():
                        cur.execute(
                            """
                            DELETE FROM intelligence.event_chronicle_contexts
                            WHERE context_id = %s
                            """,
                            (ctx_id,),
                        )
                    else:
                        cur.execute(
                            """
                            UPDATE intelligence.event_chronicle_contexts
                            SET context_id = %s
                            WHERE context_id = %s
                            """,
                            (primary_id, ctx_id),
                        )
                    stats["chronicle_relinked"] += 1

                if not dry_run:
                    cur.execute(
                        "DELETE FROM intelligence.contexts WHERE id = ANY(%s)",
                        (chunk_ids,),
                    )
                stats["chunks_deleted"] += len(chunk_ids)

            # Orphan chunks with no resolvable parent
            if orphan_ids:
                # Relink chronicle away if possible is already skipped; just delete
                if not dry_run:
                    cur.execute(
                        """
                        DELETE FROM intelligence.event_chronicle_contexts
                        WHERE context_id = ANY(%s)
                        """,
                        (orphan_ids,),
                    )
                    cur.execute(
                        "DELETE FROM intelligence.contexts WHERE id = ANY(%s)",
                        (orphan_ids,),
                    )
                stats["orphans_deleted"] += len(orphan_ids)

            # Strip [n/m] suffixes left on primary article contexts
            if not dry_run:
                cur.execute(
                    """
                    UPDATE intelligence.contexts
                    SET title = regexp_replace(title, '\\s*\\[\\d+/\\d+\\]\\s*$', ''),
                        updated_at = NOW()
                    WHERE source_type = 'article'
                      AND title ~ '\\[\\d+/\\d+\\]\\s*$'
                    """
                )

            if dry_run:
                conn.rollback()
            else:
                conn.commit()
    finally:
        conn.close()

    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    stats = collapse(dry_run=args.dry_run)
    logger.info("%s %s", "DRY-RUN" if args.dry_run else "DONE", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
