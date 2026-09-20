"""Resolve NI context_entity_mentions → investigation resolved_mentions."""

from __future__ import annotations

import time
from typing import Any

from config.investigation_tables import T_PARKED_RESOLUTION, T_RESOLVED_MENTIONS
from nri_core.config import get_config, require_prod_safety
from nri_core.evidence import ni_reader
from nri_core.spine.api.lookup import match_mention
from nri_core.spine.resolution.lazy_mint import lazy_mint_on_miss

NON_ENTITY_TYPES = frozenset({"subject"})


def _dedupe_rows_by_context_mention(
    rows: list[tuple[Any, ...]],
) -> tuple[list[tuple[Any, ...]], int]:
    """Keep last row per (context_id, mention_text). Postgres rejects ON CONFLICT
    DO UPDATE when the same constrained key appears twice in one INSERT."""
    if not rows:
        return rows, 0
    by_key: dict[tuple[Any, Any], tuple[Any, ...]] = {}
    for row in rows:
        by_key[(row[0], row[1])] = row
    deduped = list(by_key.values())
    return deduped, len(rows) - len(deduped)


def _flush_resolutions(cur: Any, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    from psycopg2.extras import execute_values

    rows, _ = _dedupe_rows_by_context_mention(rows)

    execute_values(
        cur,
        f"""
        INSERT INTO {T_RESOLVED_MENTIONS}
            (context_id, mention_text, entity_profile_id, ftm_id,
             match_score, match_tier, status)
        VALUES %s
        ON CONFLICT (context_id, mention_text) DO UPDATE SET
            ftm_id = EXCLUDED.ftm_id,
            match_score = EXCLUDED.match_score,
            match_tier = EXCLUDED.match_tier,
            status = EXCLUDED.status,
            resolved_at = NOW()
        """,
        rows,
        page_size=200,
    )


def _flush_parks(cur: Any, rows: list[tuple[Any, ...]]) -> None:
    if not rows:
        return
    from psycopg2.extras import execute_values

    rows, _dropped = _dedupe_rows_by_context_mention(rows)

    execute_values(
        cur,
        f"""
        INSERT INTO {T_PARKED_RESOLUTION}
            (context_id, mention_text, candidate_ftm_id, match_score, reason)
        VALUES %s
        """,
        rows,
        page_size=200,
    )


def _should_skip_mention(mention: dict[str, Any]) -> bool:
    cfg = get_config()
    if not cfg.skip_subject_mentions:
        return False
    entity_type = (mention.get("entity_type") or "").lower()
    return entity_type in NON_ENTITY_TYPES


def resolve_batch(
    limit: int = 200,
    *,
    budget_deadline_mono: float | None = None,
) -> dict[str, Any]:
    cfg = get_config()
    if not cfg.write_resolved_mentions:
        return {"skipped": True, "reason": "NRI_WRITE_RESOLVED_MENTIONS=false"}

    require_prod_safety()

    stats: dict[str, Any] = {
        "processed": 0,
        "auto_linked": 0,
        "parked": 0,
        "provisional": 0,
        "non_entity_topic": 0,
        "rate_limited_stop": 0,
        "budget_stop": 0,
        "dup_skipped": 0,
        "last_id": 0,
    }
    resolution_rows: list[tuple[Any, ...]] = []
    park_rows: list[tuple[Any, ...]] = []
    bridge_jobs: list[dict[str, Any]] = []
    seen_context_mention: set[tuple[Any, str]] = set()
    watermark = 0
    max_id = 0
    mentions: list[dict[str, Any]] = []

    # 1) Fetch only — release DB before Wikidata/HTTP (holding conn across HTTP hung flush).
    with ni_reader.news_intel_connection() as conn:
        watermark = ni_reader.get_watermark("mention_resolver", conn=conn)
        mentions = ni_reader.fetch_new_mentions(since_id=watermark, limit=limit, conn=conn)
        try:
            conn.commit()
        except Exception:
            pass
    stats["last_id"] = watermark
    max_id = watermark

    # 2) Resolve in-memory (may call Wikidata / OpenSanctions).
    for mention in mentions:
        if budget_deadline_mono is not None and time.monotonic() >= budget_deadline_mono:
            stats["budget_stop"] = int(stats.get("budget_stop") or 0) + 1
            break
        mention_id = int(mention["id"])
        mention_text_early = str(mention.get("mention_text") or "")
        ctx_key = (int(mention["context_id"]), mention_text_early)
        if ctx_key in seen_context_mention:
            # Still advance watermark past duplicate CEM rows for same key.
            stats["dup_skipped"] = int(stats.get("dup_skipped") or 0) + 1
            stats["processed"] += 1
            max_id = max(max_id, mention_id)
            continue
        seen_context_mention.add(ctx_key)

        if _should_skip_mention(mention):
            resolution_rows.append(
                (
                    int(mention["context_id"]),
                    mention["mention_text"],
                    mention.get("entity_profile_id"),
                    None,
                    0.0,
                    0,
                    "non_entity_topic",
                )
            )
            stats["non_entity_topic"] += 1
            stats["processed"] += 1
            max_id = max(max_id, mention_id)
            continue

        mention_text = str(mention["mention_text"])
        if len(mention_text.strip()) > 0 and len(mention_text.strip()) < 4:
            resolution_rows.append(
                (
                    int(mention["context_id"]),
                    mention_text,
                    mention.get("entity_profile_id"),
                    None,
                    0.0,
                    2,
                    "parked",
                )
            )
            park_rows.append(
                (
                    int(mention["context_id"]),
                    mention_text,
                    None,
                    0.0,
                    "mention_too_short",
                )
            )
            stats["parked"] += 1
            stats["processed"] += 1
            max_id = max(max_id, mention_id)
            continue

        result = match_mention(text=mention_text)
        ftm_id = result.ftm_id
        score = result.score
        tier = result.tier
        status = result.status
        park_reason = "below_auto_link_threshold"

        if status != "auto_linked" and cfg.lazy_mint_enabled:
            lazy = lazy_mint_on_miss(
                mention_text=mention_text,
                context_id=int(mention["context_id"]),
                entity_profile_id=mention.get("entity_profile_id"),
                entity_type=mention.get("entity_type"),
            )
            if lazy.status == "rate_limited":
                stats["rate_limited_stop"] = int(stats.get("rate_limited_stop") or 0) + 1
                break
            if lazy.status == "provisional" and lazy.ftm_id:
                ftm_id = lazy.ftm_id
                score = lazy.score
                status = "provisional"
                stats["provisional"] += 1

        if status == "auto_linked" and ftm_id:
            from nri_core.evidence.bridge_qa import validate_bridge_link

            allowed, qa_reason = validate_bridge_link(
                mention_text=mention_text,
                ni_canonical_name=mention.get("canonical_name"),
                ni_entity_type=mention.get("entity_type"),
                ftm_id=ftm_id,
                match_score=score,
                match_tier=tier,
            )
            if not allowed:
                status = "parked"
                park_reason = qa_reason
                ftm_id = None

        resolution_rows.append(
            (
                int(mention["context_id"]),
                mention_text,
                mention.get("entity_profile_id"),
                ftm_id,
                score,
                tier,
                status,
            )
        )

        if status == "auto_linked":
            stats["auto_linked"] += 1
            if mention.get("entity_profile_id") and ftm_id:
                bridge_jobs.append(
                    {
                        "entity_profile_id": int(mention["entity_profile_id"]),
                        "ftm_id": ftm_id,
                        "bridge_score": score,
                        "mention_text": mention_text,
                        "ni_canonical_name": mention.get("canonical_name"),
                        "ni_entity_type": mention.get("entity_type"),
                        "match_tier": tier,
                    }
                )
        elif status == "provisional":
            pass
        else:
            stats["parked"] += 1
            candidate = result.candidates[0]["id"] if result.candidates else None
            park_rows.append(
                (
                    int(mention["context_id"]),
                    mention_text,
                    candidate,
                    result.score,
                    park_reason,
                )
            )
        stats["processed"] += 1
        max_id = max(max_id, mention_id)

    # 3) Fresh connection for writes — advance watermark before optional bridges.
    try:
        with ni_reader.news_intel_connection() as conn:
            with conn.cursor() as cur:
                _flush_resolutions(cur, resolution_rows)
                _flush_parks(cur, park_rows)
            if max_id > watermark:
                ni_reader.set_watermark("mention_resolver", max_id, conn=conn)
            conn.commit()
            stats["last_id"] = max_id
    except Exception:
        raise

    # 4) Bridges after watermark commit; skip when budget-stopped (avoid long hang).
    if bridge_jobs and not stats.get("budget_stop"):
        from nri_core.evidence.entity_bridge import bridge_auto_link

        for job in bridge_jobs[:50]:
            try:
                bridge_auto_link(**job)
            except Exception:
                pass

    return stats


def _resolve_batch_limit(default: int = 500) -> int:
    from config.runtime import mention_resolve_batch_limit

    try:
        return mention_resolve_batch_limit()
    except Exception:
        return default


def _resolve_drain_budget_seconds(default: float = 840.0) -> float:
    from config.runtime import mention_resolve_budget_seconds

    try:
        return mention_resolve_budget_seconds()
    except Exception:
        return default


def resolve_drain(
    *,
    limit: int | None = None,
    budget_seconds: float | None = None,
    max_batches: int = 0,
) -> dict[str, Any]:
    """
    Run mention resolver batches until idle, budget exhausted, or max_batches reached.

    Intended for systemd oneshot: one timer tick drains CEM backlog proportional to
    creation rate without starving other Widow work.
    """
    batch_limit = int(limit) if limit is not None else _resolve_batch_limit()
    try:
        if get_config().lazy_mint_enabled:
            # Smaller batches = more frequent watermark commits under Wikidata latency.
            from config.runtime import mention_resolve_lazy_mint_batch_cap

            batch_limit = min(batch_limit, mention_resolve_lazy_mint_batch_cap())
    except Exception:
        batch_limit = min(batch_limit, 250)
    budget = float(budget_seconds) if budget_seconds is not None else _resolve_drain_budget_seconds()
    t0 = time.monotonic()
    deadline = (t0 + budget) if budget > 0 else None
    totals: dict[str, Any] = {
        "batches": 0,
        "processed": 0,
        "auto_linked": 0,
        "parked": 0,
        "provisional": 0,
        "non_entity_topic": 0,
        "rate_limited_stop": 0,
        "budget_stop": 0,
        "last_id": ni_reader.get_watermark("mention_resolver"),
        "budget_seconds": budget,
        "batch_limit": batch_limit,
    }

    while True:
        if max_batches > 0 and totals["batches"] >= max_batches:
            break
        if budget > 0 and (time.monotonic() - t0) >= budget:
            break

        stats = resolve_batch(limit=batch_limit, budget_deadline_mono=deadline)
        if stats.get("skipped"):
            totals["skipped"] = True
            totals["skip_reason"] = stats.get("reason")
            break

        processed = int(stats.get("processed") or 0)
        totals["batches"] += 1
        for key in (
            "processed",
            "auto_linked",
            "parked",
            "provisional",
            "non_entity_topic",
            "rate_limited_stop",
            "budget_stop",
        ):
            totals[key] = int(totals.get(key, 0) or 0) + int(stats.get(key) or 0)
        totals["last_id"] = stats.get("last_id", totals["last_id"])

        if int(stats.get("rate_limited_stop") or 0) > 0:
            break
        if int(stats.get("budget_stop") or 0) > 0:
            break
        if processed == 0:
            break

    totals["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    return totals
