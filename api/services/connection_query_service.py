"""Canned connection queries for agents, API, and graph projection."""

from __future__ import annotations

import logging
from typing import Any

from config.runtime import env_int
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from services.linkage_coverage_service import get_linkage_coverage

logger = logging.getLogger(__name__)


def orphan_summary() -> dict[str, Any]:
    """High-level orphan / linkage gaps (alias for linkage coverage global block)."""
    cov = get_linkage_coverage()
    if not cov.get("success"):
        return cov
    return {
        "success": True,
        "summary": cov.get("global") or {},
        "domains": [
            {
                "domain_key": d.get("domain_key"),
                "eel_link_pct": d.get("eel_link_pct"),
                "te_bridge_pct": d.get("te_bridge_pct"),
                "duplicate_title_groups": d.get("duplicate_title_groups"),
                "orphan_ce_in_domain": (
                    int(d.get("chronological_events_in_domain") or 0)
                    - int(d.get("chronological_events_linked") or 0)
                ),
            }
            for d in cov.get("domains") or []
        ],
    }


def event_connections(event_id: int) -> dict[str, Any]:
    """Chronological event → EEL → episode → narrative thread + cluster peers."""
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ce.id, ce.title, ce.event_cluster_id, ce.storyline_id,
                           ce.source_article_id, ce.actual_event_date
                    FROM public.chronological_events ce
                    WHERE ce.id = %s
                    """,
                    (int(event_id),),
                )
                erow = cur.fetchone()
                if not erow:
                    return {"found": False, "event_id": event_id}

                eid, title, cluster_id, ce_storyline, article_id, event_date = erow
                cur.execute(
                    """
                    SELECT eel.domain_key, eel.episode_id, eel.link_type, eel.inference_stage,
                           eel.blend_rank, eel.added_by, eel.metadata
                    FROM intelligence.event_episode_links eel
                    WHERE eel.event_id = %s
                      AND eel.inference_stage <> 'quarantined'
                    ORDER BY eel.updated_at DESC NULLS LAST
                    """,
                    (int(event_id),),
                )
                eel_rows = cur.fetchall() or []
                episodes: list[dict[str, Any]] = []
                for dk, ep_id, link_type, stage, blend, added_by, meta in eel_rows:
                    schema = resolve_domain_schema(str(dk))
                    cur.execute(
                        f"""
                        SELECT id, title, status, anchor_signature IS NOT NULL AS has_signature
                        FROM {schema}.storylines
                        WHERE id = %s
                        LIMIT 1
                        """,
                        (int(ep_id),),
                    )
                    srow = cur.fetchone()
                    thread: dict[str, Any] | None = None
                    cur.execute(
                        """
                        SELECT id, title, status
                        FROM intelligence.narrative_threads
                        WHERE domain_key = %s AND storyline_id = %s
                        LIMIT 1
                        """,
                        (str(dk), int(ep_id)),
                    )
                    trow = cur.fetchone()
                    if trow:
                        thread = {
                            "narrative_thread_id": int(trow[0]),
                            "title": trow[1],
                            "status": trow[2],
                        }
                    episodes.append(
                        {
                            "domain_key": str(dk),
                            "episode_id": int(ep_id),
                            "episode_title": srow[1] if srow else None,
                            "episode_status": srow[2] if srow else None,
                            "has_anchor_signature": bool(srow[3]) if srow else False,
                            "link_type": link_type,
                            "inference_stage": stage,
                            "blend_rank": float(blend) if blend is not None else None,
                            "added_by": added_by,
                            "metadata": meta,
                            "narrative_thread": thread,
                        }
                    )

                cluster_members: list[dict[str, Any]] = []
                if cluster_id:
                    cur.execute(
                        """
                        SELECT ce.id, ce.title,
                               EXISTS (
                                 SELECT 1 FROM intelligence.event_episode_links eel
                                 WHERE eel.event_id = ce.id
                                   AND eel.inference_stage <> 'quarantined'
                               ) AS linked
                        FROM public.chronological_events ce
                        WHERE ce.event_cluster_id = %s
                        ORDER BY ce.id
                        LIMIT 50
                        """,
                        (int(cluster_id),),
                    )
                    for mid, mtitle, linked in cur.fetchall() or []:
                        cluster_members.append(
                            {
                                "event_id": int(mid),
                                "title": mtitle,
                                "linked": bool(linked),
                            }
                        )

                tracked_events: list[dict[str, Any]] = []
                for ep in episodes:
                    cur.execute(
                        """
                        SELECT id, event_name, storyline_id
                        FROM intelligence.tracked_events
                        WHERE storyline_id = %s OR storyline_id = %s
                        LIMIT 10
                        """,
                        (
                            str(ep["episode_id"]),
                            f"{resolve_domain_schema(ep['domain_key'])}:{ep['episode_id']}",
                        ),
                    )
                    for tid, tname, tsl in cur.fetchall() or []:
                        tracked_events.append(
                            {
                                "tracked_event_id": int(tid),
                                "event_name": tname,
                                "storyline_id": tsl,
                            }
                        )

        return {
            "found": True,
            "event_id": int(eid),
            "title": title,
            "event_date": event_date.isoformat() if event_date else None,
            "event_cluster_id": int(cluster_id) if cluster_id else None,
            "legacy_storyline_id": ce_storyline,
            "source_article_id": int(article_id) if article_id else None,
            "episodes": episodes,
            "cluster_members": cluster_members,
            "tracked_events": tracked_events,
        }
    except Exception as exc:
        logger.warning("event_connections event=%s: %s", event_id, exc)
        return {"found": False, "event_id": event_id, "error": str(exc)[:200]}


def entity_graph(entity_profile_id: int, *, limit: int = 40) -> dict[str, Any]:
    """Entity profile → facts, storylines (via SEI), graph links."""
    limit = max(5, min(100, int(limit)))
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, canonical_name, domain_key, entity_type
                    FROM intelligence.entity_profiles
                    WHERE id = %s
                    """,
                    (int(entity_profile_id),),
                )
                prow = cur.fetchone()
                if not prow:
                    return {"found": False, "entity_profile_id": entity_profile_id}

                ep_id, name, domain_key, entity_type = prow
                cur.execute(
                    """
                    SELECT id, predicate, object_text, confidence, created_at
                    FROM intelligence.versioned_facts
                    WHERE entity_profile_id = %s
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (int(entity_profile_id), limit),
                )
                facts = [
                    {
                        "fact_id": int(r[0]),
                        "predicate": r[1],
                        "object_text": r[2],
                        "confidence": float(r[3]) if r[3] is not None else None,
                    }
                    for r in cur.fetchall() or []
                ]

                storylines: list[dict[str, Any]] = []
                dk = domain_key or get_pipeline_active_domain_keys()[0]
                schema = resolve_domain_schema(str(dk))
                cur.execute(
                    f"""
                    SELECT DISTINCT sei.storyline_id, s.title, s.status
                    FROM {schema}.story_entity_index sei
                    JOIN {schema}.storylines s ON s.id = sei.storyline_id
                    WHERE LOWER(sei.entity_name) = LOWER(%s)
                      AND s.merged_into_id IS NULL
                    ORDER BY sei.storyline_id DESC
                    LIMIT %s
                    """,
                    (str(name or ""), limit),
                )
                for sid, stitle, status in cur.fetchall() or []:
                    storylines.append(
                        {
                            "domain_key": str(dk),
                            "episode_id": int(sid),
                            "title": stitle,
                            "status": status,
                        }
                    )

                graph_edges: list[dict[str, Any]] = []
                cur.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema = 'intelligence' AND table_name = 'graph_connection_links'
                    )
                    """
                )
                if cur.fetchone()[0]:
                    cur.execute(
                        """
                        SELECT left_kind, left_id, right_kind, right_id, link_role, confidence
                        FROM intelligence.graph_connection_links
                        WHERE COALESCE(status, 'active') = 'active'
                          AND (
                            (left_kind = 'entity_profile' AND left_id = %s)
                            OR (right_kind = 'entity_profile' AND right_id = %s)
                          )
                        LIMIT %s
                        """,
                        (int(entity_profile_id), int(entity_profile_id), limit),
                    )
                    for lk, li, rk, ri, role, conf in cur.fetchall() or []:
                        graph_edges.append(
                            {
                                "left_kind": lk,
                                "left_id": int(li),
                                "right_kind": rk,
                                "right_id": int(ri),
                                "link_role": role,
                                "confidence": float(conf) if conf is not None else None,
                            }
                        )

        return {
            "found": True,
            "entity_profile_id": int(ep_id),
            "canonical_name": name,
            "domain_key": domain_key,
            "entity_type": entity_type,
            "facts": facts,
            "storylines_via_sei": storylines,
            "graph_edges": graph_edges,
        }
    except Exception as exc:
        logger.warning("entity_graph entity=%s: %s", entity_profile_id, exc)
        return {
            "found": False,
            "entity_profile_id": entity_profile_id,
            "error": str(exc)[:200],
        }


def refresh_assembly_graph_edges(
    *,
    domain_key: str | None = None,
    limit: int | None = None,
    apply: bool = True,
) -> dict[str, Any]:
    """Project EEL + narrative_threads + SEI into graph_connection_links."""
    from services.graph_connection_queue_service import insert_graph_connection_link_pair

    batch = limit or env_int("GRAPH_EDGE_PROJECTION_BATCH", 500)
    batch = max(10, min(5000, int(batch)))
    stats = {
        "eel_edges": 0,
        "thread_edges": 0,
        "entity_edges": 0,
        "skipped": 0,
        "apply": apply,
    }
    domains = [domain_key] if domain_key else list(get_pipeline_active_domain_keys())

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema = 'intelligence'
                        AND table_name = 'graph_connection_links'
                    )
                    """
                )
                if not cur.fetchone()[0]:
                    return {**stats, "error": "graph_connection_links table missing"}

            for dk in domains:
                schema = resolve_domain_schema(dk)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT eel.event_id, eel.episode_id, eel.blend_rank
                        FROM intelligence.event_episode_links eel
                        WHERE eel.domain_key = %s
                          AND eel.inference_stage <> 'quarantined'
                        ORDER BY eel.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (dk, batch),
                    )
                    eel_rows = cur.fetchall() or []

                    for event_id, episode_id, blend in eel_rows:
                        if not apply:
                            stats["eel_edges"] += 1
                            continue
                        ok = insert_graph_connection_link_pair(
                            domain_key=dk,
                            source_proposal_id=None,
                            left_kind="chronological_event",
                            left_id=int(event_id),
                            right_kind="storyline",
                            right_id=int(episode_id),
                            link_role="member_of_episode",
                            confidence=float(blend) if blend is not None else 0.75,
                            evidence={"phase": "assembly_projection", "method": "eel"},
                            source="episode_assembly_maintenance",
                            inference_stage="established",
                            cur=cur,
                        )
                        if ok:
                            stats["eel_edges"] += 1
                        else:
                            stats["skipped"] += 1

                    cur.execute(
                        """
                        SELECT nt.storyline_id, nt.id
                        FROM intelligence.narrative_threads nt
                        WHERE nt.domain_key = %s AND nt.storyline_id IS NOT NULL
                        ORDER BY nt.updated_at DESC NULLS LAST
                        LIMIT %s
                        """,
                        (dk, batch),
                    )
                    thread_rows = cur.fetchall() or []

                    for storyline_id, thread_id in thread_rows:
                        if not apply:
                            stats["thread_edges"] += 1
                            continue
                        ok = insert_graph_connection_link_pair(
                            domain_key=dk,
                            source_proposal_id=None,
                            left_kind="storyline",
                            left_id=int(storyline_id),
                            right_kind="narrative_thread",
                            right_id=int(thread_id),
                            link_role="has_narrative_thread",
                            confidence=0.9,
                            evidence={
                                "phase": "assembly_projection",
                                "method": "narrative_thread",
                            },
                            source="episode_assembly_maintenance",
                            inference_stage="established",
                            cur=cur,
                        )
                        if ok:
                            stats["thread_edges"] += 1

                    cur.execute(
                        f"""
                        SELECT DISTINCT sei.storyline_id, ep.id
                        FROM {schema}.story_entity_index sei
                        JOIN intelligence.entity_profiles ep
                          ON LOWER(ep.canonical_name) = LOWER(sei.entity_name)
                         AND ep.domain_key = %s
                        JOIN {schema}.storylines s ON s.id = sei.storyline_id
                        WHERE s.merged_into_id IS NULL
                        ORDER BY sei.storyline_id DESC
                        LIMIT %s
                        """,
                        (dk, batch),
                    )
                    sei_rows = cur.fetchall() or []

                    for storyline_id, profile_id in sei_rows:
                        if not apply:
                            stats["entity_edges"] += 1
                            continue
                        ok = insert_graph_connection_link_pair(
                            domain_key=dk,
                            source_proposal_id=None,
                            left_kind="storyline",
                            left_id=int(storyline_id),
                            right_kind="entity_profile",
                            right_id=int(profile_id),
                            link_role="mentions_entity",
                            confidence=0.7,
                            evidence={
                                "phase": "assembly_projection",
                                "method": "story_entity_index",
                            },
                            source="episode_assembly_maintenance",
                            inference_stage="candidate",
                            cur=cur,
                        )
                        if ok:
                            stats["entity_edges"] += 1

            if apply:
                conn.commit()
    except Exception as exc:
        logger.warning("refresh_assembly_graph_edges: %s", exc)
        return {**stats, "error": str(exc)[:200]}

    stats["items_projected"] = (
        stats["eel_edges"] + stats["thread_edges"] + stats["entity_edges"]
    )
    return stats
