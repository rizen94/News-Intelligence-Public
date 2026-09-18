"""
Relationship extraction service — extract entity relationships from context co-mentions.
Writes to intelligence.entity_relationships; supports network graph API.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from typing import Any

from shared.database.connection import get_db_connection
from shared.entity_relationships_store import UPSERT_ENTITY_RELATIONSHIP_SQL, normalize_edge

logger = logging.getLogger(__name__)

RELATIONSHIP_TYPE_CO_MENTIONED = "co_mentioned"
RELATIONSHIP_EXTRACTION_PHASE = "relationship_extraction"


def _relationship_pass_sql(alias: str = "c") -> str:
    from shared.pipeline_pass_marker import phase_backlog_uses_pass_marker, sql_context_pass_null

    if phase_backlog_uses_pass_marker(RELATIONSHIP_EXTRACTION_PHASE):
        return f" AND ({sql_context_pass_null(RELATIONSHIP_EXTRACTION_PHASE, alias)}) "
    return ""


def _record_context_relationship_passes(
    context_outcomes: dict[int, tuple[int, int]],
) -> None:
    """Record pass markers for contexts scanned in this batch."""
    if not context_outcomes:
        return
    try:
        from shared.pipeline_pass_marker import (
            infer_relationship_extraction_terminal,
            phase_backlog_uses_pass_marker,
            record_context_phase_pass,
        )

        if not phase_backlog_uses_pass_marker(RELATIONSHIP_EXTRACTION_PHASE):
            return
        for context_id, (pairs_materialized, profile_count) in context_outcomes.items():
            terminal, outcome = infer_relationship_extraction_terminal(
                pairs_materialized=pairs_materialized,
                profile_count=profile_count,
            )
            record_context_phase_pass(
                context_id,
                RELATIONSHIP_EXTRACTION_PHASE,
                outcome,
                terminal_state=terminal,
            )
    except Exception as e:
        logger.debug("record context relationship passes: %s", e)


def extract_relationships_from_contexts(
    context_ids: list[int] | None = None,
    domain_key: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """
    From contexts (or context_ids), find entity pairs co-mentioned in the same context;
    map entity_profile_id -> (domain, canonical_entity_id) and upsert into entity_relationships.
    Skips contexts already marked in metadata.pipeline.relationship_extraction when pass markers on.
    Returns { extracted: N, relationship_ids: [...], contexts_processed: N }.
    """
    conn = get_db_connection()
    if not conn:
        return {
            "success": False,
            "extracted": 0,
            "relationship_ids": [],
            "contexts_processed": 0,
            "error": "Database connection failed",
        }
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, canonical_entity_id FROM intelligence.entity_profiles
                """,
            )
            profile_to_domain_canonical: dict[int, tuple[str, int]] = {
                r[0]: (r[1], r[2]) for r in cur.fetchall()
            }
        if not profile_to_domain_canonical:
            conn.close()
            return {"success": True, "extracted": 0, "relationship_ids": [], "contexts_processed": 0}

        pass_sql = "" if context_ids else _relationship_pass_sql("c")
        if context_ids:
            placeholders = ",".join(["%s"] * len(context_ids))
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT cem.context_id, array_agg(DISTINCT cem.entity_profile_id ORDER BY cem.entity_profile_id) AS profile_ids
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE cem.context_id IN ({placeholders})
                    {pass_sql}
                    GROUP BY cem.context_id
                    HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                    LIMIT %s
                    """,
                    (*context_ids, limit * 5),
                )
                rows = cur.fetchall()
        else:
            domain_clause = "AND c.domain_key = %s" if domain_key else ""
            params: list[Any] = [limit * 5]
            if domain_key:
                params.insert(0, domain_key)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT cem.context_id, array_agg(DISTINCT cem.entity_profile_id ORDER BY cem.entity_profile_id) AS profile_ids
                    FROM intelligence.context_entity_mentions cem
                    JOIN intelligence.contexts c ON c.id = cem.context_id
                    WHERE 1=1 """
                    + domain_clause
                    + pass_sql
                    + """
                    GROUP BY cem.context_id
                    HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                    ORDER BY cem.context_id DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        if not rows:
            conn.close()
            return {"success": True, "extracted": 0, "relationship_ids": [], "contexts_processed": 0}

        seen_pairs: set[tuple[tuple[str, int], tuple[str, int]]] = set()
        to_insert: list[tuple[str, int, str, int, float]] = []
        context_outcomes: dict[int, tuple[int, int]] = {}

        for context_id, profile_ids in rows:
            if not profile_ids:
                continue
            profile_ids = list(profile_ids)
            profile_count = len(profile_ids)
            pairs_materialized = 0
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
                    d1, id1, d2, id2 = normalize_edge(d1, id1, d2, id2)
                    key = ((d1, id1), (d2, id2))
                    if key in seen_pairs:
                        pairs_materialized += 1
                        continue
                    seen_pairs.add(key)
                    pairs_materialized += 1
                    to_insert.append((d1, id1, d2, id2, 0.75))
            context_outcomes[context_id] = (pairs_materialized, profile_count)

        relationship_ids: list[int] = []
        upserted = 0
        if to_insert:
            with conn.cursor() as cur:
                for d1, id1, d2, id2, conf in to_insert:
                    try:
                        cur.execute(
                            UPSERT_ENTITY_RELATIONSHIP_SQL,
                            (d1, id1, d2, id2, RELATIONSHIP_TYPE_CO_MENTIONED, conf),
                        )
                        row = cur.fetchone()
                        if row:
                            relationship_ids.append(row[0])
                            upserted += 1
                    except Exception as e:
                        logger.debug("relationship upsert skip: %s", e)
            try:
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.warning("relationship_extraction commit: %s", e)
                conn.close()
                return {
                    "success": False,
                    "extracted": 0,
                    "relationship_ids": [],
                    "contexts_processed": 0,
                    "error": str(e),
                }

        _record_context_relationship_passes(context_outcomes)
        conn.close()
        return {
            "success": True,
            "extracted": upserted,
            "relationship_ids": relationship_ids,
            "contexts_processed": len(context_outcomes),
        }
    except Exception as e:
        logger.warning("extract_relationships_from_contexts: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {
            "success": False,
            "extracted": 0,
            "relationship_ids": [],
            "contexts_processed": 0,
            "error": str(e),
        }


def get_context_ids_pending_relationship_extraction(
    domain_key: str | None = None,
    limit: int = 50,
) -> list[int]:
    """Contexts with 2+ entity mentions and no cleared relationship_extraction pass marker."""
    conn = get_db_connection()
    if not conn:
        return []
    pass_sql = _relationship_pass_sql("c")
    domain_clause = "AND c.domain_key = %s" if domain_key else ""
    params: list[Any] = [limit]
    if domain_key:
        params.insert(0, domain_key)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT cem.context_id
                FROM intelligence.context_entity_mentions cem
                JOIN intelligence.contexts c ON c.id = cem.context_id
                WHERE 1=1 """
                + domain_clause
                + pass_sql
                + """
                GROUP BY cem.context_id
                HAVING COUNT(DISTINCT cem.entity_profile_id) >= 2
                ORDER BY cem.context_id DESC
                LIMIT %s
                """,
                tuple(params),
            )
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def get_network_subgraph(
    domain: str,
    entity_id: int,
    depth: int = 2,
    relationship_types: list[str] | None = None,
    limit_per_layer: int = 50,
) -> dict[str, Any]:
    """
    BFS from (domain, entity_id) over entity_relationships. Returns nodes and edges.
    entity_id is entity_canonical id in the given domain.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "nodes": [], "edges": [], "error": "Database connection failed"}
    try:
        types_filter = ""
        type_args: list[str] | None = None
        if relationship_types and "all" not in (relationship_types or []):
            types_filter = "AND relationship_type = ANY(%s)"
            type_args = relationship_types
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = {(domain, entity_id)}
        frontier: list[tuple[str, int]] = [(domain, entity_id)]
        nodes.append({"domain": domain, "entity_id": entity_id})
        for _ in range(depth):
            if not frontier:
                break
            next_frontier: list[tuple[str, int]] = []
            for src_domain, src_id in frontier:
                args_out: list[Any] = [src_domain, src_id]
                if type_args is not None:
                    args_out.append(type_args)
                args_out.append(limit_per_layer)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT target_domain, target_entity_id, relationship_type, confidence
                        FROM intelligence.entity_relationships
                        WHERE source_domain = %s AND source_entity_id = %s
                        """
                        + types_filter
                        + """
                        LIMIT %s
                        """,
                        tuple(args_out),
                    )
                    for t_domain, t_id, rel_type, conf in cur.fetchall():
                        edges.append(
                            {
                                "source_domain": src_domain,
                                "source_entity_id": src_id,
                                "target_domain": t_domain,
                                "target_entity_id": t_id,
                                "relationship_type": rel_type,
                                "confidence": float(conf) if conf is not None else None,
                            }
                        )
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
                        """
                        + types_filter
                        + """
                        LIMIT %s
                        """,
                        tuple(args_out),
                    )
                    for s_domain, s_id, rel_type, conf in cur.fetchall():
                        edges.append(
                            {
                                "source_domain": s_domain,
                                "source_entity_id": s_id,
                                "target_domain": src_domain,
                                "target_entity_id": src_id,
                                "relationship_type": rel_type,
                                "confidence": float(conf) if conf is not None else None,
                            }
                        )
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
