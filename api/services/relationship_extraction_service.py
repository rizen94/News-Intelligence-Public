"""
Relationship extraction service — extract entity relationships from context co-mentions.
Writes to intelligence.entity_relationships; supports network graph API.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPE_CO_MENTIONED = "co_mentioned"


def extract_relationships_from_contexts(
    context_ids: Optional[List[int]] = None,
    domain_key: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    From contexts (or context_ids), find entity pairs co-mentioned in the same context;
    map entity_profile_id -> (domain, canonical_entity_id) and insert into entity_relationships.
    Returns { extracted: N, relationship_ids: [...] }.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "extracted": 0, "relationship_ids": [], "error": "Database connection failed"}
    try:
        with conn.cursor() as cur:
            # Resolve entity_profile_id -> (domain_key, canonical_entity_id)
            cur.execute(
                """
                SELECT id, domain_key, canonical_entity_id FROM intelligence.entity_profiles
                """,
            )
            profile_to_domain_canonical: Dict[int, Tuple[str, int]] = {
                r[0]: (r[1], r[2]) for r in cur.fetchall()
            }
        if not profile_to_domain_canonical:
            conn.close()
            return {"success": True, "extracted": 0, "relationship_ids": []}

        # Co-mentions per context
        if context_ids:
            placeholders = ",".join(["%s"] * len(context_ids))
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT context_id, array_agg(DISTINCT entity_profile_id ORDER BY entity_profile_id) AS profile_ids
                    FROM intelligence.context_entity_mentions
                    WHERE context_id IN ({placeholders})
                    GROUP BY context_id
                    HAVING COUNT(DISTINCT entity_profile_id) >= 2
                    LIMIT %s
                    """,
                    (*context_ids, limit * 5),  # v8: historical depth
                )
                rows = cur.fetchall()
        else:
            domain_clause = "AND c.domain_key = %s" if domain_key else ""
            params: List[Any] = [limit * 5]  # v8: historical depth
            if domain_key:
                params.insert(0, domain_key)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cem.context_id, array_agg(DISTINCT cem.entity_profile_id ORDER BY cem.entity_profile_id) AS profile_ids
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE 1=1 """ + domain_clause + """
                    GROUP BY cem.context_id
                    HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                    ORDER BY cem.context_id DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        seen_pairs: Set[Tuple[Tuple[str, int], Tuple[str, int]]] = set()
        to_insert: List[Tuple[str, int, str, int, float]] = []
        for context_id, profile_ids in rows:
            if not profile_ids:
                continue
            profile_ids = list(profile_ids)
            for i in range(len(profile_ids)):
                for j in range(i + 1, len(profile_ids)):
                    a, b = profile_ids[i], profile_ids[j]
                    da = profile_to_domain_canonical.get(a)
                    db = profile_to_domain_canonical.get(b)
                    if not da or not db:
                        continue
                    (d1, id1), (d2, id2) = da, db
                    if (d1, id1) == (d2, id2):
                        continue
                    # Normalize order to avoid duplicate (A,B) and (B,A)
                    key = ((d1, id1), (d2, id2)) if (d1, id1) < (d2, id2) else ((d2, id2), (d1, id1))
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    to_insert.append((d1, id1, d2, id2, 0.75))

        if not to_insert:
            conn.close()
            return {"success": True, "extracted": 0, "relationship_ids": []}

        relationship_ids: List[int] = []
        with conn.cursor() as cur:
            for d1, id1, d2, id2, conf in to_insert:
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.entity_relationships
                        (source_domain, source_entity_id, target_domain, target_entity_id, relationship_type, confidence)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (d1, id1, d2, id2, RELATIONSHIP_TYPE_CO_MENTIONED, conf),
                    )
                    row = cur.fetchone()
                    if row:
                        relationship_ids.append(row[0])
                except Exception as e:
                    logger.debug("relationship insert skip: %s", e)
        try:
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.warning("relationship_extraction commit: %s", e)
        conn.close()
        return {"success": True, "extracted": len(relationship_ids), "relationship_ids": relationship_ids}
    except Exception as e:
        logger.warning("extract_relationships_from_contexts: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "extracted": 0, "relationship_ids": [], "error": str(e)}


def get_network_subgraph(
    domain: str,
    entity_id: int,
    depth: int = 2,
    relationship_types: Optional[List[str]] = None,
    limit_per_layer: int = 50,
) -> Dict[str, Any]:
    """
    BFS from (domain, entity_id) over entity_relationships. Returns nodes and edges.
    entity_id is entity_canonical id in the given domain.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "nodes": [], "edges": [], "error": "Database connection failed"}
    try:
        types_filter = ""
        type_args: Optional[List[str]] = None
        if relationship_types and "all" not in (relationship_types or []):
            types_filter = "AND relationship_type = ANY(%s)"
            type_args = relationship_types
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, int]] = {(domain, entity_id)}
        frontier: List[Tuple[str, int]] = [(domain, entity_id)]
        nodes.append({"domain": domain, "entity_id": entity_id})
        for _ in range(depth):
            if not frontier:
                break
            next_frontier: List[Tuple[str, int]] = []
            for src_domain, src_id in frontier:
                args_out: List[Any] = [src_domain, src_id]
                if type_args is not None:
                    args_out.append(type_args)
                args_out.append(limit_per_layer)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT target_domain, target_entity_id, relationship_type, confidence
                        FROM intelligence.entity_relationships
                        WHERE source_domain = %s AND source_entity_id = %s
                        """ + types_filter + """
                        LIMIT %s
                        """,
                        tuple(args_out),
                    )
                    for t_domain, t_id, rel_type, conf in cur.fetchall():
                        edges.append({
                            "source_domain": src_domain,
                            "source_entity_id": src_id,
                            "target_domain": t_domain,
                            "target_entity_id": t_id,
                            "relationship_type": rel_type,
                            "confidence": float(conf) if conf is not None else None,
                        })
                        key = (t_domain, t_id)
                        if key not in seen:
                            seen.add(key)
                            next_frontier.append(key)
                            nodes.append({"domain": t_domain, "entity_id": t_id})
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT source_domain, source_entity_id, relationship_type, confidence
                        FROM intelligence.entity_relationships
                        WHERE target_domain = %s AND target_entity_id = %s
                        """ + types_filter + """
                        LIMIT %s
                        """,
                        tuple(args_out),
                    )
                    for s_domain, s_id, rel_type, conf in cur.fetchall():
                        edges.append({
                            "source_domain": s_domain,
                            "source_entity_id": s_id,
                            "target_domain": src_domain,
                            "target_entity_id": src_id,
                            "relationship_type": rel_type,
                            "confidence": float(conf) if conf is not None else None,
                        })
                        key = (s_domain, s_id)
                        if key not in seen:
                            seen.add(key)
                            next_frontier.append(key)
                            nodes.append({"domain": s_domain, "entity_id": s_id})
            frontier = next_frontier[:limit_per_layer]
        conn.close()
        return {"success": True, "nodes": nodes, "edges": edges}
    except Exception as e:
        logger.warning("get_network_subgraph: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "nodes": [], "edges": [], "error": str(e)}
