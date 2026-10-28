"""
RSS feed health: weekly quality cull (primary) or warn-then-auto silence (legacy).

Automation runs ``run_feed_health_cycle`` via ``rss_feed_health`` phase.
Operators can dry-run via ``rss_feed_health.dry_run`` / ``RSS_FEED_SILENCE_DRY_RUN``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool, env_float, env_int, env_str

logger = logging.getLogger(__name__)


@dataclass
class FeedHealthVerdict:
    domain_key: str
    schema: str
    feed_id: int
    feed_name: str
    reason: str  # fetch_failure | zero_yield | low_signal_yield | recovered | weekly_cull
    action: str  # warn | silence | clear_warning
    review_count: int = 0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedQualityScore:
    """Scored feed row for weekly cull selection (pure / testable)."""

    domain_key: str
    schema: str
    feed_id: int
    feed_name: str
    article_count: int
    avg_quality: float


def _cfg() -> dict[str, Any]:
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = get_orchestrator_governance_config().get("rss_feed_health") or {}
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def rss_feed_silence_enabled() -> bool:
    c = _cfg()
    if "enabled" in c:
        return bool(c.get("enabled"))
    return env_bool("RSS_FEED_SILENCE_ENABLED", False)


def rss_feed_silence_dry_run() -> bool:
    c = _cfg()
    if "dry_run" in c:
        return bool(c.get("dry_run"))
    return env_bool("RSS_FEED_SILENCE_DRY_RUN", True)


def rss_feed_health_policy() -> str:
    """``weekly_cull`` (default) or legacy ``warn_silence``."""
    c = _cfg()
    raw = str(c.get("policy") or env_str("RSS_FEED_HEALTH_POLICY", "weekly_cull")).strip().lower()
    if raw in ("warn_silence", "warn-silence"):
        return "warn_silence"
    return "weekly_cull"


def _min_quality() -> float:
    c = _cfg()
    if c.get("min_quality") is not None:
        return float(c["min_quality"])
    return env_float("RSS_FEED_SILENCE_MIN_QUALITY", env_float("ARTICLE_SIGNAL_FULL_MIN_QUALITY", 0.45))


def _zero_yield_days() -> int:
    c = _cfg()
    return int(c.get("zero_yield_days") or env_int("RSS_FEED_SILENCE_ZERO_YIELD_DAYS", 14))


def _low_signal_days() -> int:
    c = _cfg()
    return int(c.get("low_signal_days") or env_int("RSS_FEED_SILENCE_LOW_SIGNAL_DAYS", 30))


def _review_cycles() -> int:
    c = _cfg()
    return max(1, int(c.get("review_cycles") or env_int("RSS_FEED_SILENCE_REVIEW_CYCLES", 3)))


def _grace_days() -> int:
    c = _cfg()
    return int(c.get("grace_days") or env_int("RSS_FEED_SILENCE_GRACE_DAYS", 21))


def _low_signal_min_articles() -> int:
    c = _cfg()
    return int(c.get("low_signal_min_articles") or env_int("RSS_FEED_SILENCE_LOW_SIGNAL_MIN_ARTICLES", 10))


def _fetch_failure_consecutive() -> int:
    c = _cfg()
    return int(c.get("fetch_failure_consecutive") or env_int("RSS_FEED_SILENCE_FETCH_FAIL_CONSECUTIVE", 5))


def _target_avg_quality() -> float:
    c = _cfg()
    if c.get("target_avg_quality") is not None:
        return max(0.0, min(1.0, float(c["target_avg_quality"])))
    return max(0.0, min(1.0, env_float("RSS_FEED_TARGET_AVG_QUALITY", 0.65)))


def _drops_per_review() -> int:
    c = _cfg()
    if c.get("drops_per_review") is not None:
        return max(0, min(50, int(c["drops_per_review"])))
    return max(0, min(50, env_int("RSS_FEED_DROPS_PER_REVIEW", 2)))


def _review_window_days() -> int:
    c = _cfg()
    if c.get("review_window_days") is not None:
        return max(1, min(90, int(c["review_window_days"])))
    return max(1, min(90, env_int("RSS_FEED_REVIEW_WINDOW_DAYS", 7)))


def _min_articles_for_score() -> int:
    c = _cfg()
    if c.get("min_articles_for_score") is not None:
        return max(1, min(500, int(c["min_articles_for_score"])))
    return max(1, min(500, env_int("RSS_FEED_MIN_ARTICLES_FOR_SCORE", 5)))


def _health_json(filters: dict | None) -> dict:
    fh = (filters or {}).get("feed_health") if isinstance(filters, dict) else None
    return dict(fh) if isinstance(fh, dict) else {}


def select_weekly_cull_drops(
    scores: list[FeedQualityScore],
    *,
    target_avg_quality: float,
    drops_per_review: int,
    min_articles_for_score: int,
) -> list[FeedQualityScore]:
    """
    Pure selection: if any scored feed is below the quality bar, return up to
    ``drops_per_review`` lowest-avg feeds that are below the bar.
    """
    if drops_per_review <= 0:
        return []
    scored = [s for s in scores if s.article_count >= min_articles_for_score]
    if not scored:
        return []
    if all(s.avg_quality >= target_avg_quality for s in scored):
        return []
    below = [s for s in scored if s.avg_quality < target_avg_quality]
    below.sort(key=lambda s: (s.avg_quality, s.feed_id))
    return below[:drops_per_review]


def evaluate_weekly_cull(domain_key: str | None = None) -> list[FeedHealthVerdict]:
    """Score active feeds and return silence verdicts for weekly quality cull."""
    if not rss_feed_silence_enabled():
        return []

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs

    pairs = pipeline_url_schema_pairs()
    if domain_key:
        pairs = [(dk, sch) for dk, sch in pairs if dk == domain_key]

    window = _review_window_days()
    min_n = _min_articles_for_score()
    target = _target_avg_quality()
    drops = _drops_per_review()
    all_scores: list[FeedQualityScore] = []

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk, schema in pairs:
                try:
                    cur.execute(
                        f"""
                        SELECT
                            rf.id,
                            rf.feed_name,
                            COUNT(a.id)::bigint,
                            COALESCE(AVG(a.quality_score), 0)::float
                        FROM {schema}.rss_feeds rf
                        LEFT JOIN {schema}.articles a ON (
                            a.rss_feed_id = rf.id
                            OR (a.rss_feed_id IS NULL AND a.source_domain = rf.feed_name)
                        )
                          AND a.created_at >= NOW() - (%s || ' days')::interval
                        WHERE rf.is_active = true
                        GROUP BY rf.id, rf.feed_name
                        """,
                        (window,),
                    )
                    for row in cur.fetchall():
                        all_scores.append(
                            FeedQualityScore(
                                domain_key=dk,
                                schema=schema,
                                feed_id=int(row[0]),
                                feed_name=str(row[1] or ""),
                                article_count=int(row[2] or 0),
                                avg_quality=float(row[3] or 0.0),
                            )
                        )
                except Exception as exc:
                    logger.warning("evaluate_weekly_cull query %s: %s", schema, exc)
                    continue

    # Cull independently per schema so one domain's sludge does not steal the drop budget.
    by_schema: dict[str, list[FeedQualityScore]] = {}
    for s in all_scores:
        by_schema.setdefault(s.schema, []).append(s)

    verdicts: list[FeedHealthVerdict] = []
    for schema, scores in by_schema.items():
        for drop in select_weekly_cull_drops(
            scores,
            target_avg_quality=target,
            drops_per_review=drops,
            min_articles_for_score=min_n,
        ):
            verdicts.append(
                FeedHealthVerdict(
                    domain_key=drop.domain_key,
                    schema=drop.schema,
                    feed_id=drop.feed_id,
                    feed_name=drop.feed_name,
                    reason="weekly_cull",
                    action="silence",
                    review_count=0,
                    details={
                        "avg_quality": round(drop.avg_quality, 4),
                        "article_count": drop.article_count,
                        "target_avg_quality": target,
                        "review_window_days": window,
                    },
                )
            )
    return verdicts


def evaluate_feeds(domain_key: str | None = None) -> list[FeedHealthVerdict]:
    """Evaluate active feeds; returns warn/silence/clear verdicts (not yet applied)."""
    if not rss_feed_silence_enabled():
        return []

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import pipeline_url_schema_pairs

    pairs = pipeline_url_schema_pairs()
    if domain_key:
        pairs = [(dk, sch) for dk, sch in pairs if dk == domain_key]

    min_q = _min_quality()
    zero_days = _zero_yield_days()
    low_days = _low_signal_days()
    grace = _grace_days()
    low_min = _low_signal_min_articles()
    fail_consec = _fetch_failure_consecutive()
    verdicts: list[FeedHealthVerdict] = []

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk, schema in pairs:
                try:
                    cur.execute(
                        f"""
                        SELECT
                            rf.id, rf.feed_name, rf.is_active, rf.status, rf.warning_message,
                            rf.last_error_message, rf.created_at, rf.filters,
                            COALESCE((rf.filters->>'consecutive_empty_fetches')::int, 0),
                            COUNT(a.id) FILTER (
                                WHERE a.created_at >= NOW() - (%s || ' days')::interval
                            )::bigint,
                            COUNT(a.id) FILTER (
                                WHERE a.created_at >= NOW() - (%s || ' days')::interval
                                  AND COALESCE(a.quality_score, 0) >= %s
                            )::bigint,
                            MAX(a.created_at)
                        FROM {schema}.rss_feeds rf
                        LEFT JOIN {schema}.articles a ON (
                            a.rss_feed_id = rf.id
                            OR (a.rss_feed_id IS NULL AND a.source_domain = rf.feed_name)
                        )
                        WHERE rf.is_active = true
                        GROUP BY rf.id
                        """,
                        (zero_days, low_days, min_q),
                    )
                    rows = cur.fetchall()
                except Exception as exc:
                    logger.warning("evaluate_feeds query %s: %s", schema, exc)
                    continue

                for row in rows:
                    feed_id = int(row[0])
                    feed_name = row[1]
                    last_err = (row[5] or "").strip()
                    created_at = row[6]
                    filters = row[7] if isinstance(row[7], dict) else {}
                    health = _health_json(filters)
                    review_count = int(health.get("silence_review_count") or 0)
                    consec_empty = int(row[8] or 0)
                    articles_zero_window = int(row[9] or 0)
                    above_threshold = int(row[10] or 0)
                    last_insert = row[11]

                    in_grace = False
                    if created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                        in_grace = age_days < grace

                    reason = ""
                    if last_err or consec_empty >= fail_consec:
                        reason = "fetch_failure"
                    elif articles_zero_window == 0 and created_at:
                        age_days = (datetime.now(timezone.utc) - created_at).days
                        if age_days >= zero_days:
                            reason = "zero_yield"
                    elif articles_zero_window >= low_min and above_threshold == 0:
                        reason = "low_signal_yield"

                    if not reason:
                        if row[4] or (row[3] or "") == "warning":
                            verdicts.append(
                                FeedHealthVerdict(
                                    domain_key=dk,
                                    schema=schema,
                                    feed_id=feed_id,
                                    feed_name=feed_name,
                                    reason="recovered",
                                    action="clear_warning",
                                    review_count=0,
                                    details={"last_insert": str(last_insert) if last_insert else None},
                                )
                            )
                        continue

                    if in_grace:
                        verdicts.append(
                            FeedHealthVerdict(
                                domain_key=dk,
                                schema=schema,
                                feed_id=feed_id,
                                feed_name=feed_name,
                                reason=reason,
                                action="warn",
                                review_count=review_count,
                                details={"grace": True, "in_grace_days": grace},
                            )
                        )
                        continue

                    next_review = review_count + 1
                    cycles_needed = _review_cycles()
                    if reason == "zero_yield":
                        cycles_needed = max(1, cycles_needed - 1)

                    action = "silence" if next_review >= cycles_needed else "warn"
                    verdicts.append(
                        FeedHealthVerdict(
                            domain_key=dk,
                            schema=schema,
                            feed_id=feed_id,
                            feed_name=feed_name,
                            reason=reason,
                            action=action,
                            review_count=next_review,
                            details={
                                "articles_zero_window": articles_zero_window,
                                "above_threshold": above_threshold,
                                "consecutive_empty": consec_empty,
                            },
                        )
                    )

    return verdicts


def apply_verdicts(
    verdicts: list[FeedHealthVerdict],
    *,
    dry_run: bool | None = None,
) -> dict[str, int]:
    """Apply warn/silence/clear to rss_feeds. Returns action counts."""
    if dry_run is None:
        dry_run = rss_feed_silence_dry_run()

    counts = {"warn": 0, "silence": 0, "clear_warning": 0, "skipped": 0}
    if not verdicts:
        return counts

    from shared.database.connection import get_db_connection_context

    now_iso = datetime.now(timezone.utc).isoformat()

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for v in verdicts:
                if dry_run:
                    counts["skipped"] += 1
                    logger.info(
                        "DRY RUN feed health %s/%s id=%s action=%s reason=%s details=%s",
                        v.schema,
                        v.feed_name,
                        v.feed_id,
                        v.action,
                        v.reason,
                        v.details,
                    )
                    continue

                if v.action == "clear_warning":
                    cur.execute(
                        f"""
                        UPDATE {v.schema}.rss_feeds
                        SET status = 'active',
                            warning_message = NULL,
                            filters = COALESCE(filters, '{{}}'::jsonb)
                                || jsonb_build_object(
                                    'feed_health', COALESCE(filters->'feed_health', '{{}}'::jsonb)
                                        || jsonb_build_object('silence_review_count', 0, 'recovered_at', %s)
                                ),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (now_iso, v.feed_id),
                    )
                    counts["clear_warning"] += 1
                elif v.action == "warn":
                    cur.execute(
                        f"""
                        UPDATE {v.schema}.rss_feeds
                        SET status = 'warning',
                            warning_message = %s,
                            filters = COALESCE(filters, '{{}}'::jsonb)
                                || jsonb_build_object(
                                    'feed_health', COALESCE(filters->'feed_health', '{{}}'::jsonb)
                                        || jsonb_build_object(
                                            'silence_review_count', %s,
                                            'last_warn_at', %s,
                                            'last_warn_reason', %s
                                        )
                                ),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (v.reason, v.review_count, now_iso, v.reason, v.feed_id),
                    )
                    counts["warn"] += 1
                elif v.action == "silence":
                    cur.execute(
                        f"""
                        UPDATE {v.schema}.rss_feeds
                        SET is_active = false,
                            status = 'inactive',
                            warning_message = %s,
                            filters = COALESCE(filters, '{{}}'::jsonb)
                                || jsonb_build_object(
                                    'feed_health', COALESCE(filters->'feed_health', '{{}}'::jsonb)
                                        || jsonb_build_object(
                                            'silence_review_count', %s,
                                            'silenced_at', %s,
                                            'silence_reason', %s
                                        )
                                ),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (v.reason, v.review_count, now_iso, v.reason, v.feed_id),
                    )
                    counts["silence"] += 1

            if not dry_run:
                conn.commit()

    return counts


def run_feed_health_cycle(*, dry_run: bool | None = None) -> dict[str, Any]:
    policy = rss_feed_health_policy()
    if policy == "weekly_cull":
        verdicts = evaluate_weekly_cull()
    else:
        verdicts = evaluate_feeds()
    applied = apply_verdicts(verdicts, dry_run=dry_run)
    return {
        "policy": policy,
        "evaluated": len(verdicts),
        "verdicts_by_action": applied,
        "dry_run": dry_run if dry_run is not None else rss_feed_silence_dry_run(),
        "target_avg_quality": _target_avg_quality() if policy == "weekly_cull" else None,
        "drops_per_review": _drops_per_review() if policy == "weekly_cull" else None,
    }


def get_feed_health_monitor_counts() -> dict[str, int]:
    """Active warning feeds and feeds silenced in last 7 days."""
    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_schema_names_active

    warning = 0
    silenced_7d = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for schema in get_pipeline_schema_names_active():
                try:
                    cur.execute(
                        f"""
                        SELECT
                            COUNT(*) FILTER (WHERE is_active AND status = 'warning')::bigint,
                            COUNT(*) FILTER (
                                WHERE NOT is_active
                                  AND filters->'feed_health'->>'silenced_at' IS NOT NULL
                                  AND updated_at >= NOW() - INTERVAL '7 days'
                            )::bigint
                        FROM {schema}.rss_feeds
                        """
                    )
                    r = cur.fetchone()
                    if r:
                        warning += int(r[0] or 0)
                        silenced_7d += int(r[1] or 0)
                except Exception:
                    continue
    return {"feeds_warning_count": warning, "feeds_silenced_7d": silenced_7d}
