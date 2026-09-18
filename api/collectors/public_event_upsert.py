"""
Shared helpers for public-data collectors upserting into chronological_events.

External feeds lack article rows; we use a sentinel source_article_id (no FK on
chronological_events.source_article_id) and storyline_id ``public_data:{domain}``.
Idempotency is via UNIQUE(event_id).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any

from config.feature_registry import is_feature_enabled
from config.runtime import env_float, env_int, env_str
from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

PUBLIC_STORYLINE_PREFIX = "public_data:"
DEFAULT_SENTINEL_ARTICLE_ID = 0

_last_http_ts = 0.0


def public_storyline_id(domain_key: str) -> str:
    dk = (domain_key or "politics").strip().lower().replace("_", "-")
    return f"{PUBLIC_STORYLINE_PREFIX}{dk}"


def sentinel_article_id() -> int:
    return env_int("PUBLIC_DATA_SENTINEL_ARTICLE_ID", DEFAULT_SENTINEL_ARTICLE_ID)


def collector_enabled(feature_key: str, *, env_flag: str | None = None) -> bool:
    """Feature registry gate (default false) plus optional env override ON."""
    if env_flag:
        raw = (env_str(env_flag, "") or "").strip().lower()
        if raw in ("1", "true", "yes", "on"):
            return True
        if raw in ("0", "false", "no", "off"):
            return False
    return bool(is_feature_enabled(feature_key, default=False))


def rate_limit_sleep(min_interval_seconds: float | None = None) -> None:
    """Simple process-wide throttle between outbound HTTP calls."""
    global _last_http_ts
    interval = (
        min_interval_seconds
        if min_interval_seconds is not None
        else env_float("PUBLIC_DATA_HTTP_MIN_INTERVAL_SECONDS", 0.35)
    )
    interval = max(0.0, float(interval))
    if interval <= 0:
        return
    elapsed = time.monotonic() - _last_http_ts
    if elapsed < interval:
        time.sleep(interval - elapsed)
    _last_http_ts = time.monotonic()


def stable_event_id(prefix: str, external_id: str) -> str:
    """Deterministic event_id; keeps human-readable prefix when short enough."""
    ext = (external_id or "").strip()
    raw = f"{prefix}:{ext}"
    if len(raw) <= 200 and ext:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    return f"{prefix}:{digest}"


def fingerprint_for_external(
    *,
    extraction_method: str,
    external_id: str,
    event_date: str | None = None,
) -> str:
    parts = [
        (extraction_method or "").strip().lower(),
        (external_id or "").strip().lower(),
        (event_date or "unknown").strip(),
    ]
    return hashlib.sha256("::".join(parts).encode("utf-8")).hexdigest()[:64]


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if len(s) >= 10:
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def upsert_chronological_event(
    *,
    event_id: str,
    title: str,
    domain_key: str,
    extraction_method: str,
    event_type: str = "other",
    description: str | None = None,
    actual_event_date: date | datetime | str | None = None,
    importance_score: float = 0.5,
    extraction_confidence: float = 0.7,
    location: str | None = None,
    entities: list[Any] | None = None,
    key_actors: list[Any] | None = None,
    tags: list[str] | None = None,
    verification_source: str | None = None,
    source_text: str | None = None,
    temporal_status: str = "occurred",
    date_precision: str = "exact",
    metadata_extra: dict[str, Any] | None = None,
) -> bool:
    """
    Insert or update one public chronological event.
    Returns True when a row was inserted (xmax=0), False on update/no-op/error.
    """
    title_clean = (title or "").strip()[:500]
    if not title_clean or not event_id:
        return False

    evt_date = _as_date(actual_event_date)
    storyline = public_storyline_id(domain_key)
    article_id = sentinel_article_id()
    fp = fingerprint_for_external(
        extraction_method=extraction_method,
        external_id=event_id,
        event_date=evt_date.isoformat() if evt_date else None,
    )
    entities_json = json.dumps(entities or [])
    actors_json = json.dumps(key_actors or [])
    tags_list = list(tags or [])
    if metadata_extra:
        # Fold light provenance into tags / description rather than schema change.
        for k, v in list(metadata_extra.items())[:5]:
            tag = f"{k}:{v}"[:80]
            if tag not in tags_list:
                tags_list.append(tag)

    temporal = temporal_status if temporal_status in ("unknown", "occurred", "scheduled") else "unknown"
    precision = (
        date_precision
        if date_precision in ("exact", "week", "month", "quarter", "year", "unknown")
        else "unknown"
    )
    now = datetime.now(timezone.utc)

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.chronological_events (
                        event_id, storyline_id, title, description, event_type,
                        actual_event_date, temporal_confidence, source_article_id,
                        extraction_method, extraction_confidence, importance_score,
                        location, entities, event_fingerprint, source_count,
                        key_actors, tags, verification_source, source_text,
                        temporal_status, date_precision, verified,
                        event_date, ingestion_date, vintage_date,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s::jsonb, %s, 1,
                        %s::jsonb, %s, %s, %s,
                        %s, %s, true,
                        %s, %s, %s,
                        NOW(), NOW()
                    )
                    ON CONFLICT (event_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = COALESCE(EXCLUDED.description, public.chronological_events.description),
                        event_type = EXCLUDED.event_type,
                        actual_event_date = COALESCE(EXCLUDED.actual_event_date, public.chronological_events.actual_event_date),
                        extraction_method = EXCLUDED.extraction_method,
                        extraction_confidence = EXCLUDED.extraction_confidence,
                        importance_score = EXCLUDED.importance_score,
                        location = COALESCE(EXCLUDED.location, public.chronological_events.location),
                        entities = EXCLUDED.entities,
                        key_actors = EXCLUDED.key_actors,
                        tags = EXCLUDED.tags,
                        verification_source = COALESCE(EXCLUDED.verification_source, public.chronological_events.verification_source),
                        source_text = COALESCE(EXCLUDED.source_text, public.chronological_events.source_text),
                        vintage_date = EXCLUDED.vintage_date,
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS inserted
                    """,
                    (
                        event_id[:255],
                        storyline[:255],
                        title_clean,
                        (description or "")[:8000] or None,
                        (event_type or "other")[:100],
                        evt_date,
                        0.85,
                        article_id,
                        (extraction_method or "public_data")[:100],
                        max(0.0, min(1.0, float(extraction_confidence))),
                        max(0.0, min(1.0, float(importance_score))),
                        (location or None),
                        entities_json,
                        fp,
                        actors_json,
                        tags_list[:40] if tags_list else None,
                        (verification_source or extraction_method)[:255] if verification_source or extraction_method else None,
                        (source_text or None),
                        temporal,
                        precision,
                        datetime.combine(evt_date, datetime.min.time()).replace(tzinfo=timezone.utc)
                        if evt_date
                        else now,
                        now,
                        now,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return bool(row and row[0])
    except Exception as e:
        logger.warning("chronological_events upsert failed event_id=%s: %s", event_id, e)
        return False


def upsert_many(events: list[dict[str, Any]]) -> dict[str, int]:
    """Batch wrapper; each item is kwargs for upsert_chronological_event."""
    inserted = 0
    updated_or_skipped = 0
    errors = 0
    for ev in events:
        try:
            if upsert_chronological_event(**ev):
                inserted += 1
            else:
                updated_or_skipped += 1
        except Exception:
            errors += 1
    return {
        "inserted": inserted,
        "updated_or_skipped": updated_or_skipped,
        "errors": errors,
        "total": len(events),
    }
