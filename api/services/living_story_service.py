"""
Living story orchestration — promote quiet follows to published republish loop.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config.runtime import (
    living_republish_min_hours,
    living_republish_min_new_members,
)
from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.episode_attach_gate import parse_anchor_signature

from services.follow_service import get_follow_by_id, patch_follow, set_tier

logger = logging.getLogger(__name__)

_PRESENTATION_BY_KIND = {
    "event_narrative": "event_narrative",
    "market_regulatory_arc": "event_narrative",
    "evidence_thread": "research_brief",
    "research_topic": "research_brief",
    "matter_docket": "hybrid",
}

_RESEARCH_STORY_KINDS = frozenset({"evidence_thread", "research_topic"})


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _episode_story_kind(domain_key: str, episode_id: int) -> str | None:
    schema = resolve_domain_schema(domain_key)
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT story_kind FROM {schema}.storylines WHERE id = %s LIMIT 1",
                (int(episode_id),),
            )
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None


def _resolve_episode_entity_id(domain_key: str, episode_id: int) -> int | None:
    """Return a single canonical entity id when episode linkage is unambiguous."""
    schema = resolve_domain_schema(domain_key)
    if not schema:
        return None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT anchor_signature, metadata
                FROM {schema}.storylines
                WHERE id = %s
                LIMIT 1
                """,
                (int(episode_id),),
            )
            row = cur.fetchone()
    if not row:
        return None
    raw_sig, meta = row[0], row[1]
    sig = parse_anchor_signature(raw_sig)
    cids: list[int] = []
    for tok in sig.get("identity") or []:
        if isinstance(tok, str) and tok.startswith("cid:"):
            try:
                cids.append(int(tok[4:]))
            except ValueError:
                continue
    if len(cids) == 1:
        return cids[0]
    if isinstance(meta, dict):
        for key in ("source_canonical_entity_id", "canonical_entity_id"):
            raw = meta.get(key)
            if raw is not None:
                try:
                    return int(raw)
                except (TypeError, ValueError):
                    continue
    return None


def living_republish_allowed(package_id: int, new_member_count: int) -> tuple[bool, str]:
    """Throttle + quality-gate auto-republish for living-tracked packages."""
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, object_id, object_kind, metadata
                FROM intelligence.followed_items
                WHERE tier = 'living' AND status = 'active'
                  AND (metadata->>'package_id')::bigint = %s
                LIMIT 1
                """,
                (int(package_id),),
            )
            row = cur.fetchone()
    if not row:
        return True, "not_living_tracked"

    domain_key, object_id, object_kind, meta = row[0], row[1], row[2], row[3]
    meta = meta if isinstance(meta, dict) else {}

    quality_ok, quality_reason = _living_episode_quality_ok(
        domain_key=str(domain_key or "").strip(),
        object_id=int(object_id or 0),
        object_kind=str(object_kind or "").strip(),
    )
    if not quality_ok:
        return False, quality_reason

    last = meta.get("last_republish_at")
    if new_member_count >= living_republish_min_new_members():
        return True, "enough_new_members"
    if not last:
        return True, "no_prior_republish"
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
        if hours >= living_republish_min_hours():
            return True, "min_hours_elapsed"
        return False, f"throttled_{hours:.1f}h"
    except Exception:
        return True, "parse_fallback"


def _living_episode_quality_ok(
    *,
    domain_key: str,
    object_id: int,
    object_kind: str,
) -> tuple[bool, str]:
    """Block living auto-republish when episode is over attach cap or incoherent."""
    if object_kind != "episode" or not domain_key or object_id <= 0:
        return False, "living_episode_unresolved"

    schema = resolve_domain_schema(domain_key)
    if not schema:
        return False, "living_episode_unresolved"

    from shared.storyline_attach_caps import attach_hard_cap, storyline_at_or_over_attach_cap
    from services.storyline_coherence_guardrails import (
        assess_cluster_coherence,
        assess_kitchen_sink_risk,
    )

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, COALESCE(total_articles, 0)
                FROM {schema}.storylines
                WHERE id = %s
                LIMIT 1
                """,
                (int(object_id),),
            )
            srow = cur.fetchone()
            if not srow:
                return False, "living_episode_missing"
            title, article_count = srow[0], int(srow[1] or 0)

            if storyline_at_or_over_attach_cap(domain_key, article_count):
                return (
                    False,
                    f"over_attach_hard_cap:{article_count}>={attach_hard_cap(domain_key)}",
                )

            cur.execute(
                f"""
                SELECT a.title, COALESCE(a.summary, '') AS summary,
                       LEFT(COALESCE(a.content, ''), 2000) AS content
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                  AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
                ORDER BY COALESCE(sa.relevance_score, 0) DESC NULLS LAST, sa.article_id
                LIMIT 40
                """,
                (int(object_id),),
            )
            articles = [
                {"title": r[0], "summary": r[1], "content": r[2]}
                for r in (cur.fetchall() or [])
            ]

    sink, sink_reason = assess_kitchen_sink_risk(title, articles)
    if sink:
        return False, f"kitchen_sink:{sink_reason}"

    # Thin samples: still block kitchen-sink title patterns above; skip strict cohesion.
    if len(articles) < 2:
        return True, "quality_ok_thin"

    ok, coh_reason = assess_cluster_coherence(domain_key, title or "", articles)
    if not ok:
        return False, f"cohesion_fail:{coh_reason}"
    return True, "quality_ok"


def stamp_living_republish(package_id: int, *, new_member_ids: list[int], story_revision_id: int | None) -> None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, metadata FROM intelligence.followed_items
                WHERE tier = 'living' AND status = 'active'
                  AND (metadata->>'package_id')::bigint = %s
                LIMIT 1
                """,
                (int(package_id),),
            )
            row = cur.fetchone()
            if not row:
                return
            fid, meta = int(row[0]), row[1] if isinstance(row[1], dict) else {}
            log = list(meta.get("republish_log") or [])
            log.append(
                {
                    "at": datetime.now(timezone.utc).isoformat(),
                    "new_member_ids": new_member_ids[:50],
                    "story_revision_id": story_revision_id,
                }
            )
            meta["republish_log"] = log[-50:]
            meta["last_republish_at"] = datetime.now(timezone.utc).isoformat()
            cur.execute(
                """
                UPDATE intelligence.followed_items
                SET metadata = %s::jsonb,
                    last_surfaced_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(meta), fid),
            )
        conn.commit()


def _promote_research_living(
    follow_id: int,
    *,
    domain_key: str,
    episode_id: int,
    user_key: str,
    actor: str,
) -> dict[str, Any] | None:
    """Entity/knowledge-profile path for research-modal episodes."""
    from services.editorial_package_service import ensure_package_from_entity
    from services.knowledge_profile_service import (
        KNOWLEDGE_PROFILE_DOMAINS,
        auto_merge_from_package,
        publish_profile,
    )

    dk = str(domain_key).strip()
    if dk not in KNOWLEDGE_PROFILE_DOMAINS:
        return None
    entity_id = _resolve_episode_entity_id(dk, int(episode_id))
    if entity_id is None:
        return None

    pkg_out = ensure_package_from_entity(
        domain_key=dk,
        canonical_entity_id=int(entity_id),
        actor=actor,
        refresh_members=True,
    )
    package_id = int(pkg_out.get("package_id") or pkg_out["id"])
    profile_id = int(pkg_out["knowledge_profile_id"])

    merge = auto_merge_from_package(
        package_id,
        actor=actor,
        publish=True,
        regenerate=True,
    )
    if merge.get("skipped"):
        publish_profile(profile_id, actor=actor)

    meta_patch: dict[str, Any] = {
        "package_id": package_id,
        "knowledge_profile_id": profile_id,
        "canonical_entity_id": int(entity_id),
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "living_path": "knowledge_profile",
    }
    patch_follow(follow_id, user_key=user_key, metadata=meta_patch)

    return {
        "ok": True,
        "follow_id": follow_id,
        "package_id": package_id,
        "knowledge_profile_id": profile_id,
        "living_path": "knowledge_profile",
        "merge": merge,
    }


def _promote_standard_living(
    follow_id: int,
    *,
    domain_key: str,
    episode_id: int,
    user_key: str,
    actor: str,
) -> dict[str, Any]:
    from services.editorial_package_service import (
        ensure_package_from_storyline,
        get_package,
        primary_modal_for_domain,
        seed_heuristic_editor_links,
        update_package,
    )
    from services.news_story_service import create_or_update_draft, publish_story

    dk = str(domain_key).strip()
    eid = int(episode_id)
    modal = primary_modal_for_domain(dk)
    pkg_out = ensure_package_from_storyline(
        domain_key=dk,
        storyline_id=eid,
        target_modal=modal,
        actor=actor,
        refresh_members=True,
    )
    package_id = int(pkg_out.get("package_id") or pkg_out["id"])
    seed_heuristic_editor_links(package_id, actor=actor)

    story_kind = _episode_story_kind(dk, eid) or ""
    pres = _PRESENTATION_BY_KIND.get(story_kind, "event_narrative")
    update_package(
        package_id,
        presentation_kind=pres,
        actor=actor,
        modal=modal,
        rationale="living story presentation_kind",
    )

    pkg = get_package(package_id, include=False) or {}
    title = str(pkg.get("working_title") or f"Episode {eid}")[:500]
    draft = create_or_update_draft(
        package_id,
        title=title,
        lede="",
        body_md="",
        presentation_kind=pres,
        created_by=actor,
        actor=actor,
        advance_status=False,
    )
    story_row = draft.get("story") if isinstance(draft.get("story"), dict) else draft
    story_id = int(story_row["id"])

    pub = publish_story(
        story_id,
        actor=actor,
        assemble=True,
        extractive_fallback=True,
    )

    meta_patch: dict[str, Any] = {
        "package_id": package_id,
        "story_id": story_id,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "living_path": "news_story",
    }
    if not pub.get("published"):
        meta_patch["living_publish_error"] = (
            pub.get("block_reason") or pub.get("reason") or pub.get("gate") or "publish_blocked"
        )

    patch_follow(follow_id, user_key=user_key, metadata=meta_patch)

    return {
        "ok": True,
        "follow_id": follow_id,
        "package_id": package_id,
        "story_id": story_id,
        "living_path": "news_story",
        "publish": pub,
    }


def promote_to_living(follow_id: int, *, user_key: str = "operator", actor: str = "living_story") -> dict[str, Any]:
    follow = get_follow_by_id(follow_id, user_key=user_key)
    if not follow:
        raise LookupError(f"follow {follow_id} not found")
    if follow.get("object_kind") != "episode":
        raise ValueError("living promotion requires episode follow")
    dk = str(follow.get("domain_key") or "").strip()
    eid = int(follow.get("object_id") or 0)
    if not dk or eid <= 0:
        raise ValueError("invalid episode follow target")

    set_tier(follow_id, "living", user_key=user_key)

    story_kind = _episode_story_kind(dk, eid) or ""
    try:
        from services.knowledge_profile_service import KNOWLEDGE_PROFILE_DOMAINS

        if dk in KNOWLEDGE_PROFILE_DOMAINS and story_kind in _RESEARCH_STORY_KINDS:
            try:
                research_out = _promote_research_living(
                    follow_id,
                    domain_key=dk,
                    episode_id=eid,
                    user_key=user_key,
                    actor=actor,
                )
                if research_out is not None:
                    return research_out
            except (LookupError, ValueError):
                raise
            except Exception as exc:
                logger.warning(
                    "research living path failed follow=%s domain=%s episode=%s: %s",
                    follow_id,
                    dk,
                    eid,
                    exc,
                )

        return _promote_standard_living(
            follow_id,
            domain_key=dk,
            episode_id=eid,
            user_key=user_key,
            actor=actor,
        )
    except (LookupError, ValueError):
        raise
    except Exception as exc:
        logger.exception("promote_to_living failed follow_id=%s", follow_id)
        raise ValueError(f"living promotion failed: {type(exc).__name__}") from exc


def demote_to_quiet(follow_id: int, *, user_key: str = "operator") -> dict[str, Any]:
    row = set_tier(follow_id, "quiet", user_key=user_key)
    return {"ok": True, "follow": row}


def run_cooling_sweep(*, dry_run: bool = False) -> dict[str, Any]:
    """Pause living follows whose episodes stayed dormant/cooling past LIVING_COOLING_DAYS."""
    from config.runtime import living_cooling_days

    days = living_cooling_days()
    actions: list[dict[str, Any]] = []

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, object_id, metadata
                FROM intelligence.followed_items
                WHERE tier = 'living' AND status = 'active'
                  AND object_kind = 'episode'
                """
            )
            follows = cur.fetchall() or []

            for fid, dk, eid, meta in follows:
                schema = resolve_domain_schema(str(dk))
                cur.execute(
                    f"""
                    SELECT episode_state, episode_state_changed_at
                    FROM {schema}.storylines
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (int(eid),),
                )
                row = cur.fetchone()
                if not row:
                    continue
                state, changed = row[0], row[1]
                if str(state or "") not in ("dormant", "cooling"):
                    continue
                if not changed:
                    continue
                cur.execute(
                    "SELECT EXTRACT(EPOCH FROM (NOW() - %s)) / 86400.0",
                    (changed,),
                )
                age_days = float((cur.fetchone() or [0])[0] or 0)
                if age_days < days:
                    continue
                action = {
                    "follow_id": int(fid),
                    "domain_key": str(dk),
                    "episode_id": int(eid),
                    "episode_state": str(state),
                    "dormant_days": round(age_days, 1),
                }
                actions.append(action)
                if dry_run:
                    continue
                m = meta if isinstance(meta, dict) else {}
                m["cooling_paused_at"] = datetime.now(timezone.utc).isoformat()
                cur.execute(
                    """
                    UPDATE intelligence.followed_items
                    SET status = 'paused',
                        metadata = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(m), int(fid)),
                )
        if not dry_run:
            conn.commit()

    return {"ok": True, "paused": len(actions), "actions": actions, "dry_run": dry_run}
