"""Event embedding service — populates chronological_events(embedding) so dedup can match.

This module is the *only* place that writes non-null embeddings into the
chronological_events table.  Every insertion path (event_extraction_service,
rag/base GDELT, etc.) should call ``embed_and_store_text_rows`` after their
bulk INSERT so deduplication picks up immediately on the next tick.

Usage
-----

.. code-block:: python

    from services.event_embedding_service import embed_and_store_text_rows

    # After bulk INSERT of events:
    rows = [(evt["event_id"], evt["title"] + " " + (evt["description"] or "")) for evt in events]
    n_written = embed_and_store_text_rows(conn, rows)  # e.g. public.chronological_events
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def embed_and_store_chronological_events(
    conn: Any,
    text_rows: list[tuple[str, str]],
    table: str = "public.chronological_events",
) -> int:
    """Generate embeddings for *text_rows* and bulk-update them into the
    chronological_events(embedding) column.

    Parameters
    ----------
    conn : psycopg2 connection (or cursor-like with execute)
        Must be a live connection so we can issue UPDATE statements.
    text_rows : list[tuple[event_id, title+description]]
        Each tuple is (event_id string, text to embed).
    table : str
        Table name for the UPDATE (default: ``public.chronological_events``).

    Returns
    -------
    int
        Number of rows successfully updated with non-null embeddings.

    Notes
    -----
    * Embedding failures per-row are silently skipped — events remain
      insertable without blocking downstream pipelines.
    * A batch-level Ollama failure logs a warning but doesn't raise, so
      event ingestion never stalls on embedding.
    """
    if not text_rows:
        return 0

    from shared.services.llm_service import ollama_embed_sync

    # ------------------------------------------------------------------
    # 1. Generate embeddings (one-by-one via ollama_embed_sync)
    # ------------------------------------------------------------------
    results: list[tuple[str, list[float] | None]] = []  # (event_id, embedding_or_None)

    model_name = "nomic-embed-text"

    for event_id, text in text_rows:
        if not text or len(text.strip()) < 3:
            results.append((event_id, None))
            continue

        try:
            # Truncate to avoid Ollama token limits (safe — title+description >2000 chars is rare)
            emb = ollama_embed_sync(text[:2000], model=model_name)
            if emb and len(emb) > 0:
                results.append((event_id, emb))
            else:
                logger.debug("Embedding returned empty for event %s", event_id)
                results.append((event_id, None))
        except Exception as e:
            # Ollama pressure / connection errors — still log the event, skip embedding
            logger.debug("Failed to embed event '%s': %s", event_id, e)
            results.append((event_id, None))

    # ------------------------------------------------------------------
    # 2. Bulk UPDATE non-null embeddings back into chronological_events
    # ------------------------------------------------------------------
    non_null = [(eid, emb) for eid, emb in results if emb is not None]
    if not non_null:
        logger.info("No non-null embeddings to store for %d event(s)", len(text_rows))
        return 0

    try:
        cursor = conn.cursor()

        # Build parameter list for execute_values: (event_id, vector_json)
        values = [(eid, _vector_to_pg_array(emb)) for eid, emb in non_null]

        sql = f"""
            UPDATE {table}
            SET embedding = v.embedding
            FROM unnest(%s::uuid[], %s::text[]) AS v(event_id_col, embedding)
            WHERE {table}.event_id = v.event_id_col::text
              AND {table}.embedding IS NULL
        """

        event_ids = [v[0] for v in values]
        vectors = [v[1] for v in values]

        cursor.execute(
            sql,
            (event_ids, vectors),
        )
        updated = cursor.rowcount
        logger.info("Updated %d/%d chronological_events with embedding", updated, len(non_null))
        cursor.close()

    except Exception as e:
        logger.warning("Failed to bulk-update embeddings into %s: %s", table, e)

    return len(non_null)


def _vector_to_pg_array(vec: list[float]) -> str:
    """Convert a Python float list to a pgvector-compatible text array string."""
    dims = ",".join(f"{v:.10f}" for v in vec)
    return f"[{dims}]"


def fill_missing_chronological_embeddings(
    conn: Any,
    batch_size: int = 200,
    max_batches: int = 50,
) -> int:
    """Backfill NULL embeddings on all existing chronological_events rows.

    Useful as a **one-shot** migration after deploying Path A so the dedup
    service can match against historical rows (e.g., the ~57k unmerged
    backlog).

    Parameters
    ----------
    conn : psycopg2 connection
        Must be a live connection; each batch runs in its own transaction.
    batch_size : int
        Rows fetched per query.  Larger = fewer round-trips but more memory.
    max_batches : int
        Safety cap to avoid runaway scans on very large tables.

    Returns
    -------
    int
        Total rows updated across all batches.
    """
    total_updated = 0

    for batch_num in range(max_batches):
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT event_id, title, description FROM chronological_events WHERE embedding IS NULL ORDER BY id LIMIT %s",
                (batch_size,),
            )
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning("Backfill batch %d scan failed: %s", batch_num + 1, e)
            cursor.close()
            break
        else:
            cursor.close()

        if not rows:
            break  # No more NULL-embedding rows

        text_rows = [
            (rid, f"{(t or '').strip()} {(d or '').strip()}".strip())
            for rid, t, d in rows
        ]

        try:
            updated = embed_and_store_chronological_events(conn, text_rows)
            total_updated += updated
            logger.info(
                "Backfill batch %d/%d: embedded %d events (total: %d)",
                batch_num + 1,
                max_batches,
                updated,
                total_updated,
            )
        except Exception as e:
            logger.warning("Backfill batch %d embed failed: %s", batch_num + 1, e)

    return total_updated


def fill_missing_gdelt_events_embeddings(
    conn: Any,
    batch_size: int = 200,
    max_batches: int = 50,
) -> int:
    """Backfill NULL embeddings on GDELT-sourced events in chronological_events.

    Same as ``fill_missing_chronological_embeddings`` but scoped to
    extraction_method = 'gdelt' rows so we don't re-embed non-GDELT events.
    """
    from psycopg2.extras import execute_values

    total_updated = 0
    model_name = "nomic-embed-text"

    for batch_num in range(max_batches):
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT event_id, title, description
                FROM chronological_events
                WHERE extraction_method = 'gdelt'
                  AND embedding IS NULL
                ORDER BY id
                LIMIT %s
                """,
                (batch_size,),
            )
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning("GDELT backfill batch %d scan failed: %s", batch_num + 1, e)
            cursor.close()
            break
        else:
            cursor.close()

        if not rows:
            break

        text_rows = [
            (rid, f"{(t or '').strip()} {(d or '').strip()}".strip())
            for rid, t, d in rows
        ]

        try:
            updated = embed_and_store_chronological_events(conn, text_rows)
            total_updated += updated
            logger.info(
                "GDELT backfill batch %d/%d: embedded %d events (total: %d)",
                batch_num + 1,
                max_batches,
                updated,
                total_updated,
            )
        except Exception as e:
            logger.warning("GDELT backfill batch %d embed failed: %s", batch_num + 1, e)

    return total_updated
