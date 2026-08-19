"""Upstream episode deduplication and EEL-aware merge.

Episodes covering the same events should grow as one long-form record (Wikipedia-style),
not spawn isolated duplicates on each discovery or continuation pass.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool, env_float, env_int
from shared.domain_registry import resolve_domain_schema
from shared.episode_title_match import episode_title_similarity, normalize_episode_title

logger = logging.getLogger(__name__)


def episode_merge_enabled() -> bool:
    return env_bool("EPISODE_MERGE_ENABLED", True)


def _title_sim_threshold() -> float:
    return max(0.5, min(1.0, env_float("EPISODE_MERGE_TITLE_SIM", 0.88)))


def _normalize_title(title: str) -> str:
    return normalize_episode_title(title)


def title_similarity(a: str, b: str) -> float:
    return episode_title_similarity(a, b)


def find_episodes_for_event(conn, *, domain_key: str, event_id: int) -> list[int]:
    """Episodes already linked to this event in this domain."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT episode_id
            FROM intelligence.event_episode_links
            WHERE domain_key = %s AND event_id = %s
              AND inference_stage <> 'quarantined'
            ORDER BY episode_id
            """,
            (domain_key, int(event_id)),
        )
        return [int(r[0]) for r in cur.fetchall() or []]


def find_episodes_by_signature_match(
    conn,
    *,
    domain_key: str,
    schema: str,
    event_id: int,
    article_id: int | None,
) -> list[int]:
    from shared.episode_attach_gate import (
        classify_event_anchors,
        parse_anchor_signature,
        signature_match,
    )

    event_anchors = classify_event_anchors(
        conn,
        domain_key=domain_key,
        schema=schema,
        event_id=int(event_id),
        article_id=article_id,
    )
    if not (event_anchors.get("identity") or event_anchors.get("supporting")):
        return []

    matches: list[int] = []
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, anchor_signature
            FROM {schema}.storylines
            WHERE merged_into_id IS NULL
              AND COALESCE(story_kind, '') <> 'container_index'
              AND COALESCE(is_mega_storyline, FALSE) = FALSE
              AND status NOT IN ('archived', 'concluded')
              AND anchor_signature IS NOT NULL
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 120
            """
        )
        for sid, raw_sig in cur.fetchall() or []:
            sig = parse_anchor_signature(raw_sig)
            ok, _matched, _reason = signature_match(
                sig, event_anchors, min_supporting=2, min_identity=2
            )
            if ok:
                matches.append(int(sid))
    return matches


def find_episodes_by_title(
    conn,
    *,
    schema: str,
    title: str,
    threshold: float | None = None,
) -> list[int]:
    threshold = threshold if threshold is not None else _title_sim_threshold()
    norm = _normalize_title(title)
    if len(norm) < 12:
        return []

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, title
            FROM {schema}.storylines
            WHERE merged_into_id IS NULL
              AND COALESCE(story_kind, '') <> 'container_index'
              AND status NOT IN ('archived', 'concluded')
              AND LOWER(TRIM(title)) = %s
            ORDER BY COALESCE(article_count, 0) DESC, id ASC
            """,
            (norm,),
        )
        exact = [int(r[0]) for r in cur.fetchall() or []]
        if exact:
            return exact

        prefix = norm[:24] + "%"
        cur.execute(
            f"""
            SELECT id, title
            FROM {schema}.storylines
            WHERE merged_into_id IS NULL
              AND COALESCE(story_kind, '') <> 'container_index'
              AND status NOT IN ('archived', 'concluded')
              AND LOWER(title) LIKE %s
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 40
            """,
            (prefix,),
        )
        fuzzy: list[int] = []
        for sid, row_title in cur.fetchall() or []:
            if title_similarity(title, row_title or "") >= threshold:
                fuzzy.append(int(sid))
        return fuzzy


def pick_canonical_episode(conn, *, schema: str, episode_ids: list[int]) -> int | None:
    if not episode_ids:
        return None
    ids = sorted({int(x) for x in episode_ids})
    if len(ids) == 1:
        return ids[0]

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.id,
                   COALESCE(s.article_count, 0) AS ac,
                   (s.signature_locked_at IS NOT NULL) AS sig_locked,
                   (SELECT COUNT(*) FROM intelligence.event_episode_links eel
                    WHERE eel.episode_id = s.id
                      AND eel.inference_stage <> 'quarantined') AS eel_count,
                   s.created_at
            FROM {schema}.storylines s
            WHERE s.id = ANY(%s) AND s.merged_into_id IS NULL
            ORDER BY eel_count DESC, sig_locked DESC, ac DESC, s.created_at ASC
            LIMIT 1
            """,
            (ids,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else ids[0]


def resolve_existing_episode(
    conn,
    *,
    domain_key: str,
    event_id: int | None = None,
    article_id: int | None = None,
    title_hint: str | None = None,
    article_ids: list[int] | None = None,
) -> int | None:
    """
    Find the canonical episode before minting a new one.

    Priority: shared event links > signature match > title match > narrative-first.
    """
    if not episode_merge_enabled():
        return None

    schema = resolve_domain_schema(domain_key)
    candidates: list[int] = []

    if event_id is not None:
        candidates.extend(
            find_episodes_for_event(conn, domain_key=domain_key, event_id=int(event_id))
        )
        candidates.extend(
            find_episodes_by_signature_match(
                conn,
                domain_key=domain_key,
                schema=schema,
                event_id=int(event_id),
                article_id=article_id,
            )
        )

    if title_hint:
        candidates.extend(
            find_episodes_by_title(conn, schema=schema, title=title_hint)
        )

    aids = [int(a) for a in (article_ids or []) if int(a) > 0][:20]
    if aids:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT eel.episode_id
                FROM intelligence.event_episode_links eel
                JOIN public.chronological_events ce ON ce.id = eel.event_id
                WHERE eel.domain_key = %s
                  AND eel.inference_stage <> 'quarantined'
                  AND ce.source_article_id = ANY(%s)
                """,
                (domain_key, aids),
            )
            candidates.extend(int(r[0]) for r in cur.fetchall() or [])

    if not candidates and (aids or title_hint):
        try:
            from services.narrative_first_linking_service import (
                find_narrative_storyline_match,
                narrative_linking_enabled,
            )

            if narrative_linking_enabled():
                match = find_narrative_storyline_match(
                    domain_key,
                    article_ids=aids,
                    title_hint=title_hint,
                )
                if match and match.storyline_id:
                    candidates.append(int(match.storyline_id))
        except Exception as e:
            logger.debug("resolve_existing_episode narrative-first: %s", e)

    if not candidates:
        return None

    canonical = pick_canonical_episode(conn, schema=schema, episode_ids=candidates)
    if canonical:
        logger.info(
            "episode_merge resolve domain=%s -> episode=%s (%d candidates, event=%s title=%r)",
            domain_key,
            canonical,
            len(set(candidates)),
            event_id,
            (title_hint or "")[:60],
        )
    return canonical


def _merge_narrative_threads(
    cur, domain_key: str, primary_id: int, secondary_id: int
) -> None:
    cur.execute(
        """
        SELECT id, summary FROM intelligence.narrative_threads
        WHERE domain_key = %s AND storyline_id = %s
        """,
        (domain_key, secondary_id),
    )
    sec = cur.fetchone()
    if not sec:
        return

    cur.execute(
        """
        SELECT id, summary FROM intelligence.narrative_threads
        WHERE domain_key = %s AND storyline_id = %s
        """,
        (domain_key, primary_id),
    )
    pri = cur.fetchone()
    sec_summary = (sec[1] or "").strip()
    if pri:
        pri_summary = (pri[1] or "").strip()
        combined = pri_summary
        if sec_summary and sec_summary not in pri_summary:
            combined = (pri_summary + "\n\n" + sec_summary).strip()[:8000]
        cur.execute(
            "UPDATE intelligence.narrative_threads SET summary = %s WHERE id = %s",
            (combined, pri[0]),
        )
        cur.execute("DELETE FROM intelligence.narrative_threads WHERE id = %s", (sec[0],))
    else:
        cur.execute(
            "UPDATE intelligence.narrative_threads SET storyline_id = %s WHERE id = %s",
            (primary_id, sec[0]),
        )


def _append_episode_dossier_note(
    cur,
    schema: str,
    primary_id: int,
    secondary_id: int,
    secondary_title: str | None,
    reason: str,
) -> None:
    """Grow the canonical episode dossier metadata over time."""
    cur.execute(f"SELECT metadata FROM {schema}.storylines WHERE id = %s", (primary_id,))
    row = cur.fetchone()
    meta = row[0] if row and row[0] else {}
    if not isinstance(meta, dict):
        meta = {}

    dossier = meta.get("episode_dossier") or {}
    merges = list(dossier.get("merges") or [])
    merges.append(
        {
            "from_episode_id": secondary_id,
            "title": (secondary_title or "")[:200],
            "reason": reason,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    dossier["merges"] = merges[-50:]
    dossier["last_updated"] = datetime.now(timezone.utc).isoformat()
    meta["episode_dossier"] = dossier
    cur.execute(
        f"UPDATE {schema}.storylines SET metadata = %s::jsonb WHERE id = %s",
        (json.dumps(meta), primary_id),
    )


def merge_episodes_eel_aware(
    conn,
    *,
    domain_key: str,
    primary_id: int,
    secondary_id: int,
    reason: str = "episode_merge",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Merge secondary episode into primary, repointing event_episode_links."""
    primary_id, secondary_id = int(primary_id), int(secondary_id)
    out: dict[str, Any] = {
        "success": False,
        "primary_id": primary_id,
        "secondary_id": secondary_id,
        "eel_moved": 0,
        "reason": reason,
    }
    if primary_id == secondary_id:
        return {**out, "error": "same_episode"}

    schema = resolve_domain_schema(domain_key)

    with conn.cursor() as cur:
        cur.execute(
            f"SELECT merged_into_id FROM {schema}.storylines WHERE id = %s",
            (secondary_id,),
        )
        row = cur.fetchone()
        if row and row[0] is not None:
            return {**out, "error": "already_merged"}

        cur.execute(
            f"""
            SELECT id, title, description, anchor_signature, signature_locked_at
            FROM {schema}.storylines
            WHERE id IN (%s, %s)
            """,
            (primary_id, secondary_id),
        )
        rows = {int(r[0]): r for r in cur.fetchall() or []}
        if primary_id not in rows or secondary_id not in rows:
            return {**out, "error": "episode_missing"}

        if dry_run:
            return {**out, "success": True, "dry_run": True}

        cur.execute(
            """
            SELECT event_id, link_type, matched_anchors, inference_stage,
                   blend_rank, added_by, metadata
            FROM intelligence.event_episode_links
            WHERE domain_key = %s AND episode_id = %s
            """,
            (domain_key, secondary_id),
        )
        eel_rows = cur.fetchall() or []

        from shared.episode_attach_gate import (
            insert_event_episode_link,
            lock_episode_signature,
            parse_anchor_signature,
        )

        for eid, ltype, anchors, stage, blend, _added_by, meta in eel_rows:
            anchor_list = list(anchors or []) if isinstance(anchors, list) else []
            merge_meta: dict[str, Any] = {"merged_from": secondary_id}
            if isinstance(meta, dict):
                merge_meta.update(meta)
            insert_event_episode_link(
                cur,
                event_id=int(eid),
                domain_key=domain_key,
                episode_id=primary_id,
                link_type=str(ltype or "continuation"),
                matched_anchors=anchor_list,
                inference_stage=str(stage or "established"),
                blend_rank=float(blend) if blend is not None else None,
                added_by=f"{reason}_merge",
                metadata=merge_meta,
            )
            out["eel_moved"] += 1
            cur.execute(
                """
                UPDATE public.chronological_events
                SET storyline_id = %s::text
                WHERE id = %s
                """,
                (str(primary_id), int(eid)),
            )

        cur.execute(
            """
            DELETE FROM intelligence.event_episode_links
            WHERE domain_key = %s AND episode_id = %s
            """,
            (domain_key, secondary_id),
        )

        _pid, _ptitle, _pdesc, psig, psig_locked = rows[primary_id]
        _sid, stitle, _sdesc, ssig, _ = rows[secondary_id]
        if not psig_locked and (psig or ssig):
            p_sig = parse_anchor_signature(psig)
            s_sig = parse_anchor_signature(ssig)
            merged_sig = {
                "identity": list(
                    dict.fromkeys(
                        (p_sig.get("identity") or []) + (s_sig.get("identity") or [])
                    )
                )[:12],
                "supporting": list(
                    dict.fromkeys(
                        (p_sig.get("supporting") or []) + (s_sig.get("supporting") or [])
                    )
                )[:12],
            }
            lock_episode_signature(cur, schema, primary_id, merged_sig)

        try:
            from shared.assembly_link_funnel import storyline_articles_write_allowed

            if storyline_articles_write_allowed():
                from shared.membership_store import copy_bag_rows

                copy_bag_rows(
                    cur,
                    schema=schema,
                    from_storyline_id=secondary_id,
                    to_storyline_id=primary_id,
                    added_by=f"{reason}_merge",
                )
                cur.execute(
                    f"DELETE FROM {schema}.storyline_articles WHERE storyline_id = %s",
                    (secondary_id,),
                )
        except Exception as e:
            logger.debug("episode merge bag move: %s", e)

        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET merged_into_id = %s,
                status = 'archived',
                article_count = 0,
                updated_at = NOW(),
                metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (
                primary_id,
                json.dumps(
                    {
                        "merged_reason": reason,
                        "merged_at": datetime.now(timezone.utc).isoformat(),
                    }
                ),
                secondary_id,
            ),
        )

        from shared.storyline_article_counts import sync_counts_update_sql

        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET {sync_counts_update_sql(schema)},
                merge_count = COALESCE(merge_count, 0) + 1,
                description = COALESCE(description, '') || %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            (f" [Merged episode {secondary_id}: {(stitle or '')[:80]}]", primary_id),
        )

        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET parent_storyline_id = %s
            WHERE parent_storyline_id = %s
            """,
            (primary_id, secondary_id),
        )

        _merge_narrative_threads(cur, domain_key, primary_id, secondary_id)
        _append_episode_dossier_note(
            cur, schema, primary_id, secondary_id, stitle, reason
        )

    out["success"] = True
    logger.info(
        "episode_merge %s <- %s domain=%s eel_moved=%s reason=%s",
        primary_id,
        secondary_id,
        domain_key,
        out["eel_moved"],
        reason,
    )
    return out


def merge_if_duplicate_before_create(
    conn,
    *,
    domain_key: str,
    proposed_title: str,
    event_id: int | None = None,
    article_id: int | None = None,
    article_ids: list[int] | None = None,
) -> int | None:
    """
    Resolve to an existing episode before INSERT; fold title-duplicates into canonical.
    """
    if not episode_merge_enabled():
        return None

    canonical = resolve_existing_episode(
        conn,
        domain_key=domain_key,
        event_id=event_id,
        article_id=article_id,
        title_hint=proposed_title,
        article_ids=article_ids,
    )
    if not canonical:
        return None

    schema = resolve_domain_schema(domain_key)
    dupes = find_episodes_by_title(conn, schema=schema, title=proposed_title)
    max_merges = max(1, env_int("EPISODE_MERGE_PRE_CREATE_MAX", 8))
    merged = 0
    for dup_id in dupes:
        if dup_id == canonical or merged >= max_merges:
            continue
        result = merge_episodes_eel_aware(
            conn,
            domain_key=domain_key,
            primary_id=canonical,
            secondary_id=dup_id,
            reason="pre_create_dedup",
        )
        if result.get("success"):
            merged += 1

    return canonical


def scan_and_merge_duplicate_episodes(
    conn,
    *,
    domain_key: str,
    limit: int = 50,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair pass: merge episodes with identical normalized titles."""
    schema = resolve_domain_schema(domain_key)
    merged = 0
    pairs_found = 0

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT LOWER(TRIM(title)) AS norm_title,
                   array_agg(id ORDER BY id) AS ids,
                   COUNT(*) AS cnt
            FROM {schema}.storylines
            WHERE merged_into_id IS NULL
              AND COALESCE(story_kind, '') <> 'container_index'
              AND status NOT IN ('archived', 'concluded')
              AND LENGTH(TRIM(COALESCE(title, ''))) >= 20
            GROUP BY LOWER(TRIM(title))
            HAVING COUNT(*) > 1
            ORDER BY COUNT(*) DESC
            LIMIT %s
            """,
            (limit,),
        )
        groups = cur.fetchall() or []

    for _norm_title, ids, _cnt in groups:
        ep_ids = [int(x) for x in ids]
        canonical = pick_canonical_episode(conn, schema=schema, episode_ids=ep_ids)
        if not canonical:
            continue
        for dup_id in ep_ids:
            if dup_id == canonical:
                continue
            pairs_found += 1
            result = merge_episodes_eel_aware(
                conn,
                domain_key=domain_key,
                primary_id=canonical,
                secondary_id=dup_id,
                reason="repair_scan",
                dry_run=dry_run,
            )
            if result.get("success"):
                merged += 1

    return {
        "domain": domain_key,
        "groups": len(groups),
        "pairs_found": pairs_found,
        "merged": merged,
        "dry_run": dry_run,
    }
