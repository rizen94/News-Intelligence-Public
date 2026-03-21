"""
Entity profile sync service — Phase 1.3 context-centric.
Ensures every entity_canonical (per domain) has a row in intelligence.entity_profiles
and intelligence.old_entity_to_new. Required before context_entity_mentions can link contexts to profiles.
See docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md.
"""

import json
import logging

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


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
                    WHERE ec.canonical_name = ae.entity_name
                      AND ec.entity_type = ae.entity_type
                )
                ORDER BY ae.entity_name
            """)
            created = cur.rowcount

            if created > 0:
                cur.execute(f"""
                    UPDATE {schema}.article_entities ae
                    SET canonical_entity_id = ec.id
                    FROM {schema}.entity_canonical ec
                    WHERE ae.entity_name = ec.canonical_name
                      AND ae.entity_type = ec.entity_type
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
    For each row in {schema}.entity_canonical, ensure:
    - intelligence.entity_profiles (domain_key, canonical_entity_id, compilation_date, sections default)
    - intelligence.old_entity_to_new (domain_key, old_entity_id, entity_profile_id)
    Returns number of new profiles created.
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
                SELECT id, canonical_name, entity_type
                FROM {schema_name}.entity_canonical
                ORDER BY id
                """
            )
            canonicals = cur.fetchall()
            if not canonicals:
                conn.close()
                return 0

            for old_entity_id, canonical_name, entity_type in canonicals:
                # Already mapped?
                cur.execute(
                    """
                    SELECT entity_profile_id FROM intelligence.old_entity_to_new
                    WHERE domain_key = %s AND old_entity_id = %s
                    """,
                    (domain_key, old_entity_id),
                )
                if cur.fetchone():
                    continue

                # Insert entity_profiles row
                metadata = json.dumps(
                    {"canonical_name": canonical_name, "entity_type": entity_type}
                )
                cur.execute(
                    """
                    INSERT INTO intelligence.entity_profiles
                    (domain_key, canonical_entity_id, compilation_date, sections, relationships_summary, metadata)
                    VALUES (%s, %s, CURRENT_DATE, '[]', '[]', %s)
                    ON CONFLICT (domain_key, canonical_entity_id) DO UPDATE SET updated_at = NOW()
                    RETURNING id
                    """,
                    (domain_key, old_entity_id, metadata),
                )
                row = cur.fetchone()
                profile_id = row[0] if row else None
                if not profile_id:
                    cur.execute(
                        """
                        SELECT id FROM intelligence.entity_profiles
                        WHERE domain_key = %s AND canonical_entity_id = %s
                        """,
                        (domain_key, old_entity_id),
                    )
                    profile_id = cur.fetchone()[0]

                # Insert old_entity_to_new
                cur.execute(
                    """
                    INSERT INTO intelligence.old_entity_to_new (domain_key, old_entity_id, entity_profile_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (domain_key, old_entity_id) DO NOTHING
                    """,
                    (domain_key, old_entity_id, profile_id),
                )
                if cur.rowcount:
                    created += 1

            conn.commit()
        conn.close()
        if created > 0:
            logger.info(f"Entity profile sync {domain_key}: {created} new mappings created")
        # Backfill context_entity_mentions for existing contexts (article_entities now map to profiles)
        try:
            from services.context_processor_service import (
                backfill_context_entity_mentions_for_domain,
            )

            backfill_context_entity_mentions_for_domain(domain_key, limit=1000)
        except Exception as e:
            logger.debug(f"Entity profile sync backfill mentions: {e}")
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
