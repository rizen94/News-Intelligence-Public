"""Resolve NI context_entity_mentions → investigation resolved_mentions."""

from __future__ import annotations

import os
import time
from typing import Any

from config.investigation_tables import T_PARKED_RESOLUTION, T_RESOLVED_MENTIONS
from nri_core.config import get_config, require_prod_safety
from nri_core.evidence import ni_reader
from nri_core.spine.api.lookup import match_mention
from nri_core.spine.resolution.lazy_mint import lazy_mint_on_miss

NON_ENTITY_TYPES = frozenset({"subject"})


def _insert_resolution(
    context_id: int,
    mention_text: str,
    entity_profile_id: int | None,
    ftm_id: str | None,
    score: float,
    tier: int,
    status: str,
) -> None:
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_RESOLVED_MENTIONS}
                    (context_id, mention_text, entity_profile_id, ftm_id,
                     match_score, match_tier, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (context_id, mention_text) DO UPDATE SET
                    ftm_id = EXCLUDED.ftm_id,
                    match_score = EXCLUDED.match_score,
                    match_tier = EXCLUDED.match_tier,
                    status = EXCLUDED.status,
                    resolved_at = NOW()
                """,
                (context_id, mention_text, entity_profile_id, ftm_id, score, tier, status),
            )
        conn.commit()


def _park_mention(
    context_id: int,
    mention_text: str,
    candidate_ftm_id: str | None,
    score: float,
    reason: str,
) -> None:
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_PARKED_RESOLUTION}
                    (context_id, mention_text, candidate_ftm_id, match_score, reason)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (context_id, mention_text, candidate_ftm_id, score, reason),
            )
        conn.commit()


def _should_skip_mention(mention: dict[str, Any]) -> bool:
    cfg = get_config()
    if not cfg.skip_subject_mentions:
        return False
    entity_type = (mention.get("entity_type") or "").lower()
    return entity_type in NON_ENTITY_TYPES


def resolve_batch(limit: int = 200) -> dict[str, Any]:
    cfg = get_config()
    if not cfg.write_resolved_mentions:
        return {"skipped": True, "reason": "NRI_WRITE_RESOLVED_MENTIONS=false"}

    require_prod_safety()
    watermark = ni_reader.get_watermark("mention_resolver")
    mentions = ni_reader.fetch_new_mentions(since_id=watermark, limit=limit)

    stats: dict[str, Any] = {
        "processed": 0,
        "auto_linked": 0,
        "parked": 0,
        "provisional": 0,
        "non_entity_topic": 0,
        "last_id": watermark,
    }
    max_id = watermark

    for mention in mentions:
        max_id = max(max_id, int(mention["id"]))

        if _should_skip_mention(mention):
            _insert_resolution(
                context_id=int(mention["context_id"]),
                mention_text=mention["mention_text"],
                entity_profile_id=mention.get("entity_profile_id"),
                ftm_id=None,
                score=0.0,
                tier=0,
                status="non_entity_topic",
            )
            stats["non_entity_topic"] += 1
            stats["processed"] += 1
            continue

        mention_text = str(mention["mention_text"])
        if len(mention_text.strip()) > 0 and len(mention_text.strip()) < 4:
            _insert_resolution(
                context_id=int(mention["context_id"]),
                mention_text=mention_text,
                entity_profile_id=mention.get("entity_profile_id"),
                ftm_id=None,
                score=0.0,
                tier=2,
                status="parked",
            )
            stats["parked"] += 1
            _park_mention(
                int(mention["context_id"]),
                mention_text,
                None,
                0.0,
                "mention_too_short",
            )
            stats["processed"] += 1
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
            if lazy.status == "provisional" and lazy.ftm_id:
                ftm_id = lazy.ftm_id
                score = lazy.score
                status = "provisional"
                stats["provisional"] += 1

        # Downgrade auto_linked when bridge QA would reject the FtM pairing
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

        _insert_resolution(
            context_id=int(mention["context_id"]),
            mention_text=mention_text,
            entity_profile_id=mention.get("entity_profile_id"),
            ftm_id=ftm_id,
            score=score,
            tier=tier,
            status=status,
        )

        if status == "auto_linked":
            stats["auto_linked"] += 1
            if mention.get("entity_profile_id") and ftm_id:
                from nri_core.evidence.entity_bridge import bridge_auto_link

                bridge_auto_link(
                    entity_profile_id=int(mention["entity_profile_id"]),
                    ftm_id=ftm_id,
                    bridge_score=score,
                    mention_text=mention_text,
                    ni_canonical_name=mention.get("canonical_name"),
                    ni_entity_type=mention.get("entity_type"),
                    match_tier=tier,
                )
        elif status == "provisional":
            pass  # provisional mints require human review — no entity_bridge
        else:
            stats["parked"] += 1
            candidate = result.candidates[0]["id"] if result.candidates else None
            _park_mention(
                int(mention["context_id"]),
                mention_text,
                candidate,
                result.score,
                park_reason,
            )
        stats["processed"] += 1

    if max_id > watermark:
        ni_reader.set_watermark("mention_resolver", max_id)
    stats["last_id"] = max_id
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
    budget = float(budget_seconds) if budget_seconds is not None else _resolve_drain_budget_seconds()
    t0 = time.monotonic()
    totals: dict[str, Any] = {
        "batches": 0,
        "processed": 0,
        "auto_linked": 0,
        "parked": 0,
        "provisional": 0,
        "non_entity_topic": 0,
        "last_id": ni_reader.get_watermark("mention_resolver"),
        "budget_seconds": budget,
        "batch_limit": batch_limit,
    }

    while True:
        if max_batches > 0 and totals["batches"] >= max_batches:
            break
        if budget > 0 and (time.monotonic() - t0) >= budget:
            break

        stats = resolve_batch(limit=batch_limit)
        if stats.get("skipped"):
            totals["skipped"] = True
            totals["skip_reason"] = stats.get("reason")
            break

        processed = int(stats.get("processed") or 0)
        totals["batches"] += 1
        for key in ("processed", "auto_linked", "parked", "provisional", "non_entity_topic"):
            totals[key] = int(totals.get(key, 0) or 0) + int(stats.get(key) or 0)
        totals["last_id"] = stats.get("last_id", totals["last_id"])

        if processed == 0:
            break

    totals["elapsed_seconds"] = round(time.monotonic() - t0, 2)
    return totals
