"""
Apply pending rows from intelligence.graph_connection_proposals.

- Storyline merge: DB merge when confidence >= MERGE_SIMILARITY_THRESHOLD (same bar as consolidation).
- Entity merge: repoint article_entities + drop duplicate canonical when confidence is high enough.
- Associate / hyperedge: materialize pairwise rows in intelligence.graph_connection_links (many-to-many).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

ENTITY_MERGE_EXECUTE_MIN = float(env_str("GRAPH_CONNECTION_ENTITY_MERGE_MIN", "0.88") or 0.88)
STORYLINE_LINK_ONLY_BELOW_MERGE = float(
    env_str("GRAPH_CONNECTION_STORYLINE_LINK_ONLY_MAX", "0.64") or 0.64
)


def process_graph_connection_proposals_batch(
    limit: int | None = None,
    proposal_ids: list[int] | None = None,
) -> dict[str, Any]:
    """
    Drain up to ``limit`` pending proposals (highest confidence first).
    When ``proposal_ids`` is set, only those pending rows are considered (desk accept).
    """
    from services.graph_connection_queue_service import (
        fetch_pending_proposals,
        insert_graph_connection_link_pair,
        mark_proposal_resolved,
        merge_edge_evidence,
    )
    from services.storyline_consolidation_service import MERGE_SIMILARITY_THRESHOLD, get_consolidation_service

    if proposal_ids:
        lim = max(1, min(len(proposal_ids), 50))
        rows = fetch_pending_proposals(
            limit=lim, min_confidence=0.0, proposal_ids=[int(x) for x in proposal_ids]
        )
    else:
        if limit is None:
            try:
                default = int(env_str("GRAPH_CONNECTION_DISTILLATION_BATCH", "50") or 50)
            except (TypeError, ValueError):
                default = 50
            try:
                from shared.adaptive_batch_policy import resolve_adaptive_batch

                lim, _meta = resolve_adaptive_batch("graph_connection_distillation", default)
            except Exception:
                lim = default
        else:
            lim = int(limit)
        lim = max(1, min(lim, 200))
        rows = fetch_pending_proposals(limit=lim, min_confidence=0.0)
    stats: dict[str, Any] = {
        "examined": len(rows),
        "batch_limit": lim,
        "storyline_merged": 0,
        "storyline_links": 0,
        "entity_merged": 0,
        "entity_links": 0,
        "cross_domain_links": 0,
        "topic_links": 0,
        "hyperedge_links": 0,
        "rejected": 0,
        "errors": [],
    }

    svc = get_consolidation_service()

    def _link_evidence(row: dict[str, Any], *, method: str) -> dict[str, Any]:
        return merge_edge_evidence(
            row.get("evidence") if isinstance(row.get("evidence"), dict) else {},
            phase=str(row.get("source") or "graph_connection_distillation"),
            method=method,
            score_parts={"overall": float(row.get("confidence") or 0.0)},
        )

    for row in rows:
        pid = int(row["id"])
        kind = str(row.get("proposal_kind") or "")
        conf = float(row.get("confidence") or 0.0)
        ep = row.get("endpoints") or {}
        domain_key = row.get("domain_key") or ep.get("domain_key")
        row_source = str(row.get("source") or "graph_connection_distillation")

        try:
            # Cross-domain associate: left/right domain-scoped endpoints
            if (
                kind == "associate"
                and isinstance(ep.get("left"), dict)
                and isinstance(ep.get("right"), dict)
            ):
                left, right = ep["left"], ep["right"]
                left_dk = str(left.get("domain_key") or "")
                right_dk = str(right.get("domain_key") or "")
                base_lk = str(left.get("kind") or "entity")
                base_rk = str(right.get("kind") or "entity")
                # Qualify kind with domain so same integer id is not a self-loop.
                lk = f"{base_lk}:{left_dk}" if left_dk else base_lk
                rk = f"{base_rk}:{right_dk}" if right_dk else base_rk
                try:
                    li, ri = int(left["id"]), int(right["id"])
                except (KeyError, TypeError, ValueError):
                    mark_proposal_resolved(pid, "rejected", "bad_cross_domain_endpoints")
                    stats["rejected"] += 1
                    continue
                if lk == rk and li == ri:
                    mark_proposal_resolved(pid, "rejected", "cross_domain_self_loop")
                    stats["rejected"] += 1
                    continue
                ev = _link_evidence(row, method="cross_domain_canonical")
                ev["anchors"] = {
                    **(ev.get("anchors") or {}),
                    "canonical_ids": ep.get("canonical_ids") or [],
                    "left_domain": left_dk,
                    "right_domain": right_dk,
                }
                insert_graph_connection_link_pair(
                    domain_key=None,
                    source_proposal_id=pid,
                    left_kind=lk,
                    left_id=li,
                    right_kind=rk,
                    right_id=ri,
                    link_role="associated_cross_domain",
                    confidence=conf,
                    evidence=ev,
                    source=row_source,
                )
                mark_proposal_resolved(pid, "auto_applied", "cross_domain_link_materialized")
                stats["cross_domain_links"] += 1
                continue

            if kind == "merge" and isinstance(ep.get("storyline_ids"), list):
                sids = [int(x) for x in ep["storyline_ids"]]
                if len(sids) != 2 or not domain_key:
                    mark_proposal_resolved(pid, "rejected", "bad_storyline_merge_endpoints")
                    stats["rejected"] += 1
                    continue
                try:
                    from services.domain_synthesis_config import get_domain_synthesis_config

                    if not get_domain_synthesis_config(str(domain_key)).link_score_profile.allow_storyline_merge:
                        # Chemistry kinds: edge-first — demote merge to associate link
                        insert_graph_connection_link_pair(
                            domain_key=str(domain_key),
                            source_proposal_id=pid,
                            left_kind="storyline",
                            left_id=sids[0],
                            right_kind="storyline",
                            right_id=sids[1],
                            link_role="associated_similarity",
                            confidence=conf,
                            evidence=_link_evidence(row, method="storyline_similarity_no_merge"),
                            source=row_source,
                        )
                        mark_proposal_resolved(
                            pid, "auto_applied", "edge_only_merge_disallowed_by_story_kind"
                        )
                        stats["storyline_links"] = int(stats.get("storyline_links") or 0) + 1
                        continue
                except Exception:
                    pass
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
                        evidence=_link_evidence(row, method="storyline_similarity"),
                        source=row_source,
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
                    # T2 ambiguous band — leave pending for editorial entity_disambig.
                    # Do not auto-materialize links (that emptied the pending feed).
                    stats.setdefault("left_pending_editorial", 0)
                    stats["left_pending_editorial"] += 1
                    continue

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
                    evidence=_link_evidence(row, method="topic_associate"),
                    source=row_source,
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
                            evidence=_link_evidence(row, method="hyperedge"),
                            source=row_source,
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
                link_role = "associated_similarity"
                ev_raw = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
                if str(ev_raw.get("link_role_intent") or "") == "associated":
                    link_role = "associated"
                insert_graph_connection_link_pair(
                    domain_key=str(domain_key),
                    source_proposal_id=pid,
                    left_kind="storyline",
                    left_id=sids[0],
                    right_kind="storyline",
                    right_id=sids[1],
                    link_role=link_role,
                    confidence=conf,
                    evidence=_link_evidence(row, method="cosine_chunk"),
                    source=row_source,
                )
                mark_proposal_resolved(pid, "auto_applied", "storyline_associate_link")
                stats["storyline_links"] += 1

            elif kind == "associate" and isinstance(ep.get("entity_ids"), list):
                # Co-occurrence / soft associates from link indexer — materialize pairwise
                # links so the pending queue drains (leaving them pending forever starved
                # higher-confidence multi-entity rows ahead of rejectable singles).
                # Legacy cross-domain rows without left/right: still within-domain pairs.
                eids = sorted({int(x) for x in ep["entity_ids"] if x is not None})
                if len(eids) < 2:
                    mark_proposal_resolved(pid, "rejected", "bad_entity_associate_endpoints")
                    stats["rejected"] += 1
                    continue
                if not domain_key:
                    domain_key = ep.get("domain_key")
                if not domain_key:
                    mark_proposal_resolved(pid, "rejected", "missing_domain_for_entity_associate")
                    stats["rejected"] += 1
                    continue
                pairs = 0
                # Cap fan-out: C(12,2)=66; larger sets still get a connected skeleton.
                pair_cap = 66
                for i in range(len(eids)):
                    for j in range(i + 1, len(eids)):
                        if pairs >= pair_cap:
                            break
                        if insert_graph_connection_link_pair(
                            domain_key=str(domain_key),
                            source_proposal_id=pid,
                            left_kind="entity",
                            left_id=eids[i],
                            right_kind="entity",
                            right_id=eids[j],
                            link_role="associated_cooccurrence",
                            confidence=conf,
                            evidence=_link_evidence(row, method="entity_jaccard"),
                            source=row_source,
                        ):
                            pairs += 1
                    if pairs >= pair_cap:
                        break
                mark_proposal_resolved(
                    pid, "auto_applied", f"entity_associate_pairs={pairs}"
                )
                stats["entity_links"] += pairs

            else:
                mark_proposal_resolved(pid, "rejected", f"unsupported_or_empty_kind={kind}")
                stats["rejected"] += 1

        except Exception as e:
            logger.warning("graph_connection processor row %s: %s", pid, e)
            stats["errors"].append({"id": pid, "msg": str(e)})
            mark_proposal_resolved(pid, "rejected", str(e)[:500])

    stats["processed"] = sum(
        int(stats.get(k) or 0)
        for k in (
            "storyline_merged",
            "storyline_links",
            "entity_merged",
            "entity_links",
            "cross_domain_links",
            "topic_links",
            "hyperedge_links",
            "rejected",
        )
    )
    return stats


def apply_graph_connection_proposal_by_id(
    proposal_id: int,
    *,
    force: bool = True,
) -> dict[str, Any]:
    """
    Desk/OWUI accept: apply one pending proposal.
    When force=True, bump confidence to 1.0 for the apply path so editor override wins thresholds.
    """
    from services.graph_connection_queue_service import get_proposal_by_id, mark_proposal_resolved

    row = get_proposal_by_id(int(proposal_id))
    if not row:
        return {"ok": False, "error": "not_found", "proposal_id": proposal_id}
    if str(row.get("status") or "") != "pending":
        return {
            "ok": False,
            "error": "not_pending",
            "proposal_id": proposal_id,
            "status": row.get("status"),
        }
    if force:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.graph_connection_proposals
                        SET confidence = GREATEST(confidence, 1.0),
                            evidence = COALESCE(evidence, '{}'::jsonb) || %s::jsonb,
                            updated_at = NOW()
                        WHERE id = %s AND status = 'pending'
                        """,
                        (json.dumps({"desk_force_accept": True}), int(proposal_id)),
                    )
                conn.commit()
            except Exception as e:
                logger.debug("force confidence bump: %s", e)
                try:
                    conn.rollback()
                except Exception:
                    pass
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
    stats = process_graph_connection_proposals_batch(proposal_ids=[int(proposal_id)])
    # Entity merge below threshold may leave pending — mark applied_manual if still pending
    again = get_proposal_by_id(int(proposal_id))
    if again and str(again.get("status") or "") == "pending" and force:
        mark_proposal_resolved(
            int(proposal_id),
            "applied_manual",
            "desk_agent_accept_left_pending_kind",
        )
        return {"ok": True, "proposal_id": proposal_id, "stats": stats, "forced_manual": True}
    ok = again is not None and str(again.get("status") or "") != "pending"
    return {
        "ok": ok,
        "proposal_id": proposal_id,
        "status": (again or {}).get("status"),
        "stats": stats,
    }


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
