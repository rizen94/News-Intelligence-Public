"""Episode assembly maintenance — orphan event linkage for automation + CLI.

Runs continuation backfill (force-recheck), cluster batch-link (optional founding),
EEL candidate promotion, and tracked-event bridging. Called by automation_manager
``episode_assembly_maintenance`` phase and thin CLI scripts.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from config.runtime import env_bool, env_int
from shared.chronological_event_domain import (
    resolve_chronological_event_domain_key,
    unlinked_event_domain_predicate,
)
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema
from shared.episode_attach_gate import insert_event_episode_link, parse_anchor_signature, signature_match
from shared.episode_title_match import episode_title_similarity
from services.episode_merge_service import resolve_existing_episode
from services.story_continuation_service import (
    StoryContinuationService,
    continuation_recheck_due_sql,
)

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    return env_bool("EPISODE_ASSEMBLY_MAINTENANCE_ENABLED", True)


def _maintenance_limits() -> dict[str, int | bool]:
    return {
        "continuation_per_domain": max(
            10, env_int("EPISODE_ASSEMBLY_CONTINUATION_LIMIT_PER_DOMAIN", 200)
        ),
        "cluster_limit": max(10, env_int("EPISODE_ASSEMBLY_CLUSTER_LIMIT", 500)),
        "te_bridge_limit": max(10, env_int("EPISODE_ASSEMBLY_TE_BRIDGE_LIMIT", 200)),
        "force_recheck": env_bool("EPISODE_ASSEMBLY_FORCE_RECHECK", True),
        "allow_founding": env_bool(
            "EPISODE_ASSEMBLY_ALLOW_FOUNDING", env_bool("CONTINUATION_FOUNDING_ENABLED", False)
        ),
        "promote_eel": env_bool("EPISODE_ASSEMBLY_PROMOTE_EEL", True),
    }


async def continuation_backfill_domain(
    conn,
    domain_key: str,
    *,
    limit: int,
    force_recheck: bool,
    apply: bool = True,
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, Any] = {
        "domain": domain_key,
        "processed": 0,
        "matched": 0,
        "founded": 0,
        "skipped": 0,
    }
    recheck_sql, recheck_params = continuation_recheck_due_sql("ce")
    domain_pred, domain_params = unlinked_event_domain_predicate(conn, schema, domain_key)
    recheck_clause = "TRUE" if force_recheck else recheck_sql
    recheck_bind: tuple = () if force_recheck else recheck_params

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT ce.id
            FROM public.chronological_events ce
            WHERE NOT EXISTS (
                SELECT 1 FROM intelligence.event_episode_links eel
                WHERE eel.event_id = ce.id
                  AND eel.inference_stage <> 'quarantined'
              )
              AND {domain_pred}
              AND {recheck_clause}
            ORDER BY ce.extraction_timestamp DESC NULLS LAST
            LIMIT %s
            """,
            (*domain_params, *recheck_bind, int(limit)),
        )
        event_ids = [int(r[0]) for r in cur.fetchall() or []]

    svc = StoryContinuationService(conn, schema=schema)
    for eid in event_ids:
        stats["processed"] += 1
        if not apply:
            stats["skipped"] += 1
            continue
        try:
            result = await svc.match_event_to_storyline(eid)
        except Exception as exc:
            logger.debug("continuation backfill event=%s: %s", eid, exc)
            stats["skipped"] += 1
            continue
        if not result:
            stats["skipped"] += 1
            continue
        if result.get("founded") or result.get("merge_redirect"):
            stats["founded"] += 1
        else:
            stats["matched"] += 1

    stats["apply"] = apply
    return stats


def link_orphan_clusters(
    conn,
    *,
    domain_key: str | None = None,
    limit_clusters: int,
    allow_founding: bool = False,
    apply: bool = True,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "clusters_seen": 0,
        "events_linked": 0,
        "clusters_resolved": 0,
        "clusters_skipped": 0,
        "clusters_founded": 0,
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ce.event_cluster_id,
                   MIN(ce.id) AS root_id,
                   array_agg(ce.id ORDER BY ce.id) AS member_ids
            FROM public.chronological_events ce
            WHERE ce.event_cluster_id IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM intelligence.event_episode_links eel
                WHERE eel.event_id = ce.id
                  AND eel.inference_stage <> 'quarantined'
              )
            GROUP BY ce.event_cluster_id
            HAVING COUNT(*) >= 1
            ORDER BY COUNT(*) DESC
            LIMIT %s
            """,
            (int(limit_clusters),),
        )
        clusters = cur.fetchall() or []

    for cluster_id, root_id, member_ids in clusters:
        stats["clusters_seen"] += 1
        members = [int(x) for x in (member_ids or [])]
        if not members:
            stats["clusters_skipped"] += 1
            continue

        episode_id: int | None = None
        dk: str | None = domain_key

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT eel.episode_id, eel.domain_key
                FROM intelligence.event_episode_links eel
                WHERE eel.event_id = ANY(%s)
                  AND eel.inference_stage <> 'quarantined'
                ORDER BY eel.updated_at DESC NULLS LAST
                LIMIT 1
                """,
                (members,),
            )
            linked = cur.fetchone()
            if linked:
                episode_id, dk = int(linked[0]), str(linked[1])

        if not episode_id:
            dk = dk or resolve_chronological_event_domain_key(conn, int(root_id))
            if not dk:
                stats["clusters_skipped"] += 1
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT title FROM public.chronological_events WHERE id = %s",
                    (int(root_id),),
                )
                erow = cur.fetchone()
                event_title = (erow[0] if erow else "") or ""
            episode_id = resolve_existing_episode(
                conn,
                domain_key=dk,
                event_id=int(root_id),
                article_id=None,
                title_hint=event_title,
            )
            if not episode_id and event_title:
                from services.episode_merge_service import find_episodes_by_title, pick_canonical_episode

                schema = resolve_domain_schema(dk)
                title_matches = find_episodes_by_title(conn, schema=schema, title=event_title)
                if title_matches:
                    episode_id = pick_canonical_episode(
                        conn, schema=schema, episode_ids=title_matches
                    )

        if not episode_id and allow_founding and dk and apply:
            schema = resolve_domain_schema(dk)
            svc = StoryContinuationService(conn, schema=schema)
            founded = asyncio.run(svc.match_event_to_storyline(int(root_id)))
            if founded and founded.get("storyline_id"):
                episode_id = int(founded["storyline_id"])
                stats["clusters_founded"] += 1

        if not episode_id:
            stats["clusters_skipped"] += 1
            continue

        stats["clusters_resolved"] += 1
        linked_this = 0
        with conn.cursor() as cur:
            for eid in members:
                if not apply:
                    linked_this += 1
                    continue
                if insert_event_episode_link(
                    cur,
                    event_id=int(eid),
                    domain_key=dk,
                    episode_id=int(episode_id),
                    link_type="continuation",
                    matched_anchors=[],
                    inference_stage="candidate",
                    blend_rank=0.75,
                    added_by="cluster_batch_link",
                    metadata={"cluster_id": int(cluster_id), "root_event_id": int(root_id)},
                ):
                    linked_this += 1
                    cur.execute(
                        """
                        UPDATE public.chronological_events
                        SET storyline_id = %s::text
                        WHERE id = %s
                        """,
                        (str(int(episode_id)), int(eid)),
                    )
        stats["events_linked"] += linked_this
        if apply:
            conn.commit()
        elif linked_this:
            conn.rollback()

    stats["domain"] = domain_key or "all"
    stats["apply"] = apply
    return stats


def _anchors_from_te(anchors_raw, participant_ids) -> dict:
    identity: list[str] = []
    supporting: list[str] = []
    if isinstance(anchors_raw, dict):
        identity.extend(str(x) for x in (anchors_raw.get("identity") or [])[:12])
        supporting.extend(str(x) for x in (anchors_raw.get("supporting") or [])[:12])
    if participant_ids:
        for pid in participant_ids[:12]:
            token = f"cid:{int(pid)}"
            if token not in identity:
                identity.append(token)
    return {"identity": identity, "supporting": supporting, "hub": []}


def bridge_tracked_events_domain(
    conn,
    domain_key: str,
    *,
    apply: bool,
    limit: int,
) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    stats: dict[str, Any] = {"domain": domain_key, "scanned": 0, "bridged": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, event_name, anchors, key_participant_entity_ids, domain_keys
            FROM intelligence.tracked_events
            WHERE storyline_id IS NULL
              AND %s = ANY(domain_keys)
            ORDER BY updated_at DESC NULLS LAST
            LIMIT %s
            """,
            (domain_key, int(limit)),
        )
        rows = cur.fetchall() or []

    for te_id, event_name, anchors_raw, participant_ids, _domain_keys in rows:
        stats["scanned"] += 1
        event_anchors = _anchors_from_te(anchors_raw, participant_ids)
        te_name = (event_name or "").strip()
        if not (event_anchors.get("identity") or event_anchors.get("supporting")) and len(
            te_name
        ) < 12:
            stats["skipped"] += 1
            continue

        best_ep: int | None = None
        best_score = 0.0
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, anchor_signature
                FROM {schema}.storylines
                WHERE merged_into_id IS NULL
                  AND COALESCE(story_kind, '') <> 'container_index'
                  AND status NOT IN ('archived', 'concluded')
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 200
                """
            )
            for sid, title, raw_sig in cur.fetchall() or []:
                title_sim = episode_title_similarity(te_name, title or "") if te_name else 0.0
                if title_sim >= 0.72 and title_sim > best_score:
                    best_score = title_sim
                    best_ep = int(sid)
                    continue
                if not raw_sig:
                    continue
                sig = parse_anchor_signature(raw_sig)
                ok, matched, _reason = signature_match(
                    sig, event_anchors, min_supporting=2, min_identity=2
                )
                if ok and len(matched) > best_score:
                    best_score = float(len(matched))
                    best_ep = int(sid)

        if not best_ep:
            stats["skipped"] += 1
            continue

        if apply:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.tracked_events
                    SET storyline_id = %s, updated_at = NOW()
                    WHERE id = %s AND storyline_id IS NULL
                    """,
                    (best_ep, int(te_id)),
                )
            conn.commit()
        stats["bridged"] += 1

    stats["apply"] = apply
    return stats


def promote_candidate_eel_domain(conn, domain_key: str, *, apply: bool = True) -> dict[str, Any]:
    schema = resolve_domain_schema(domain_key)
    with conn.cursor() as cur:
        if not apply:
            cur.execute(
                f"""
                SELECT COUNT(*)
                FROM intelligence.event_episode_links eel
                JOIN {schema}.storylines s ON s.id = eel.episode_id
                WHERE eel.domain_key = %s
                  AND eel.inference_stage = 'candidate'
                  AND s.merged_into_id IS NULL
                  AND (
                    s.signature_locked_at IS NOT NULL
                    OR (
                      SELECT COUNT(DISTINCT e2.event_id)
                      FROM intelligence.event_episode_links e2
                      WHERE e2.episode_id = s.id
                        AND e2.domain_key = eel.domain_key
                        AND e2.inference_stage <> 'quarantined'
                    ) >= 2
                  )
                """,
                (domain_key,),
            )
            count = int((cur.fetchone() or [0])[0] or 0)
            return {"domain": domain_key, "promoted": count, "dry_run": True}

        cur.execute(
            f"""
            UPDATE intelligence.event_episode_links eel
            SET inference_stage = 'established', updated_at = NOW()
            FROM {schema}.storylines s
            WHERE eel.episode_id = s.id
              AND eel.domain_key = %s
              AND eel.inference_stage = 'candidate'
              AND s.merged_into_id IS NULL
              AND (
                s.signature_locked_at IS NOT NULL
                OR (
                  SELECT COUNT(DISTINCT e2.event_id)
                  FROM intelligence.event_episode_links e2
                  WHERE e2.episode_id = s.id
                    AND e2.domain_key = eel.domain_key
                    AND e2.inference_stage <> 'quarantined'
                ) >= 2
              )
            """,
            (domain_key,),
        )
        promoted = int(cur.rowcount or 0)
    if apply:
        conn.commit()
    return {"domain": domain_key, "promoted": promoted, "dry_run": False}


def count_episode_assembly_pending(conn=None) -> int:
    """Orphan clusters without any EEL on members (capped probe for scheduling)."""
    cap = max(100, env_int("EPISODE_ASSEMBLY_PENDING_PROBE_CAP", 5000))
    close_conn = False
    if conn is None:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        close_conn = True
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '8s'")
            cur.execute(
                """
                SELECT COUNT(*)::int FROM (
                    SELECT 1
                    FROM public.chronological_events ce
                    WHERE ce.event_cluster_id IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.event_episode_links eel
                        WHERE eel.event_id = ce.id
                          AND eel.inference_stage <> 'quarantined'
                      )
                    GROUP BY ce.event_cluster_id
                    LIMIT %s
                ) t
                """,
                (cap,),
            )
            return int(cur.fetchone()[0] or 0)
    except Exception as exc:
        logger.debug("episode_assembly_maintenance pending count: %s", exc)
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        if close_conn:
            try:
                conn.close()
            except Exception:
                pass


async def run_episode_assembly_maintenance(
    conn,
    *,
    apply: bool = True,
    limits: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One maintenance pass — used by automation_manager and CLI orchestrator."""
    if not is_enabled():
        return {"enabled": False, "skipped": True}

    cfg = limits or _maintenance_limits()
    out: dict[str, Any] = {"apply": apply, "limits": cfg}

    if cfg.get("promote_eel"):
        promoted_total = 0
        promote_results = []
        for dk in get_pipeline_active_domain_keys():
            pr = promote_candidate_eel_domain(conn, dk, apply=apply)
            promote_results.append(pr)
            promoted_total += int(pr.get("promoted") or 0)
        out["promote_eel"] = {"total_promoted": promoted_total, "domains": promote_results}

    continuation_results = []
    cont_matched = cont_founded = 0
    for dk in get_pipeline_active_domain_keys():
        cr = await continuation_backfill_domain(
            conn,
            dk,
            limit=int(cfg["continuation_per_domain"]),
            force_recheck=bool(cfg["force_recheck"]),
            apply=apply,
        )
        continuation_results.append(cr)
        cont_matched += int(cr.get("matched") or 0)
        cont_founded += int(cr.get("founded") or 0)
    out["continuation_backfill"] = {
        "matched": cont_matched,
        "founded": cont_founded,
        "domains": continuation_results,
    }

    cluster_limit = int(cfg.get("cluster_limit") or 0)
    if cluster_limit > 0:
        out["cluster_link"] = link_orphan_clusters(
            conn,
            limit_clusters=cluster_limit,
            allow_founding=bool(cfg["allow_founding"]),
            apply=apply,
        )
    else:
        out["cluster_link"] = {"skipped": True, "events_linked": 0}

    bridge_results = []
    bridged_total = 0
    for dk in get_pipeline_active_domain_keys():
        br = bridge_tracked_events_domain(
            conn, dk, apply=apply, limit=int(cfg["te_bridge_limit"])
        )
        bridge_results.append(br)
        bridged_total += int(br.get("bridged") or 0)
    out["te_bridge"] = {"bridged": bridged_total, "domains": bridge_results}

    out["items_processed"] = (
        cont_matched
        + cont_founded
        + int(out["cluster_link"].get("events_linked") or 0)
        + bridged_total
        + int(out.get("promote_eel", {}).get("total_promoted") or 0)
    )
    return out
