"""
Apply pending rows from intelligence.graph_connection_proposals.

- Storyline merge: DB merge when confidence >= MERGE_SIMILARITY_THRESHOLD (same bar as consolidation).
- Entity merge: repoint article_entities + drop duplicate canonical when confidence is high enough.
- Associate / hyperedge: materialize pairwise rows in intelligence.graph_connection_links (many-to-many).
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

ENTITY_MERGE_EXECUTE_MIN = float(os.environ.get("GRAPH_CONNECTION_ENTITY_MERGE_MIN", "0.88") or 0.88)
STORYLINE_LINK_ONLY_BELOW_MERGE = float(
    os.environ.get("GRAPH_CONNECTION_STORYLINE_LINK_ONLY_MAX", "0.64") or 0.64
)


def process_graph_connection_proposals_batch(
    limit: int | None = None,
) -> dict[str, Any]:
    """
    Drain up to ``limit`` pending proposals (highest confidence first).
    """
    from services.graph_connection_queue_service import (
        fetch_pending_proposals,
        insert_graph_connection_link_pair,
        mark_proposal_resolved,
    )
    from services.storyline_consolidation_service import MERGE_SIMILARITY_THRESHOLD, get_consolidation_service

    lim = limit if limit is not None else int(os.environ.get("GRAPH_CONNECTION_DISTILLATION_BATCH", "12") or 12)
    lim = max(1, min(lim, 100))

    rows = fetch_pending_proposals(limit=lim, min_confidence=0.0)
    stats: dict[str, Any] = {
        "examined": len(rows),
        "storyline_merged": 0,
        "storyline_links": 0,
        "entity_merged": 0,
        "entity_links": 0,
        "topic_links": 0,
        "hyperedge_links": 0,
        "rejected": 0,
        "errors": [],
    }

    svc = get_consolidation_service()

    for row in rows:
        pid = int(row["id"])
        kind = str(row.get("proposal_kind") or "")
        conf = float(row.get("confidence") or 0.0)
        ep = row.get("endpoints") or {}
        domain_key = row.get("domain_key") or ep.get("domain_key")

        try:
            if kind == "merge" and isinstance(ep.get("storyline_ids"), list):
                sids = [int(x) for x in ep["storyline_ids"]]
                if len(sids) != 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_storyline_merge_endpoints")
                    stats["rejected"] += 1
                    continue
                a, b = sids[0], sids[1]
                evp = row.get("evidence") or {}
                pa, sb = evp.get("primary_storyline_id"), evp.get("secondary_storyline_id")
                if pa is not None and sb is not None:
                    primary_id, secondary_id = int(pa), int(sb)
                else:
                    primary_id, secondary_id = (a, b) if a <= b else (b, a)
                if conf >= MERGE_SIMILARITY_THRESHOLD:
                    out = svc.merge_storylines_by_ids(
                        str(domain_key), primary_id, secondary_id, conf
                    )
                    if out:
                        from services.graph_connection_queue_service import mark_storyline_merge_applied

                        mark_storyline_merge_applied(str(domain_key), primary_id, secondary_id)
                        mark_proposal_resolved(pid, "auto_applied", f"merged_into={primary_id}")
                        stats["storyline_merged"] += 1
                    else:
                        mark_proposal_resolved(pid, "rejected", "merge_storylines_by_ids_noop")
                        stats["rejected"] += 1
                elif conf > STORYLINE_LINK_ONLY_BELOW_MERGE:
                    insert_graph_connection_link_pair(
                        domain_key=str(domain_key),
                        source_proposal_id=pid,
                        left_kind="storyline",
                        left_id=a,
                        right_kind="storyline",
                        right_id=b,
                        link_role="associated_similarity",
                        confidence=conf,
                    )
                    mark_proposal_resolved(pid, "auto_applied", "materialized_storyline_link_only")
                    stats["storyline_links"] += 1
                else:
                    mark_proposal_resolved(pid, "rejected", "below_storyline_link_materialize_threshold")
                    stats["rejected"] += 1

            elif kind == "merge" and isinstance(ep.get("entity_ids"), list):
                eids = [int(x) for x in ep["entity_ids"]]
                if len(eids) != 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_entity_merge_endpoints")
                    stats["rejected"] += 1
                    continue
                ev = row.get("evidence") or {}
                if ev.get("keep_canonical_id") is not None and ev.get("merge_canonical_id") is not None:
                    keep = int(ev["keep_canonical_id"])
                    drop = int(ev["merge_canonical_id"])
                else:
                    keep, drop = min(eids), max(eids)
                if conf >= ENTITY_MERGE_EXECUTE_MIN:
                    if _apply_entity_merge(str(domain_key), keep, drop):
                        mark_proposal_resolved(pid, "auto_applied", f"entity_merged_into={keep}")
                        stats["entity_merged"] += 1
                    else:
                        mark_proposal_resolved(pid, "rejected", "entity_merge_failed")
                        stats["rejected"] += 1
                else:
                    insert_graph_connection_link_pair(
                        domain_key=str(domain_key),
                        source_proposal_id=pid,
                        left_kind="entity",
                        left_id=eids[0],
                        right_kind="entity",
                        right_id=eids[1],
                        link_role="associated_merge_candidate",
                        confidence=conf,
                    )
                    mark_proposal_resolved(pid, "auto_applied", "entity_link_only_low_confidence")
                    stats["entity_links"] += 1

            elif kind == "associate" and isinstance(ep.get("topic_ids"), list):
                tids = [int(x) for x in ep["topic_ids"]]
                if len(tids) != 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_topic_associate_endpoints")
                    stats["rejected"] += 1
                    continue
                insert_graph_connection_link_pair(
                    domain_key=str(domain_key),
                    source_proposal_id=pid,
                    left_kind="topic",
                    left_id=tids[0],
                    right_kind="topic",
                    right_id=tids[1],
                    link_role="associated",
                    confidence=conf,
                )
                mark_proposal_resolved(pid, "auto_applied", "topic_link_materialized")
                stats["topic_links"] += 1

            elif kind == "hyperedge" and isinstance(ep.get("storyline_ids"), list):
                sids = sorted(set(int(x) for x in ep["storyline_ids"]))
                if len(sids) < 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_hyperedge_endpoints")
                    stats["rejected"] += 1
                    continue
                pairs = 0
                for i in range(len(sids)):
                    for j in range(i + 1, len(sids)):
                        if insert_graph_connection_link_pair(
                            domain_key=str(domain_key),
                            source_proposal_id=pid,
                            left_kind="storyline",
                            left_id=sids[i],
                            right_kind="storyline",
                            right_id=sids[j],
                            link_role="hyperedge_cluster",
                            confidence=conf,
                        ):
                            pairs += 1
                stats["hyperedge_links"] += pairs
                mark_proposal_resolved(pid, "auto_applied", f"hyperedge_pairs={pairs}")

            elif kind == "associate" and isinstance(ep.get("storyline_ids"), list):
                sids = [int(x) for x in ep["storyline_ids"]]
                if len(sids) != 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_storyline_associate_endpoints")
                    stats["rejected"] += 1
                    continue
                insert_graph_connection_link_pair(
                    domain_key=str(domain_key),
                    source_proposal_id=pid,
                    left_kind="storyline",
                    left_id=sids[0],
                    right_kind="storyline",
                    right_id=sids[1],
                    link_role="associated",
                    confidence=conf,
                )
                mark_proposal_resolved(pid, "auto_applied", "storyline_associate_link")
                stats["storyline_links"] += 1

            else:
                mark_proposal_resolved(pid, "rejected", f"unsupported_or_empty_kind={kind}")
                stats["rejected"] += 1

        except Exception as e:
            logger.warning("graph_connection processor row %s: %s", pid, e)
            stats["errors"].append({"id": pid, "msg": str(e)})
            mark_proposal_resolved(pid, "rejected", str(e)[:500])

    return stats


def _apply_entity_merge(domain_key: str, keep_id: int, drop_id: int) -> bool:
    """Repoint article_entities then remove duplicate canonical (same transaction pattern as cleanup)."""
    from shared.database.connection import get_db_connection
    from shared.domain_registry import resolve_domain_schema

    if keep_id == drop_id:
        return False
    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT 1 FROM {schema}.entity_canonical WHERE id = %s",
                (drop_id,),
            )
            if not cur.fetchone():
                return True
            cur.execute(
                f"""
                UPDATE {schema}.article_entities
                SET canonical_entity_id = %s
                WHERE canonical_entity_id = %s
                """,
                (keep_id, drop_id),
            )
            from services.intelligence_cleanup_controller import IntelligenceCleanupController

            IntelligenceCleanupController()._delete_canonical_ids(cur, schema, domain_key, [drop_id])
        conn.commit()
        return True
    except Exception as e:
        logger.warning("entity merge apply %s keep=%s drop=%s: %s", domain_key, keep_id, drop_id, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
