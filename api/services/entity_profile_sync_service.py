"""
Entity profile sync service — Phase 1.3 context-centric.
Ensures every entity_canonical (per domain) has a row in intelligence.entity_profiles
and intelligence.old_entity_to_new. Required before context_entity_mentions can link contexts to profiles.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging
import os

from typing import Any

from api.shared.domain_registry import resolve_domain_schema

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
    from api.shared.database import get_db_connection

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
    from api.shared.database import get_db_connection

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


def sync_cross_domain_priorities() -> dict[str, Any]:
    """Full reconciliation of multi_domain_priority across all entity profiles.

    Unsets all flags, then re-computes which entities appear in >= 2 domains
    via context_entity_mentions and cross_domain_correlations. Returns a summary dict.
    """
    from api.shared.database import get_db_connection

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "No DB connection", "multi_domain_count": 0}

    total_flagged = 0
    try:
        with conn.cursor() as cur:
            # Step 1: Unset all flags first (full reconciliation)
            cur.execute(
                "UPDATE intelligence.entity_profiles SET multi_domain_priority = FALSE"
            )
            unset_count = cur.rowcount or 0

            # Step 2: Compute entities present in >= 2 domains from mentions
            cur.execute(
                """
                SELECT entity_profile_id, COUNT(DISTINCT c.domain_key) AS dom_count
                FROM intelligence.context_entity_mentions cem
                JOIN intelligence.contexts c ON c.id = cem.context_id
                GROUP BY entity_profile_id
                HAVING COUNT(DISTINCT c.domain_key) >= 2
                """
            )
            from_mentions = {r[0] for r in cur.fetchall()}

            # Step 3: Compute entities present in correlations spanning >= 2 domains
            cur.execute(
                """
                SELECT DISTINCT UNNEST(entity_profile_ids) AS ep_id
                FROM intelligence.cross_domain_correlations
                WHERE domain_1 IS NOT NULL AND domain_2 IS NOT NULL
                  AND domain_1 != domain_2
                  AND array_length(source_context_ids, 1) > 0
                """
            )
            from_correlations = {r[0] for r in cur.fetchall()}

            # Union of both sources
            multi_domain_ids = from_mentions | from_correlations
            total_flagged = len(multi_domain_ids)

            if multi_domain_ids:
                ids_sql = tuple(multi_domain_ids[:500])
                cur.execute(
                    """
                    UPDATE intelligence.entity_profiles ep
                    SET multi_domain_priority = TRUE
                    WHERE ep.id = ANY(%s)
                    """,
                    (ids_sql,),
                )
                flagged_rows = cur.rowcount or 0
            else:
                flagged_rows = 0

            conn.commit()
        conn.close()

        logger.info(
            "sync_cross_domain_priorities: unset=%s, multi-domain entities flagged=%s (from_mentions=%d, from_correlations=%d)",
            unset_count,
            total_flagged,
            len(from_mentions),
            len(from_correlations),
        )
        return {
            "success": True,
            "unset_count": unset_count,
            "multi_domain_count": total_flagged,
            "flags_from_mentions": len(from_mentions),
            "flags_from_correlations": len(from_correlations),
        }

    except Exception as e:
        logger.warning("sync_cross_domain_priorities failed: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e), "multi_domain_count": 0}


def sync_cross_domain_priorities_for_domain(domain_key: str) -> int:
    """Lightweight per-domain variant: flag entities that have mentions in this domain plus >=1 others.

    Useful when called at the end of `sync_domain_entity_profiles` to avoid full reconciliation cost.
    Returns count of newly flagged entities.
    """
    from api.shared.database import get_db_connection

    conn = get_db_connection()
    if not conn:
        return 0

    newly_flagged = 0
    try:
        with conn.cursor() as cur:
            # Find entity profiles in this domain that appear in >= 2 domains total
            schema = _schema_for_domain(domain_key)
            cur.execute(
                f"""
                SELECT ec.id AS canonical_id
                FROM {schema}.entity_canonical ec
                WHERE ec.id IN (
                    SELECT ep.canonical_entity_id
                    FROM intelligence.entity_profiles ep
                    WHERE ep.domain_key = %s
                      AND EXISTS (
                        SELECT 1 FROM intelligence.context_entity_mentions cem2
                        JOIN intelligence.contexts c2 ON c2.id = cem2.context_id
                        WHERE cem2.entity_profile_id = ep.id
                          AND c2.domain_key != %s
                      )
                )
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.entity_profiles ep2
                    WHERE ep2.canonical_entity_id = ec.id
                      AND ep2.multi_domain_priority = TRUE
                  )
                """,
                (domain_key, domain_key),
            )
            new_candidates = cur.fetchall()

            if not new_candidates:
                return 0

            ids_to_flag = []
            for row in new_candidates:
                canon_id = row[0]
                # Find the entity_profile_id that matches this canonical ID
                cur.execute(
                    """
                    SELECT ep.id FROM intelligence.entity_profiles ep
                    WHERE ep.canonical_entity_id = %s AND ep.domain_key = %s
                    """,
                    (canon_id, domain_key),
                )
                r2 = cur.fetchone()
                if r2:
                    ids_to_flag.append(r2[0])

            newly_flagged = len(ids_to_flag)
            if ids_to_flag:
                ids_sql = tuple(ids_to_flag[:100])
                cur.execute(
                    """
                    UPDATE intelligence.entity_profiles ep
                    SET multi_domain_priority = TRUE
                    WHERE ep.id = ANY(%s) AND ep.multi_domain_priority = FALSE
                    """,
                    (ids_sql,),
                )

            conn.commit()
        conn.close()
        if newly_flagged > 0:
            logger.info(
                "sync_cross_domain_priorities_for_domain %s: %d new entities flagged",
                domain_key,
                newly_flagged,
            )
        return newly_flagged

    except Exception as e:
        logger.warning("sync_cross_domain_priorities_for_domain %s failed: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return 0

        return 0
