"""
Single write choke point for article→episode membership.

All callers use admit() / admit_batch(); direct INSERT INTO storyline_articles
is forbidden outside this module (CI-enforced) except maintenance scripts.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from typing import Any

from shared.membership_mode import MembershipMode, get_membership_mode

logger = logging.getLogger(__name__)

_MEMBERSHIP_STORE_SESSION_KEY = "ni.membership_store_write"


class MembershipIntent(str, Enum):
    DISCOVERY_SEED = "discovery_seed"
    CONTINUATION = "continuation"
    HITL_APPROVE = "hitl_approve"
    AUTOMATION = "automation"
    CONSOLIDATION_MOVE = "consolidation_move"
    TOPIC_CONVERT = "topic_convert"
    API_MANUAL = "api_manual"
    MEMBERSHIP_ADMIT = "membership_admit"


def _log_admit(
    *,
    intent: MembershipIntent,
    outcome: str,
    mode: MembershipMode,
    episode_id: int,
    article_id: int,
    reason: str = "",
) -> None:
    logger.info(
        "membership_admit intent=%s outcome=%s mode=%s episode=%s article=%s reason=%s",
        intent.value,
        outcome,
        mode.value,
        episode_id,
        article_id,
        reason,
    )


def _maybe_enqueue_finisher_after_admit(
    *,
    domain_key: str,
    episode_id: int,
    article_id: int,
    intent: MembershipIntent,
    membership_changed: bool,
) -> None:
    """Materiality-gated narrative finisher after a real membership change."""
    if not membership_changed:
        return
    try:
        from services.content_refinement_queue_service import (
            maybe_enqueue_narrative_finisher_on_membership,
        )

        maybe_enqueue_narrative_finisher_on_membership(
            domain_key,
            int(episode_id),
            source="membership_admit",
            article_id=int(article_id),
            intent=intent.value,
        )
    except Exception as exc:
        logger.debug(
            "membership finisher enqueue skip episode=%s article=%s: %s",
            episode_id,
            article_id,
            exc,
        )


def _set_bag_write_session(cur) -> None:
    cur.execute("SELECT set_config(%s, %s, true)", (_MEMBERSHIP_STORE_SESSION_KEY, "1"))


def _insert_bag_row(
    cur,
    *,
    schema: str,
    storyline_id: int,
    article_id: int,
    relevance_score: float,
    added_by: str,
    relationship_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Private — only called when mode allows bag writes."""
    _set_bag_write_session(cur)
    meta_json = json.dumps(metadata or {})
    if relationship_type:
        cur.execute(
            f"""
            INSERT INTO {schema}.storyline_articles
            (storyline_id, article_id, relevance_score, relationship_type,
             added_by, created_at, updated_at, metadata)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), %s::jsonb)
            ON CONFLICT (storyline_id, article_id) DO NOTHING
            """,
            (
                int(storyline_id),
                int(article_id),
                float(relevance_score),
                relationship_type,
                added_by,
                meta_json,
            ),
        )
    else:
        cur.execute(
            f"""
            INSERT INTO {schema}.storyline_articles
            (storyline_id, article_id, relevance_score, added_by, created_at, updated_at, metadata)
            VALUES (%s, %s, %s, %s, NOW(), NOW(), %s::jsonb)
            ON CONFLICT (storyline_id, article_id) DO NOTHING
            """,
            (
                int(storyline_id),
                int(article_id),
                float(relevance_score),
                added_by,
                meta_json,
            ),
        )
    return bool(cur.rowcount)


def _record_attach_block(
    cur,
    *,
    schema: str,
    episode_id: int,
    reason: str,
) -> None:
    try:
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET metadata = jsonb_set(
                    jsonb_set(
                        COALESCE(metadata, '{{}}'::jsonb),
                        '{{attach_block_reason}}',
                        to_jsonb(%s::text)
                    ),
                    '{{last_attach_attempt_at}}',
                    to_jsonb(NOW()::text)
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (reason[:500], int(episode_id)),
        )
    except Exception as exc:
        logger.debug("attach_block metadata update failed episode=%s: %s", episode_id, exc)


def admit(
    conn,
    *,
    domain_key: str,
    schema: str,
    episode_id: int,
    article_id: int,
    intent: MembershipIntent,
    blend_score: float = 0.0,
    added_by: str,
    link_mode: str | None = None,
    score_parts: dict[str, Any] | None = None,
    recompute_score: bool | None = None,
    bag_metadata: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    """
    Admit an article to an episode. Returns (success, reason).

    EPISODE_EEL: EEL attach only — no bag fallback on failure.
    EPISODE_EEL_DUAL_WRITE: EEL + optional derived/thin bag rows.
    LEGACY_BAG: funnel gate + bag insert.

    When ``recompute_score`` is True (default for discovery/automation/continuation),
    content-aware ``score_article_storyline_membership`` overrides ``blend_score``
    unless the caller already supplied ``score_parts``.
    """
    from shared.assembly_link_modes import LINK_MODE_SEQUENCE
    from shared.episode_attach_gate import (
        attach_article_events_to_episode,
        episode_container_assembly_enabled,
    )

    mode = get_membership_mode()
    mode_str = link_mode or LINK_MODE_SEQUENCE
    eid = int(episode_id)
    aid = int(article_id)

    # A3: yieldable-before-attach — enriched alone is not enough.
    _yield_intents = {
        MembershipIntent.DISCOVERY_SEED,
        MembershipIntent.AUTOMATION,
        MembershipIntent.CONTINUATION,
        MembershipIntent.MEMBERSHIP_ADMIT,
    }
    if intent in _yield_intents:
        try:
            from services.article_content_enrichment_service import is_false_enriched_body

            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT content, enrichment_status FROM {schema}.articles WHERE id = %s",
                    (aid,),
                )
                row = cur.fetchone()
            if not row:
                _log_admit(
                    intent=intent,
                    outcome="reject",
                    mode=mode,
                    episode_id=eid,
                    article_id=aid,
                    reason="article_missing",
                )
                return False, "article_missing"
            body, estatus = row[0], (row[1] or "")
            if estatus == "removed" or is_false_enriched_body(body):
                _log_admit(
                    intent=intent,
                    outcome="reject",
                    mode=mode,
                    episode_id=eid,
                    article_id=aid,
                    reason="not_yieldable",
                )
                return False, "not_yieldable"
        except Exception as exc:
            logger.debug("admit yieldable check failed article=%s: %s", aid, exc)

    _auto_recompute = {
        MembershipIntent.DISCOVERY_SEED,
        MembershipIntent.AUTOMATION,
        MembershipIntent.CONTINUATION,
        MembershipIntent.MEMBERSHIP_ADMIT,
    }
    do_recompute = (
        bool(recompute_score)
        if recompute_score is not None
        else (intent in _auto_recompute and not score_parts)
    )

    effective_score = float(blend_score or 0.0)
    parts_meta: dict[str, Any] = dict(score_parts) if isinstance(score_parts, dict) else {}
    if do_recompute:
        try:
            from shared.membership_scoring import score_article_storyline_membership

            ms = score_article_storyline_membership(
                conn,
                domain_key=domain_key,
                storyline_id=eid,
                article_id=aid,
                schema=schema,
            )
            if ms.rejected and ms.reject_reason not in (
                "storyline_missing",
                "article_missing",
            ):
                # Soft signals empty (new episode): keep caller blend when present
                if effective_score <= 0:
                    _log_admit(
                        intent=intent,
                        outcome="reject",
                        mode=mode,
                        episode_id=eid,
                        article_id=aid,
                        reason=ms.reject_reason,
                    )
                    return False, ms.reject_reason
            else:
                if not ms.rejected:
                    effective_score = float(ms.combined)
                    parts_meta = ms.as_metadata()
                elif ms.combined > 0:
                    effective_score = float(ms.combined)
                    parts_meta = ms.as_metadata()
        except Exception as exc:
            logger.debug("admit recompute_score failed: %s", exc)

    # Tight-bag floors for automated intents (HITL / consolidation / API exempt)
    _floor_intents = {
        MembershipIntent.DISCOVERY_SEED,
        MembershipIntent.AUTOMATION,
        MembershipIntent.CONTINUATION,
        MembershipIntent.MEMBERSHIP_ADMIT,
        MembershipIntent.TOPIC_CONVERT,
    }
    if intent in _floor_intents:
        try:
            from services.domain_synthesis_config import get_domain_synthesis_config

            lsp = get_domain_synthesis_config(domain_key).link_score_profile
            floor = (
                float(lsp.discovery_seed_floor)
                if intent == MembershipIntent.DISCOVERY_SEED
                else float(lsp.auto_approve_combined)
            )
            if effective_score + 1e-9 < floor:
                _log_admit(
                    intent=intent,
                    outcome="reject",
                    mode=mode,
                    episode_id=eid,
                    article_id=aid,
                    reason=f"below_score_floor:{effective_score:.3f}<{floor:.3f}",
                )
                return False, f"below_score_floor:{floor}"
        except Exception as exc:
            logger.debug("admit score floor skip: %s", exc)

    # Block automated absorb into kitchen-sink / mega bags and rare-anchor collisions.
    if intent in _floor_intents:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT title,
                           COALESCE(is_mega_storyline, FALSE),
                           COALESCE(story_kind, '')
                    FROM {schema}.storylines
                    WHERE id = %s
                    """,
                    (eid,),
                )
                erow = cur.fetchone()
                if erow:
                    ep_title, is_mega, story_kind = erow[0], bool(erow[1]), (erow[2] or "")
                    if story_kind == "container_index" or is_mega:
                        _log_admit(
                            intent=intent,
                            outcome="reject",
                            mode=mode,
                            episode_id=eid,
                            article_id=aid,
                            reason="mega_or_container_absorb_blocked",
                        )
                        return False, "mega_or_container_absorb_blocked"
                    try:
                        from services.storyline_coherence_guardrails import (
                            title_looks_mega_bag,
                        )

                        if title_looks_mega_bag(ep_title or ""):
                            _log_admit(
                                intent=intent,
                                outcome="reject",
                                mode=mode,
                                episode_id=eid,
                                article_id=aid,
                                reason="kitchen_sink_title_absorb_blocked",
                            )
                            return False, "kitchen_sink_title_absorb_blocked"
                    except Exception:
                        pass
                    try:
                        from services.event_core_membership_service import (
                            should_block_mega_absorb,
                        )

                        cur.execute(
                            f"""
                            SELECT title, coalesce(summary, ''), left(coalesce(content, ''), 2000)
                            FROM {schema}.articles WHERE id = %s
                            """,
                            (aid,),
                        )
                        arow = cur.fetchone()
                        article = {
                            "id": aid,
                            "title": (arow[0] if arow else "") or "",
                            "summary": (arow[1] if arow else "") or "",
                            "content": (arow[2] if arow else "") or "",
                        }
                        block, reason, _anchors = should_block_mega_absorb(
                            cur,
                            domain_key=domain_key,
                            storyline_id=eid,
                            article=article,
                        )
                        if block:
                            _log_admit(
                                intent=intent,
                                outcome="reject",
                                mode=mode,
                                episode_id=eid,
                                article_id=aid,
                                reason=reason or "mega_absorb_blocked",
                            )
                            return False, reason or "mega_absorb_blocked"
                    except Exception as mega_e:
                        logger.debug("admit mega absorb check skip: %s", mega_e)
        except Exception as exc:
            logger.debug("admit mega/container gate skip: %s", exc)

    row_meta: dict[str, Any] = {"intent": intent.value}
    if bag_metadata:
        row_meta.update(bag_metadata)
    if parts_meta:
        row_meta.update(parts_meta if "score_parts" in parts_meta else {"score_parts": parts_meta})
        if "combined" not in row_meta:
            row_meta["combined"] = round(effective_score, 4)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT COALESCE(story_kind, ''), COALESCE(is_mega_storyline, FALSE)
            FROM {schema}.storylines WHERE id = %s
            """,
            (eid,),
        )
        row = cur.fetchone()
        if not row:
            _log_admit(
                intent=intent,
                outcome="reject",
                mode=mode,
                episode_id=eid,
                article_id=aid,
                reason="storyline_missing",
            )
            return False, "storyline_missing"
        skind, is_mega = row[0], bool(row[1])
        if (skind or "").lower() == "container_index" or is_mega:
            _log_admit(
                intent=intent,
                outcome="reject",
                mode=mode,
                episode_id=eid,
                article_id=aid,
                reason="container_index_no_membership",
            )
            return False, "container_index_no_membership"

        # Cap bag size + per-article arc count (HITL / consolidation exempt)
        _cap_exempt = {
            MembershipIntent.HITL_APPROVE,
            MembershipIntent.CONSOLIDATION_MOVE,
            MembershipIntent.API_MANUAL,
        }
        if intent not in _cap_exempt:
            try:
                from services.domain_synthesis_config import get_domain_synthesis_config

                lsp = get_domain_synthesis_config(domain_key).link_score_profile
                max_members = lsp.max_member_articles
                if max_members is not None:
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                        """,
                        (eid,),
                    )
                    n_members = int((cur.fetchone() or [0])[0] or 0)
                    if n_members >= int(max_members):
                        _log_admit(
                            intent=intent,
                            outcome="reject",
                            mode=mode,
                            episode_id=eid,
                            article_id=aid,
                            reason=f"max_member_articles:{max_members}",
                        )
                        return False, "max_member_articles"
                max_arcs = int(getattr(lsp, "max_storylines_per_article", 3) or 3)
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT sa.storyline_id)
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.storylines s ON s.id = sa.storyline_id
                    WHERE sa.article_id = %s
                      AND s.merged_into_id IS NULL
                      AND COALESCE(s.status, 'active') = 'active'
                      AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                      AND COALESCE(s.story_kind, '') <> 'container_index'
                    """,
                    (aid,),
                )
                n_arcs = int((cur.fetchone() or [0])[0] or 0)
                # Allow if already a member of this episode
                cur.execute(
                    f"""
                    SELECT 1 FROM {schema}.storyline_articles
                    WHERE storyline_id = %s AND article_id = %s
                    LIMIT 1
                    """,
                    (eid, aid),
                )
                already = cur.fetchone() is not None
                if not already and n_arcs >= max_arcs:
                    _log_admit(
                        intent=intent,
                        outcome="reject",
                        mode=mode,
                        episode_id=eid,
                        article_id=aid,
                        reason=f"max_storylines_per_article:{max_arcs}",
                    )
                    return False, "max_storylines_per_article"
            except Exception as exc:
                logger.debug("admit bag caps skip: %s", exc)

    if mode in (MembershipMode.EPISODE_EEL, MembershipMode.EPISODE_EEL_DUAL_WRITE):
        # Automated intents never bag-launder (liveblogs must stay event-grain).
        derive = mode == MembershipMode.EPISODE_EEL_DUAL_WRITE and intent not in _floor_intents
        n_ev, attach_reason = attach_article_events_to_episode(
            conn,
            domain_key=domain_key,
            schema=schema,
            episode_id=eid,
            article_id=aid,
            blend_rank=float(effective_score or 0.0),
            added_by=added_by,
            derive_storyline_article=derive,
        )
        if n_ev or attach_reason == "ok":
            _log_admit(
                intent=intent,
                outcome="eel_ok",
                mode=mode,
                episode_id=eid,
                article_id=aid,
                reason=f"events:{n_ev}",
            )
            _maybe_enqueue_finisher_after_admit(
                domain_key=domain_key,
                episode_id=eid,
                article_id=aid,
                intent=intent,
                membership_changed=bool(n_ev) or attach_reason == "ok",
            )
            return True, f"episode_events:{n_ev}"

        if mode == MembershipMode.EPISODE_EEL or intent in _floor_intents:
            reason = f"episode_no_events:{attach_reason}"
            with conn.cursor() as cur:
                _record_attach_block(cur, schema=schema, episode_id=eid, reason=reason)
            _log_admit(
                intent=intent,
                outcome="reject",
                mode=mode,
                episode_id=eid,
                article_id=aid,
                reason=reason,
            )
            return False, reason

        # DUAL_WRITE + HITL/manual only: thin bag seed when no CE yet
        try:
            from shared.assembly_link_funnel import allow_storyline_membership_attach

            ok_gate, gate_reason = allow_storyline_membership_attach(
                conn,
                domain_key=domain_key,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                blend_score=float(effective_score or 0.0),
                link_mode=mode_str,
            )
            if not ok_gate:
                reason = f"episode_no_events:{attach_reason}:{gate_reason}"
                _log_admit(
                    intent=intent,
                    outcome="reject",
                    mode=mode,
                    episode_id=eid,
                    article_id=aid,
                    reason=reason,
                )
                return False, reason
        except Exception as exc:
            return False, f"episode_no_events:{attach_reason}:{exc}"

        with conn.cursor() as cur:
            inserted = _insert_bag_row(
                cur,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                relevance_score=float(effective_score or 0.0),
                added_by=added_by,
                relationship_type="related",
                metadata={**row_meta, "thin_seed": attach_reason, "membership_role": "derived"},
            )
        _log_admit(
            intent=intent,
            outcome="bag_seed" if inserted else "bag_noop",
            mode=mode,
            episode_id=eid,
            article_id=aid,
            reason=attach_reason,
        )
        if inserted:
            _maybe_enqueue_finisher_after_admit(
                domain_key=domain_key,
                episode_id=eid,
                article_id=aid,
                intent=intent,
                membership_changed=True,
            )
        return inserted, f"episode_seed:{attach_reason}"

    # LEGACY_BAG
    if not episode_container_assembly_enabled():
        try:
            from shared.assembly_link_funnel import allow_storyline_membership_attach

            ok_gate, gate_reason = allow_storyline_membership_attach(
                conn,
                domain_key=domain_key,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                blend_score=float(effective_score or 0.0),
                link_mode=mode_str,
            )
            if not ok_gate:
                _log_admit(
                    intent=intent,
                    outcome="reject",
                    mode=mode,
                    episode_id=eid,
                    article_id=aid,
                    reason=gate_reason,
                )
                return False, gate_reason
        except Exception as exc:
            return False, f"gate_error:{exc}"

        with conn.cursor() as cur:
            inserted = _insert_bag_row(
                cur,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                relevance_score=float(effective_score or 0.0),
                added_by=added_by,
                metadata=row_meta or None,
            )
        _log_admit(
            intent=intent,
            outcome="bag_ok" if inserted else "bag_noop",
            mode=mode,
            episode_id=eid,
            article_id=aid,
        )
        if inserted:
            _maybe_enqueue_finisher_after_admit(
                domain_key=domain_key,
                episode_id=eid,
                article_id=aid,
                intent=intent,
                membership_changed=True,
            )
        return inserted or True, "membership_ok"

    return False, "unexpected_mode"


def insert_derived_bag_row(
    cur,
    *,
    schema: str,
    storyline_id: int,
    article_id: int,
    relevance_score: float,
    added_by: str,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Dual-write derived row from EEL attach (episode_attach_gate only)."""
    from shared.membership_mode import bag_writes_allowed

    if not bag_writes_allowed():
        return False
    # DB check allows related|core|supporting|context|background (not "derived").
    meta = dict(metadata or {})
    meta.setdefault("membership_role", "derived")
    return _insert_bag_row(
        cur,
        schema=schema,
        storyline_id=storyline_id,
        article_id=article_id,
        relevance_score=relevance_score,
        added_by=added_by,
        relationship_type="related",
        metadata=meta,
    )


def reconcile_derived_bag_from_eel(
    conn,
    *,
    domain_key: str,
    schema: str,
    episode_id: int,
) -> dict[str, int]:
    """Make storyline_articles match non-quarantined EEL→CE articles for one episode.

    ASSEMBLY_MODEL: bag is derived from EEL. Safe when episode_container_assembly is on.
    """
    from shared.episode_attach_gate import episode_container_assembly_enabled
    from shared.storyline_article_counts import sync_counts_update_sql

    if not episode_container_assembly_enabled():
        return {"skipped": 1, "inserted": 0, "removed": 0}
    eid = int(episode_id)
    stats = {"inserted": 0, "removed": 0, "eel_n": 0, "bag_n": 0}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ce.source_article_id
            FROM intelligence.event_episode_links eel
            JOIN public.chronological_events ce ON ce.id = eel.event_id
            WHERE eel.domain_key = %s
              AND eel.episode_id = %s
              AND COALESCE(eel.inference_stage, '') <> 'quarantined'
              AND ce.source_article_id IS NOT NULL
            """,
            (domain_key, eid),
        )
        eel_ids = {int(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None}
        stats["eel_n"] = len(eel_ids)
        cur.execute(
            f"""
            SELECT article_id FROM {schema}.storyline_articles
            WHERE storyline_id = %s
            """,
            (eid,),
        )
        bag_ids = {int(r[0]) for r in (cur.fetchall() or []) if r and r[0] is not None}
        stats["bag_n"] = len(bag_ids)
        for aid in sorted(eel_ids - bag_ids):
            if _insert_bag_row(
                cur,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                relevance_score=0.0,
                added_by="reconcile_derived_bag",
                relationship_type="related",
                metadata={"reconcile": "eel_to_bag", "membership_role": "derived"},
            ):
                stats["inserted"] += 1
        stale = sorted(bag_ids - eel_ids)
        if stale:
            _set_bag_write_session(cur)
            cur.execute(
                f"""
                DELETE FROM {schema}.storyline_articles
                WHERE storyline_id = %s
                  AND article_id = ANY(%s)
                """,
                (eid, stale),
            )
            stats["removed"] = int(cur.rowcount or 0)
        # sync_counts_update_sql embeds two %s placeholders for storyline_id.
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET {sync_counts_update_sql(schema)}, updated_at = NOW()
            WHERE id = %s
            """,
            (eid, eid, eid),
        )
    return stats


def reconcile_derived_bags_for_domain(
    conn,
    *,
    domain_key: str,
    schema: str,
    limit: int = 80,
) -> dict[str, Any]:
    """Reconcile active episodes that show bag↔EEL article-set drift."""
    from shared.episode_attach_gate import episode_container_assembly_enabled

    if not episode_container_assembly_enabled():
        return {"domain": domain_key, "skipped": True, "episodes": 0, "inserted": 0, "removed": 0}
    out = {"domain": domain_key, "episodes": 0, "inserted": 0, "removed": 0, "drift_found": 0}
    with conn.cursor() as cur:
        # Prefer set asymmetry (count match can still drift); fall back to count delta.
        cur.execute(
            f"""
            WITH eel_arts AS (
              SELECT eel.episode_id, ce.source_article_id AS article_id
              FROM intelligence.event_episode_links eel
              JOIN public.chronological_events ce ON ce.id = eel.event_id
              WHERE eel.domain_key = %s
                AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                AND ce.source_article_id IS NOT NULL
            ),
            bag_arts AS (
              SELECT storyline_id AS episode_id, article_id
              FROM {schema}.storyline_articles
            ),
            bad AS (
              SELECT episode_id FROM (
                SELECT episode_id, article_id FROM bag_arts
                EXCEPT
                SELECT episode_id, article_id FROM eel_arts
              ) x
              UNION
              SELECT episode_id FROM (
                SELECT episode_id, article_id FROM eel_arts
                EXCEPT
                SELECT episode_id, article_id FROM bag_arts
              ) y
            )
            SELECT DISTINCT b.episode_id
            FROM bad b
            JOIN {schema}.storylines s ON s.id = b.episode_id
            WHERE s.merged_into_id IS NULL
              AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
            ORDER BY b.episode_id
            LIMIT %s
            """,
            (domain_key, int(limit)),
        )
        episode_ids = [int(r[0]) for r in (cur.fetchall() or [])]
    for eid in episode_ids:
        out["drift_found"] += 1
        st = reconcile_derived_bag_from_eel(
            conn, domain_key=domain_key, schema=schema, episode_id=eid
        )
        out["episodes"] += 1
        out["inserted"] += int(st.get("inserted") or 0)
        out["removed"] += int(st.get("removed") or 0)
    return out


def copy_bag_rows(
    cur,
    *,
    schema: str,
    from_storyline_id: int,
    to_storyline_id: int,
    added_by: str = "consolidation_move",
    relevance_multiplier: float = 1.0,
) -> int:
    """Maintenance: copy bag rows between storylines (consolidation only)."""
    from shared.membership_mode import bag_writes_allowed

    if not bag_writes_allowed():
        return 0
    _set_bag_write_session(cur)
    cur.execute(
        f"""
        INSERT INTO {schema}.storyline_articles
            (storyline_id, article_id, relevance_score, added_by, created_at, updated_at)
        SELECT %s, sa.article_id, sa.relevance_score * %s, %s, NOW(), NOW()
        FROM {schema}.storyline_articles sa
        WHERE sa.storyline_id = %s
        ON CONFLICT (storyline_id, article_id) DO NOTHING
        """,
        (int(to_storyline_id), float(relevance_multiplier), added_by, int(from_storyline_id)),
    )
    return int(cur.rowcount or 0)


def admit_batch(
    conn,
    *,
    domain_key: str,
    schema: str,
    episode_id: int,
    article_ids: list[int],
    intent: MembershipIntent,
    blend_score: float = 0.0,
    added_by: str,
    link_mode: str | None = None,
) -> list[tuple[int, bool, str]]:
    results: list[tuple[int, bool, str]] = []
    for aid in article_ids:
        ok, reason = admit(
            conn,
            domain_key=domain_key,
            schema=schema,
            episode_id=episode_id,
            article_id=int(aid),
            intent=intent,
            blend_score=blend_score,
            added_by=added_by,
            link_mode=link_mode,
        )
        results.append((int(aid), ok, reason))
    return results
