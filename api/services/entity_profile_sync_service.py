"""
Entity profile sync service — Phase 1.3 context-centric.
Ensures every entity_canonical (per domain) has a row in intelligence.entity_profiles
and intelligence.old_entity_to_new. Required before context_entity_mentions can link contexts to profiles.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
import os

from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)


def _mention_backfill_limit() -> int:
    """Contexts per domain to refresh per round (link_context_to_article_entities)."""
    try:
        return max(50, int(os.environ.get("ENTITY_PROFILE_SYNC_MENTION_BACKFILL_LIMIT", "10000")))
    except ValueError:
        return 10_000


def _mention_backfill_rounds() -> int:
    try:
        return max(1, min(50, int(os.environ.get("ENTITY_PROFILE_SYNC_MENTION_BACKFILL_ROUNDS", "3"))))
    except ValueError:
        return 3


def _schema_for_domain(domain_key: str) -> str:
    return resolve_domain_schema(domain_key)


def backfill_entity_canonical(domain_key: str) -> int:
    """
    Populate {schema}.entity_canonical from distinct entity names in
    {schema}.article_entities that don't yet have a canonical row.
    Returns number of new canonical entities created.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.warning("backfill_entity_canonical: no DB connection")
        return 0

    schema = _schema_for_domain(domain_key)
    created = 0
    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO {schema}.entity_canonical (canonical_name, entity_type)
                SELECT DISTINCT ae.entity_name, ae.entity_type
                FROM {schema}.article_entities ae
                WHERE NOT EXISTS (
                    SELECT 1 FROM {schema}.entity_canonical ec
                    WHERE lower(trim(ec.canonical_name)) = lower(trim(ae.entity_name))
                      AND ec.entity_type IS NOT DISTINCT FROM ae.entity_type
                )
                ORDER BY ae.entity_name
            """)
            created = cur.rowcount

            cur.execute(f"""
                UPDATE {schema}.article_entities ae
                SET canonical_entity_id = ec.id
                FROM {schema}.entity_canonical ec
                WHERE lower(trim(ae.entity_name)) = lower(trim(ec.canonical_name))
                  AND ae.entity_type IS NOT DISTINCT FROM ec.entity_type
                  AND ae.canonical_entity_id IS NULL
            """)

            conn.commit()
        conn.close()
        if created > 0:
            logger.info(
                f"backfill_entity_canonical {domain_key}: {created} canonical entities created"
            )
        return created
    except Exception as e:
        logger.warning(f"backfill_entity_canonical {domain_key} failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0


def sync_domain_entity_profiles(domain_key: str) -> int:
    """
    For each row in {schema}.entity_canonical lacking ``old_entity_to_new``, ensure:
    - intelligence.entity_profiles (domain_key, canonical_entity_id, …)
    - intelligence.old_entity_to_new (domain_key, old_entity_id, entity_profile_id)

    Uses two bulk SQL statements (no per-row round trips). Returns the number of **new**
    ``old_entity_to_new`` rows inserted.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.warning("Entity profile sync: no DB connection")
        return 0

    schema_name = _schema_for_domain(domain_key)
    created = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO intelligence.entity_profiles
                    (domain_key, canonical_entity_id, compilation_date, sections, relationships_summary, metadata)
                SELECT %s, ec.id, CURRENT_DATE, '[]', '[]',
                    to_jsonb(json_build_object(
                        'canonical_name', ec.canonical_name,
                        'entity_type', ec.entity_type
                    ))
                FROM {schema_name}.entity_canonical ec
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.old_entity_to_new o
                    WHERE o.domain_key = %s AND o.old_entity_id = ec.id
                )
                ON CONFLICT (domain_key, canonical_entity_id)
                DO UPDATE SET updated_at = NOW()
                """,
                (domain_key, domain_key),
            )

            cur.execute(
                f"""
                INSERT INTO intelligence.old_entity_to_new (domain_key, old_entity_id, entity_profile_id)
                SELECT %s, ec.id, ep.id
                FROM {schema_name}.entity_canonical ec
                INNER JOIN intelligence.entity_profiles ep
                  ON ep.domain_key = %s AND ep.canonical_entity_id = ec.id
                WHERE NOT EXISTS (
                    SELECT 1 FROM intelligence.old_entity_to_new o
                    WHERE o.domain_key = %s AND o.old_entity_id = ec.id
                )
                """,
                (domain_key, domain_key, domain_key),
            )
            created = cur.rowcount or 0

            conn.commit()
        conn.close()
        if created > 0:
            logger.info(f"Entity profile sync {domain_key}: {created} new mappings created")
        try:
            from services.context_processor_service import (
                backfill_context_entity_mentions_for_domain,
            )

            lim = _mention_backfill_limit()
            rounds = _mention_backfill_rounds()
            total_bf = 0
            for _ in range(rounds):
                n = backfill_context_entity_mentions_for_domain(domain_key, limit=lim)
                total_bf += n
                if n <= 0:
                    break
            if total_bf > 0:
                logger.info(
                    "Entity profile sync %s: context_entity_mentions rounds=%s updated_contexts≈%s (limit/round=%s)",
                    domain_key,
                    rounds,
                    total_bf,
                    lim,
                )
        except Exception as e:
            logger.debug("Entity profile sync backfill mentions: %s", e)
        return created
    except Exception as e:
        logger.warning(f"Entity profile sync {domain_key} failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0
