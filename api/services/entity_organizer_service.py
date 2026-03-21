"""
Entity organizer service — cleanup, relationship extraction, and key-entity maintenance.

Runs as part of the data collection pipeline (after entities are collected and identified)
and during downtime between data loads: merges duplicate entities, prunes low-value ones,
and generates relationship "vectors" (entity_relationships from co-mentions) so the graph
stays current. Can be invoked by AutomationManager (entity_organizer phase) or by the
downtime loop that runs between rss/article/entity_extraction loads.

See docs/ENTITY_GROUPING_AND_KEY_TARGETS.md.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default batch sizes per cycle (tune for latency vs throughput)
DEFAULT_RELATIONSHIP_LIMIT = 100
DEFAULT_DOWNTIME_RELATIONSHIP_LIMIT = 50


def run_cycle(
    domain_key: str | None = None,
    relationship_limit: int = DEFAULT_RELATIONSHIP_LIMIT,
    cleanup_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Run one organizer cycle: intelligence cleanup (merge duplicates, prune, cap)
    then relationship extraction (co-mentions -> entity_relationships).

    Returns combined stats for pipeline/downtime loop reporting.
    """
    result: dict[str, Any] = {
        "cleanup": {},
        "relationships_extracted": 0,
        "errors": [],
    }
    # 1. Cleanup: merge duplicate entities, prune low-value, cap count
    try:
        from services.intelligence_cleanup_controller import IntelligenceCleanupController

        controller = IntelligenceCleanupController(policy=cleanup_policy)
        cleanup_out = controller.run(domain_key=domain_key)
        result["cleanup"] = cleanup_out
    except Exception as e:
        logger.warning("Entity organizer cleanup: %s", e)
        result["errors"].append(f"cleanup: {e!s}")

    # 2. Relationship extraction: co-mentions -> entity_relationships (vectors between entities)
    try:
        from services.relationship_extraction_service import extract_relationships_from_contexts

        rel_out = extract_relationships_from_contexts(
            domain_key=domain_key,
            limit=relationship_limit,
        )
        if rel_out.get("success"):
            result["relationships_extracted"] = rel_out.get("extracted", 0)
        else:
            result["errors"].append(rel_out.get("error", "relationship extraction failed"))
    except Exception as e:
        logger.warning("Entity organizer relationship extraction: %s", e)
        result["errors"].append(f"relationships: {e!s}")

    return result


def get_key_entities(
    domain_key: str | None = None,
    limit: int = 100,
    min_mentions: int = 2,
) -> dict[str, Any]:
    """
    Return a ranked list of entities by mention count (recurring / key targets).
    Uses entity_canonical + article_entities counts; does not require a cache table.
    """
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return {"success": False, "entities": [], "error": "Database connection failed"}

    domains: list[str] = [domain_key] if domain_key else ["politics", "finance", "science-tech"]
    schema_map = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}
    entities: list[dict[str, Any]] = []

    try:
        with conn.cursor() as cur:
            for d in domains:
                schema = schema_map.get(d, d.replace("-", "_"))
                cur.execute(f"SET search_path TO {schema}, public")
                cur.execute(
                    """
                    SELECT ec.id, ec.canonical_name, ec.entity_type,
                           COUNT(ae.id) AS mention_count
                    FROM entity_canonical ec
                    LEFT JOIN article_entities ae ON ae.canonical_entity_id = ec.id
                    GROUP BY ec.id, ec.canonical_name, ec.entity_type
                    HAVING COUNT(ae.id) >= %s
                    ORDER BY mention_count DESC
                    LIMIT %s
                    """,
                    (min_mentions, limit),
                )
                for row in cur.fetchall():
                    entities.append(
                        {
                            "domain_key": d,
                            "canonical_entity_id": row[0],
                            "canonical_name": row[1],
                            "entity_type": row[2],
                            "mention_count": row[3],
                        }
                    )
        conn.close()
        # Sort across domains by mention_count and trim to limit
        entities.sort(key=lambda x: x["mention_count"], reverse=True)
        return {"success": True, "entities": entities[:limit], "total": len(entities)}
    except Exception as e:
        logger.warning("get_key_entities: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "entities": [], "error": str(e)}
