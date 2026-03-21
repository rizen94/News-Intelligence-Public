"""
Story state update trigger service — processes fact_change_log and story_update_queue.
When versioned_facts are inserted, a DB trigger logs to fact_change_log. This service:
1. Processes unprocessed fact_change_log: resolves entity_profile -> domain + canonical name,
   finds storylines via story_entity_index, enqueues story_update_queue.
2. Processes story_update_queue: batches by (domain_key, storyline_id), calls story state updater.
See docs/STORY_STATE_UPDATE_TRIGGERS.md.
"""

import logging

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def process_fact_change_log(batch_size: int = 100) -> int:
    """
    Process unprocessed fact_change_log rows: resolve entity_profile to domain + canonical name,
    find storylines via story_entity_index, insert into story_update_queue. Mark log rows processed.
    Production: 100-change batches, ~2s each; if behind >10k consider alert and skip to recent.
    Returns number of log rows processed.
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("story_state_trigger: no DB connection")
        return 0

    processed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, fact_id, entity_profile_id, change_type
                FROM intelligence.fact_change_log
                WHERE processed = FALSE
                ORDER BY changed_at ASC
                LIMIT %s
                """,
                (batch_size,),
            )
            rows = cur.fetchall()
        if not rows:
            conn.close()
            return 0

        for log_id, fact_id, entity_profile_id, change_type in rows:
            triggered = _process_one_fact_change(
                conn, log_id, fact_id, entity_profile_id, change_type
            )
            if triggered is not None:
                processed += 1
                with conn.cursor() as cur2:
                    cur2.execute(
                        """
                        UPDATE intelligence.fact_change_log
                        SET processed = TRUE, processed_at = NOW(), story_updates_triggered = %s
                        WHERE id = %s
                        """,
                        (triggered, log_id),
                    )
        conn.commit()
    except Exception as e:
        logger.warning("process_fact_change_log failed: %s", e, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return processed


def _process_one_fact_change(
    conn, log_id: int, fact_id: int, entity_profile_id: int, change_type: str
) -> int | None:
    """Resolve entity_profile -> (domain_key, canonical_name), find storylines, enqueue. Returns count enqueued or None on error."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ep.domain_key, ep.canonical_entity_id, ep.metadata->>'canonical_name'
            FROM intelligence.entity_profiles ep
            WHERE ep.id = %s
            """,
            (entity_profile_id,),
        )
        row = cur.fetchone()
    if not row:
        logger.debug(
            "fact_change_log %s: entity_profile_id %s not found", log_id, entity_profile_id
        )
        return 0
    domain_key, canonical_entity_id, canonical_name = row
    if not domain_key:
        return 0
    schema = _schema_for_domain(domain_key)
    # Prefer canonical name from metadata; else fetch from entity_canonical
    if not (canonical_name or "").strip() and canonical_entity_id is not None:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT canonical_name FROM {schema}.entity_canonical WHERE id = %s",
                    (canonical_entity_id,),
                )
                r = cur.fetchone()
                if r:
                    canonical_name = r[0]
        except Exception as e:
            logger.debug("entity_canonical lookup %s: %s", schema, e)
    name = (canonical_name or "").strip()
    if not name:
        return 0
    # Find storylines: story_entity_index by entity_name (try domain schema then public)
    storyline_ids: set[int] = set()
    for try_schema in (schema, "public"):
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT storyline_id FROM {try_schema}.story_entity_index
                    WHERE LOWER(entity_name) = LOWER(%s)
                    """,
                    (name[:255],),
                )
                for (sid,) in cur.fetchall():
                    storyline_ids.add(sid)
        except Exception as e:
            if "does not exist" not in str(e).lower():
                logger.debug("story_entity_index %s: %s", try_schema, e)
    if not storyline_ids:
        return 0
    # Priority from change_type (could later use fact confidence)
    priority = "high" if change_type == "new_fact" else "medium"
    trigger_id = str(fact_id)
    enqueued = 0
    with conn.cursor() as cur:
        for sid in storyline_ids:
            try:
                cur.execute(
                    """
                    INSERT INTO intelligence.story_update_queue
                    (domain_key, storyline_id, trigger_type, trigger_id, priority)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (domain_key, sid, change_type, trigger_id, priority),
                )
                enqueued += cur.rowcount
            except Exception as e:
                logger.debug("story_update_queue insert skip: %s", e)
    return enqueued


def process_story_update_queue(batch_size: int = 20) -> int:
    """
    Process unprocessed story_update_queue rows: dedupe by (domain_key, storyline_id),
    then call story state updater for each. Mark queue rows processed.
    Returns number of queue rows processed.
    """
    conn = get_db_connection()
    if not conn:
        logger.warning("story_state_trigger: no DB connection")
        return 0

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, storyline_id, trigger_type, trigger_id, priority
                FROM intelligence.story_update_queue
                WHERE processed = FALSE
                ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, created_at ASC
                LIMIT %s
                """,
                (batch_size,),
            )
            rows = cur.fetchall()
        if not rows:
            conn.close()
            return 0

        # Dedupe by (domain_key, storyline_id), keep set of (domain_key, storyline_id)
        seen: set[tuple[str, int]] = set()
        to_update: list[tuple[str, int]] = []
        for _id, domain_key, storyline_id, _trigger_type, _trigger_id, _priority in rows:
            key = (domain_key, storyline_id)
            if key not in seen:
                seen.add(key)
                to_update.append((domain_key, storyline_id))
        for domain_key, storyline_id in to_update:
            _update_story_state(conn, domain_key, storyline_id)
        # Mark all fetched rows as processed
        ids = [r[0] for r in rows]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE intelligence.story_update_queue SET processed = TRUE, processed_at = NOW() WHERE id = ANY(%s)",
                (ids,),
            )
        conn.commit()
        return len(rows)
    except Exception as e:
        logger.warning("process_story_update_queue failed: %s", e, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _update_story_state(conn, domain_key: str, storyline_id: int) -> None:
    """Update story state: write storyline_states row with maturity score and knowledge gaps (Phase 2)."""
    try:
        from services.story_state_service import update_story_state

        update_story_state(domain_key, storyline_id)
    except Exception as e:
        logger.debug("story state update %s/%s: %s", domain_key, storyline_id, e)
