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
                json.dumps(metadata or {}),
            ),
        )
    else:
        cur.execute(
            f"""
            INSERT INTO {schema}.storyline_articles
            (storyline_id, article_id, relevance_score, added_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (storyline_id, article_id) DO NOTHING
            """,
            (int(storyline_id), int(article_id), float(relevance_score), added_by),
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
) -> tuple[bool, str]:
    """
    Admit an article to an episode. Returns (success, reason).

    EPISODE_EEL: EEL attach only — no bag fallback on failure.
    EPISODE_EEL_DUAL_WRITE: EEL + optional derived/thin bag rows.
    LEGACY_BAG: funnel gate + bag insert.
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

    if mode in (MembershipMode.EPISODE_EEL, MembershipMode.EPISODE_EEL_DUAL_WRITE):
        derive = mode == MembershipMode.EPISODE_EEL_DUAL_WRITE
        n_ev, attach_reason = attach_article_events_to_episode(
            conn,
            domain_key=domain_key,
            schema=schema,
            episode_id=eid,
            article_id=aid,
            blend_rank=float(blend_score or 0.0),
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
            return True, f"episode_events:{n_ev}"

        if mode == MembershipMode.EPISODE_EEL:
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

        # DUAL_WRITE: thin bag seed when no CE yet
        try:
            from shared.assembly_link_funnel import allow_storyline_membership_attach

            ok_gate, gate_reason = allow_storyline_membership_attach(
                conn,
                domain_key=domain_key,
                schema=schema,
                storyline_id=eid,
                article_id=aid,
                blend_score=float(blend_score or 0.0),
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
                relevance_score=float(blend_score or 0.0),
                added_by=added_by,
                relationship_type="derived",
                metadata={"intent": intent.value, "thin_seed": attach_reason},
            )
        _log_admit(
            intent=intent,
            outcome="bag_seed" if inserted else "bag_noop",
            mode=mode,
            episode_id=eid,
            article_id=aid,
            reason=attach_reason,
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
                blend_score=float(blend_score or 0.0),
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
                relevance_score=float(blend_score or 0.0),
                added_by=added_by,
            )
        _log_admit(
            intent=intent,
            outcome="bag_ok" if inserted else "bag_noop",
            mode=mode,
            episode_id=eid,
            article_id=aid,
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
    return _insert_bag_row(
        cur,
        schema=schema,
        storyline_id=storyline_id,
        article_id=article_id,
        relevance_score=relevance_score,
        added_by=added_by,
        relationship_type="derived",
        metadata=metadata,
    )


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
