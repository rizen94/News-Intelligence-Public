"""
Pulse digest — ranked episode/container movement for a time window (read-only scoring).
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from config.runtime import (
    pulse_bonus_cross_domain,
    pulse_bonus_lifecycle_active,
    pulse_bonus_new_episode,
    pulse_bonus_reactivation,
    pulse_default_limit,
    pulse_default_window_hours,
    pulse_stubs_enabled,
    pulse_stubs_top_n,
)
from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

from services.editorial_package_service import (
    find_package_by_legacy_seed,
    legacy_seed_for_storyline,
)

logger = logging.getLogger(__name__)

_MOVEMENT_LIMIT = 5

_TOKEN = re.compile(r"[a-z0-9']{4,}", re.I)
_THEME_STOP = frozenset(
    {
        "with",
        "from",
        "that",
        "this",
        "have",
        "been",
        "will",
        "were",
        "their",
        "about",
        "after",
        "before",
        "when",
        "where",
        "which",
        "while",
        "into",
        "over",
        "under",
        "between",
        "arxiv",
    }
)


def _movement_tokens(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN.findall((text or "").lower()):
        if len(tok) < 4 or tok in _THEME_STOP or tok.isdigit():
            continue
        out.add(tok)
    return out


def _event_tokens_from_summary(movement_summary: list[dict[str, Any]]) -> set[str]:
    toks: set[str] = set()
    for ev in movement_summary or []:
        toks |= _movement_tokens(str(ev.get("title") or ""))
    return toks


def _stub_overlaps_events(stub: str, movement_summary: list[dict[str, Any]]) -> bool:
    event_toks = _event_tokens_from_summary(movement_summary)
    if not event_toks:
        return False
    stub_toks = _movement_tokens(stub)
    sig_events = {t for t in event_toks if len(t) >= 4}
    sig_stub = {t for t in stub_toks if len(t) >= 4}
    return bool(sig_events & sig_stub)


def _generate_movement_stub(item: dict[str, Any]) -> str | None:
    """Optional LLM stub — returns None when overlap check fails or LLM unavailable."""
    movement = list(item.get("movement_summary") or [])
    if not movement:
        return None
    title = str(item.get("title") or "Episode")
    events = "\n".join(
        f"- {ev.get('title') or 'Event'}" + (f" ({ev.get('event_date')})" if ev.get("event_date") else "")
        for ev in movement[:5]
    )
    prompt = (
        "Write 1-2 sentences explaining why this news episode is moving now.\n"
        "Rules:\n"
        "- Name a concrete actor or organization that did something (not a venue like arXiv).\n"
        "- Reference at least one event from the list below.\n"
        "- Focus on what changed, who did it, and why it matters.\n"
        "- If you cannot say that in two sentences, reply with exactly: NONE\n\n"
        f"Episode: {title}\n\nRecent events:\n{events}\n\nSummary:"
    )

    async def _run() -> str:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.INTERACTIVE_SUMMARY,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return (result.text or "").strip()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    try:
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                raw = pool.submit(lambda: asyncio.run(_run())).result(timeout=90)
        else:
            raw = asyncio.run(_run())
    except Exception as exc:
        logger.debug("pulse movement stub LLM skipped: %s", exc)
        return None

    text = (raw or "").strip()
    if not text or text.upper() == "NONE":
        return None
    text = text.split("\n\n")[0].strip()
    if len(text) > 320:
        text = text[:317].rstrip() + "…"
    if not _stub_overlaps_events(text, movement):
        return None
    return text


def _apply_movement_stubs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not pulse_stubs_enabled():
        return items
    top_n = pulse_stubs_top_n()
    out: list[dict[str, Any]] = []
    generated = 0
    for item in items:
        if generated >= top_n or not item.get("movement_summary"):
            out.append(item)
            continue
        stub = _generate_movement_stub(item)
        out.append({**item, "movement_stub": stub})
        if stub:
            generated += 1
    return out


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
          SELECT 1 FROM information_schema.tables
          WHERE table_schema = %s AND table_name = %s
        )
        """,
        (schema, table),
    )
    return bool((cur.fetchone() or [False])[0])


def _resolve_published_story_id(domain_key: str, episode_id: int) -> int | None:
    seed = legacy_seed_for_storyline(domain_key, int(episode_id))
    pkg = find_package_by_legacy_seed(seed)
    if not pkg:
        return None
    pid = int(pkg["id"])
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.news_stories
                WHERE package_id = %s AND status = 'published'
                ORDER BY published_at DESC NULLS LAST, id DESC
                LIMIT 1
                """,
                (pid,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None


def _movement_for_episode(
    cur, domain_key: str, episode_id: int, since: datetime, limit: int = _MOVEMENT_LIMIT
) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT ce.id, ce.title, ce.actual_event_date
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND eel.inference_stage <> 'quarantined'
          AND eel.created_at >= %s
        ORDER BY ce.actual_event_date DESC NULLS LAST, ce.id DESC
        LIMIT %s
        """,
        (domain_key, int(episode_id), since, limit),
    )
    out: list[dict[str, Any]] = []
    for eid, title, edate in cur.fetchall() or []:
        out.append(
            {
                "event_id": int(eid),
                "title": (title or "")[:240],
                "event_date": edate.isoformat() if edate else None,
            }
        )
    return out


def _item_include_gate_text(item: dict[str, Any]) -> str:
    """Title + recent movement titles — enough for pulse opt-in allowlists."""
    from services.domain_synthesis_config import topic_gate_text

    moves = []
    for ev in item.get("movement_summary") or []:
        if isinstance(ev, dict) and ev.get("title"):
            moves.append(str(ev.get("title")))
    return topic_gate_text(str(item.get("title") or ""), extra=" ".join(moves))


def _domain_has_include_keywords(domain_key: str) -> bool:
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        return get_domain_synthesis_config(domain_key).has_include_keywords()
    except Exception:
        # Unknown — treat as allowlist domain so early/fail-closed paths stay conservative.
        return True


def _passes_domain_include_gate(
    item: dict[str, Any],
    *,
    domain_key: str | None = None,
) -> bool:
    """
    Opt-in topic gate from domain_synthesis_config topic_filter.include_keywords.

    Domains without include_keywords are unchanged. Domains with an allowlist only
    surface when the card text matches. Config errors fail-closed when the domain
    has (or may have) include_keywords.
    """
    dk = (domain_key or str(item.get("domain_key") or "")).strip()
    if not dk:
        return True
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(dk)
        if not cfg.has_include_keywords():
            return True
        return cfg.passes_include_topic_gate(_item_include_gate_text(item))
    except Exception as exc:
        logger.warning("pulse include gate failed for domain=%s: %s", dk, exc)
        return False


def _item_passes_pulse_domain_gates(
    item: dict[str, Any],
    *,
    domain_filter: str | None,
) -> bool:
    """Domain scope + include allowlist before scoring / publish resolve."""
    df = (domain_filter or "").strip() or None
    dk = str(item.get("domain_key") or "").strip()
    if df:
        dks = item.get("domain_keys")
        in_list = isinstance(dks, list) and df in [str(x) for x in dks]
        if dk != df and not in_list:
            return False
        return _passes_domain_include_gate(item, domain_key=df)
    return _passes_domain_include_gate(item)


def _filter_pulse_items(
    items: list[dict[str, Any]],
    *,
    domain_filter: str | None,
) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if _item_passes_pulse_domain_gates(item, domain_filter=domain_filter)
    ]


def get_episode_velocity(
    window_hours: int | None = None,
    *,
    domain_filter: str | None = None,
) -> list[dict[str, Any]]:
    hours = int(window_hours or pulse_default_window_hours())
    domains = [domain_filter] if domain_filter else list(get_pipeline_active_domain_keys())
    domains = [d for d in domains if d]
    since = datetime.now(timezone.utc).replace(microsecond=0)
    # SQL interval uses hours param
    rows_out: list[dict[str, Any]] = []

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT eel.domain_key, eel.episode_id, COUNT(*)::int AS velocity
                FROM intelligence.event_episode_links eel
                WHERE eel.created_at >= NOW() - (%s || ' hours')::interval
                  AND eel.inference_stage <> 'quarantined'
                  AND eel.domain_key = ANY(%s)
                GROUP BY eel.domain_key, eel.episode_id
                HAVING COUNT(*) > 0
                """,
                (str(hours), domains),
            )
            velocity_rows = cur.fetchall() or []

            for dk, eid, velocity in velocity_rows:
                schema = resolve_domain_schema(str(dk))
                if not _table_exists(cur, schema, "storylines"):
                    continue
                cur.execute(
                    f"""
                    SELECT id, title, story_kind, episode_state, created_at,
                           episode_state_changed_at
                    FROM {schema}.storylines
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (int(eid),),
                )
                meta = cur.fetchone()
                if not meta:
                    continue
                _id, title, story_kind, episode_state, created_at, state_changed = meta
                if str(story_kind or "") == "container_index":
                    continue
                # Early include allowlist (title-only) before cross-domain / movement queries.
                df = (domain_filter or "").strip() or None
                if df and _domain_has_include_keywords(df):
                    probe = {
                        "title": title or "",
                        "movement_summary": [],
                        "domain_key": str(dk),
                    }
                    if not _passes_domain_include_gate(probe, domain_key=df):
                        continue
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT domain_key)::int
                    FROM intelligence.event_episode_links
                    WHERE event_id IN (
                        SELECT event_id FROM intelligence.event_episode_links
                        WHERE domain_key = %s AND episode_id = %s
                          AND inference_stage <> 'quarantined'
                    )
                      AND inference_stage <> 'quarantined'
                    """,
                    (str(dk), int(eid)),
                )
                cross_domains = int((cur.fetchone() or [1])[0] or 1)
                cur.execute(
                    """
                    SELECT ce.id, ce.title, ce.actual_event_date
                    FROM intelligence.event_episode_links eel
                    JOIN public.chronological_events ce ON ce.id = eel.event_id
                    WHERE eel.domain_key = %s AND eel.episode_id = %s
                      AND eel.inference_stage <> 'quarantined'
                      AND eel.created_at >= NOW() - (%s || ' hours')::interval
                    ORDER BY ce.actual_event_date DESC NULLS LAST, ce.id DESC
                    LIMIT %s
                    """,
                    (str(dk), int(eid), str(hours), _MOVEMENT_LIMIT),
                )
                movement = [
                    {
                        "event_id": int(r[0]),
                        "title": (r[1] or "")[:240],
                        "event_date": r[2].isoformat() if r[2] else None,
                    }
                    for r in (cur.fetchall() or [])
                ]
                rows_out.append(
                    {
                        "object_kind": "container"
                        if str(story_kind or "") == "container_index"
                        else "episode",
                        "domain_key": str(dk),
                        "id": int(_id),
                        "title": (title or f"Episode {eid}")[:500],
                        "story_kind": story_kind,
                        "episode_state": episode_state,
                        "velocity": int(velocity),
                        "movement_summary": movement,
                        "cross_domain_count": cross_domains,
                        "created_at": created_at,
                        "episode_state_changed_at": state_changed,
                    }
                )
    return rows_out


def get_lifecycle_transitions(window_hours: int | None = None) -> dict[tuple[str, int], str]:
    """Return {(domain_key, episode_id): transition_kind} for scoring bonuses."""
    hours = int(window_hours or pulse_default_window_hours())
    out: dict[tuple[str, int], str] = {}
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                if not _table_exists(cur, schema, "storylines"):
                    continue
                cur.execute(
                    f"""
                    SELECT id, episode_state, episode_state_changed_at
                    FROM {schema}.storylines
                    WHERE episode_state_changed_at >= NOW() - (%s || ' hours')::interval
                    """,
                    (str(hours),),
                )
                for eid, state, _changed in cur.fetchall() or []:
                    key = (str(dk), int(eid))
                    st = str(state or "")
                    if st == "active":
                        out[key] = "activated"
                    elif st in ("dormant", "cooling"):
                        out[key] = "cooling"
                    else:
                        out[key] = "other"
    return out


def get_new_episodes(window_hours: int | None = None) -> set[tuple[str, int]]:
    hours = int(window_hours or pulse_default_window_hours())
    found: set[tuple[str, int]] = set()
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                if not _table_exists(cur, schema, "storylines"):
                    continue
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.storylines
                    WHERE created_at >= NOW() - (%s || ' hours')::interval
                      AND COALESCE(story_kind, '') <> 'container_index'
                    """,
                    (str(hours),),
                )
                for (eid,) in cur.fetchall() or []:
                    found.add((str(dk), int(eid)))
    return found


def get_container_movement(
    window_hours: int | None = None,
    *,
    domain_filter: str | None = None,
) -> list[dict[str, Any]]:
    hours = int(window_hours or pulse_default_window_hours())
    out: list[dict[str, Any]] = []
    df = (domain_filter or "").strip() or None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT te.id, te.event_name, te.container_kind, te.domain_keys,
                       te.updated_at
                FROM intelligence.tracked_events te
                WHERE te.container_kind IS NOT NULL
                  AND te.updated_at >= NOW() - (%s || ' hours')::interval
                ORDER BY te.updated_at DESC NULLS LAST
                LIMIT 50
                """,
                (str(hours),),
            )
            for tid, name, kind, domain_keys, updated_at in cur.fetchall() or []:
                dks = domain_keys if isinstance(domain_keys, list) else []
                dks_s = [str(x) for x in dks]
                if df and df not in dks_s:
                    continue
                dk = str(dks_s[0]) if dks_s else (df or None)
                out.append(
                    {
                        "object_kind": "container",
                        "domain_key": dk,
                        "domain_keys": dks_s,
                        "id": int(tid),
                        "title": (name or f"Container {tid}")[:500],
                        "story_kind": "container_index",
                        "episode_state": None,
                        "velocity": 1,
                        "movement_summary": [],
                        "container_kind": kind,
                        "cross_domain_count": max(1, len(dks_s)),
                        "updated_at": updated_at.isoformat() if updated_at else None,
                    }
                )
    return out


def _score_item(
    item: dict[str, Any],
    *,
    lifecycle: dict[tuple[str, int], str],
    new_episodes: set[tuple[str, int]],
) -> tuple[float, dict[str, float]]:
    key = (str(item.get("domain_key") or ""), int(item.get("id") or 0))
    velocity = float(item.get("velocity") or 0)
    breakdown = {"velocity": velocity}
    score = velocity
    if key in new_episodes:
        bonus = pulse_bonus_new_episode()
        breakdown["new_episode"] = bonus
        score += bonus
    trans = lifecycle.get(key)
    if trans == "activated":
        bonus = pulse_bonus_lifecycle_active()
        breakdown["lifecycle_active"] = bonus
        score += bonus
    cross = int(item.get("cross_domain_count") or 1)
    if cross > 1:
        bonus = pulse_bonus_cross_domain()
        breakdown["cross_domain"] = bonus
        score += bonus
    return score, breakdown


def compute_pulse(
    window_hours: int | None = None,
    limit: int | None = None,
    *,
    domain_filter: str | None = None,
) -> dict[str, Any]:
    hours = int(window_hours or pulse_default_window_hours())
    lim = int(limit or pulse_default_limit())
    episodes = get_episode_velocity(hours, domain_filter=domain_filter)
    lifecycle = get_lifecycle_transitions(hours)
    new_eps = get_new_episodes(hours)
    containers = get_container_movement(hours, domain_filter=domain_filter)

    scored: list[dict[str, Any]] = []
    episode_keys: set[tuple[str, int]] = set()

    for item in episodes:
        if item.get("object_kind") == "container":
            continue
        if not _item_passes_pulse_domain_gates(item, domain_filter=domain_filter):
            continue
        key = (str(item["domain_key"]), int(item["id"]))
        episode_keys.add(key)
        score, breakdown = _score_item(item, lifecycle=lifecycle, new_episodes=new_eps)
        pub_id = _resolve_published_story_id(str(item["domain_key"]), int(item["id"]))
        scored.append(
            {
                **item,
                "score": score,
                "score_breakdown": breakdown,
                "published_story_id": pub_id,
                "movement_stub": None,
            }
        )

    for c in containers:
        if not _item_passes_pulse_domain_gates(c, domain_filter=domain_filter):
            continue
        key = (str(c.get("domain_key") or ""), int(c.get("id") or 0))
        if key in episode_keys:
            continue
        scored.append(
            {
                **c,
                "score": float(c.get("velocity") or 1),
                "score_breakdown": {"container_update": 1.0},
                "published_story_id": None,
                "movement_stub": None,
            }
        )

    scored = _filter_pulse_items(scored, domain_filter=domain_filter)
    scored.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    items = scored[:lim]
    return {
        "ok": True,
        "window_hours": hours,
        "limit": lim,
        "domain_filter": domain_filter,
        "items": items,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def get_followed_movement(
    user_key: str = "operator",
    window_hours: int | None = None,
) -> list[dict[str, Any]]:
    """Ranked movement for followed objects since last_read_at."""
    hours = int(window_hours or pulse_default_window_hours())
    pulse = compute_pulse(window_hours=hours, limit=200)
    all_items = { (i.get("object_kind"), i.get("domain_key"), i.get("id")): i for i in pulse.get("items") or [] }

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, object_kind, domain_key, object_id, tier, status,
                       last_read_at, last_surfaced_at, metadata
                FROM intelligence.followed_items
                WHERE user_key = %s AND status = 'active'
                ORDER BY COALESCE(last_surfaced_at, created_at) DESC
                """,
                (user_key,),
            )
            follows = cur.fetchall() or []

    out: list[dict[str, Any]] = []
    for fid, kind, dk, oid, tier, status, last_read, surfaced, meta in follows:
        if last_read and surfaced and surfaced <= last_read:
            continue
        key = (kind, dk, int(oid))
        card = all_items.get(key)
        if not card:
            continue
        out.append(
            {
                "follow_id": int(fid),
                "tier": tier,
                "status": status,
                "last_read_at": last_read.isoformat() if last_read else None,
                "last_surfaced_at": surfaced.isoformat() if surfaced else None,
                "metadata": meta if isinstance(meta, dict) else {},
                **card,
            }
        )
    out.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    return out


def stamp_followed_movement(scored_items: list[dict[str, Any]], user_key: str = "operator") -> int:
    """Update last_surfaced_at for active follows that appear in scored_items."""
    if not scored_items:
        return 0
    keys: list[tuple[str, str | None, int]] = []
    for item in scored_items:
        if item.get("object_kind") not in ("episode", "container", "package"):
            continue
        keys.append(
            (str(item["object_kind"]), item.get("domain_key"), int(item["id"]))
        )
    if not keys:
        return 0
    updated = 0
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            for kind, dk, oid in keys:
                cur.execute(
                    """
                    UPDATE intelligence.followed_items
                    SET last_surfaced_at = NOW(), updated_at = NOW()
                    WHERE user_key = %s AND status = 'active'
                      AND object_kind = %s
                      AND domain_key IS NOT DISTINCT FROM %s
                      AND object_id = %s
                    """,
                    (user_key, kind, dk, int(oid)),
                )
                updated += cur.rowcount
        conn.commit()
    return updated


def run_pulse_digest_job(
    *,
    window_hours: int | None = None,
    limit: int | None = None,
    user_key: str = "operator",
) -> dict[str, Any]:
    """Compute pulse, stamp active follows, persist snapshot. Used by cron/automation."""
    import json

    payload = compute_pulse(window_hours=window_hours, limit=limit)
    items = list(payload.get("items") or [])
    items = _apply_movement_stubs(items)
    stamped = stamp_followed_movement(items, user_key=user_key)
    snap_id = None
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.pulse_snapshots
                    (window_hours, items, metadata)
                VALUES (%s, %s::jsonb, %s::jsonb)
                RETURNING id
                """,
                (
                    int(payload.get("window_hours") or window_hours or pulse_default_window_hours()),
                    json.dumps(items, default=str),
                    json.dumps(
                        {
                            "generated_at": payload.get("generated_at"),
                            "stamped_follows": stamped,
                            "item_count": len(items),
                            "movement_stubs_enabled": pulse_stubs_enabled(),
                            "movement_stubs_generated": sum(
                                1 for i in items if i.get("movement_stub")
                            ),
                        }
                    ),
                ),
            )
            row = cur.fetchone()
            snap_id = int(row[0]) if row else None
        conn.commit()
    return {
        "ok": True,
        "items": len(items),
        "stamped_follows": stamped,
        "snapshot_id": snap_id,
        "window_hours": payload.get("window_hours"),
    }
