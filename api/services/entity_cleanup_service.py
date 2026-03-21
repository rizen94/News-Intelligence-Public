"""
Entity cleanup service — removes noise entities and merges case-duplicates.
Operates on {schema}.entity_canonical, then cascades to intelligence.entity_profiles
and intelligence.old_entity_to_new.
"""

import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}

GENERIC_FRAGMENTS = [
    "no name",
    "mentioned",
    "unknown",
    "n/a",
    "not specified",
    "unnamed",
    "unidentified",
]


def _schema(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def _is_noise(name: str, entity_type: str) -> bool:
    """Return True if the entity is noise that should be removed."""
    stripped = name.strip()
    if len(stripped) < 2:
        return True
    if re.match(r"^[\d,.\s%$€£]+$", stripped):
        return True
    if len(stripped) > 80:
        return True
    if any(g in stripped.lower() for g in GENERIC_FRAGMENTS):
        return True
    if entity_type == "person" and re.match(r"^\d", stripped):
        return True
    if entity_type == "person" and len(stripped) > 60:
        return True
    return False


def cleanup_domain_entities(domain_key: str) -> dict:
    """
    Clean up entities for a domain:
    1. Remove noise entities from entity_canonical
    2. Merge case-duplicates (keep the first, redirect references)
    3. Cascade deletions to intelligence.entity_profiles and old_entity_to_new

    Returns summary stats.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.warning("entity_cleanup: no DB connection")
        return {"error": "no_db_connection"}

    schema = _schema(domain_key)
    stats = {"noise_removed": 0, "duplicates_merged": 0, "profiles_removed": 0}

    try:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT id, canonical_name, entity_type
                FROM {schema}.entity_canonical
                ORDER BY id
            """)
            all_rows = cur.fetchall()

            if not all_rows:
                conn.close()
                return stats

            noise_ids = []
            clean_rows = []
            for row_id, name, etype in all_rows:
                if _is_noise(name, etype):
                    noise_ids.append(row_id)
                else:
                    clean_rows.append((row_id, name, etype))

            # --- Step 1: Remove noise ---
            if noise_ids:
                cur.execute(
                    f"""
                    UPDATE {schema}.article_entities
                    SET canonical_entity_id = NULL
                    WHERE canonical_entity_id = ANY(%s)
                """,
                    (noise_ids,),
                )

                cur.execute(
                    """
                    DELETE FROM intelligence.old_entity_to_new
                    WHERE domain_key = %s AND old_entity_id = ANY(%s)
                """,
                    (domain_key, noise_ids),
                )

                cur.execute(
                    """
                    DELETE FROM intelligence.entity_profiles
                    WHERE domain_key = %s AND canonical_entity_id = ANY(%s)
                """,
                    (domain_key, noise_ids),
                )

                cur.execute(
                    f"""
                    DELETE FROM {schema}.entity_canonical
                    WHERE id = ANY(%s)
                """,
                    (noise_ids,),
                )
                stats["noise_removed"] = len(noise_ids)

            # --- Step 2: Merge case-duplicates ---
            by_lower = defaultdict(list)
            for row_id, name, etype in clean_rows:
                by_lower[(name.lower().strip(), etype)].append((row_id, name))

            for (_, _), entries in by_lower.items():
                if len(entries) < 2:
                    continue
                keep_id = entries[0][0]
                merge_ids = [e[0] for e in entries[1:]]

                cur.execute(
                    f"""
                    UPDATE {schema}.article_entities
                    SET canonical_entity_id = %s
                    WHERE canonical_entity_id = ANY(%s)
                """,
                    (keep_id, merge_ids),
                )

                cur.execute(
                    """
                    DELETE FROM intelligence.old_entity_to_new
                    WHERE domain_key = %s AND old_entity_id = ANY(%s)
                """,
                    (domain_key, merge_ids),
                )

                cur.execute(
                    """
                    DELETE FROM intelligence.entity_profiles
                    WHERE domain_key = %s AND canonical_entity_id = ANY(%s)
                """,
                    (domain_key, merge_ids),
                )

                cur.execute(
                    f"""
                    DELETE FROM {schema}.entity_canonical
                    WHERE id = ANY(%s)
                """,
                    (merge_ids,),
                )

                stats["duplicates_merged"] += len(merge_ids)

            stats["profiles_removed"] = stats["noise_removed"] + stats["duplicates_merged"]

        conn.commit()
        conn.close()
        logger.info(
            f"entity_cleanup {domain_key}: removed {stats['noise_removed']} noise, "
            f"merged {stats['duplicates_merged']} duplicates"
        )
        return stats
    except Exception as e:
        logger.error(f"entity_cleanup {domain_key} failed: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"error": str(e)}
