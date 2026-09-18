"""
Hygiene for intelligence.event_chronicles across all tracked events.

Root-cause cleanup for chronicle pollution:
- same-day duplicate rows
- off-topic developments attached via loose keyword OR matching
- bloated domain_keys unioned from those junk contexts
- stale event_chronicle_contexts junction rows
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_DOMAIN_HINTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "artificial-intelligence",
        (
            "language model",
            "large language",
            " llm",
            "llm ",
            "neural",
            "machine learning",
            "openai",
            "deep learning",
            "generative ai",
        ),
    ),
    (
        "medicine",
        ("cancer", "clinical", "patient", "fda", "pharma", "vaccine", "hospital", "disease"),
    ),
    (
        "finance",
        ("market", "stock", "treasury", "federal reserve", "bond", "bank ", "earnings", "inflation"),
    ),
    (
        "legal",
        ("court", "lawsuit", "litigation", "statute", "supreme court", "attorney", "indictment"),
    ),
    (
        "politics",
        ("election", "congress", "senate", "parliament", "minister", "president", "campaign"),
    ),
]


def infer_domain_from_event_name(event_name: str) -> str | None:
    low = f" {(event_name or '').lower()} "
    for domain_key, hints in _DOMAIN_HINTS:
        if any(h in low for h in hints):
            return domain_key
    return None


def _infer_domain_from_event_name(event_name: str) -> str | None:
    """Backward-compatible alias."""
    return infer_domain_from_event_name(event_name)


def _parse_developments(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [d for d in raw if isinstance(d, dict)]
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    return []


def _filter_developments(event_name: str, developments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from services.event_tracking_service import development_title_matches_event

    out: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    seen_ids: set[int] = set()
    for d in developments:
        title = d.get("title")
        if not development_title_matches_event(event_name, title):
            continue
        cid = d.get("context_id")
        if cid is not None:
            try:
                cid_i = int(cid)
            except (TypeError, ValueError):
                cid_i = None
            if cid_i is not None:
                if cid_i in seen_ids:
                    continue
                seen_ids.add(cid_i)
        title_key = re.sub(r"\s+", " ", (title or "").strip().lower())[:120]
        if title_key and title_key in seen_titles:
            continue
        if title_key:
            seen_titles.add(title_key)
        out.append(d)
    return out


def _scrub_analysis(analysis: Any, filtered_n: int) -> dict[str, Any]:
    base = analysis if isinstance(analysis, dict) else {}
    out = dict(base)
    out["context_count"] = filtered_n
    if filtered_n <= 0:
        out["latest_developments"] = None
    return out


def hygiene_tracked_event_chronicles(
    conn,
    event_id: int,
    event_name: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Clean one event's chronicles in-place.

    Returns counts: kept_days, deleted_dupes, deleted_empty, filtered_out_devs, domain_keys.
    """
    stats = {
        "event_id": event_id,
        "kept_days": 0,
        "deleted_dupes": 0,
        "deleted_empty": 0,
        "filtered_out_devs": 0,
        "kept_devs": 0,
        "domain_keys": [],
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, update_date, developments, analysis
            FROM intelligence.event_chronicles
            WHERE event_id = %s
            ORDER BY update_date DESC, id DESC
            """,
            (event_id,),
        )
        rows = cur.fetchall()
        if not rows:
            return stats

        keep_day_ids: list[int] = []
        seen_days: set[str] = set()
        day_keep_meta: list[tuple[int, list[dict[str, Any]], dict[str, Any]]] = []

        for cid, udate, devs, analysis in rows:
            day = str(udate) if udate is not None else f"id-{cid}"
            if day in seen_days:
                continue
            seen_days.add(day)
            keep_day_ids.append(cid)
            raw = _parse_developments(devs)
            filtered = _filter_developments(event_name, raw)
            stats["filtered_out_devs"] += max(0, len(raw) - len(filtered))
            stats["kept_devs"] += len(filtered)
            day_keep_meta.append((cid, filtered, _scrub_analysis(analysis, len(filtered))))

        stats["kept_days"] = len(keep_day_ids)
        stats["deleted_dupes"] = len(rows) - len(keep_day_ids)

        # Drop developments whose context_id no longer exists (stale JSON).
        candidate_ids: list[int] = []
        for _, filtered, _ in day_keep_meta:
            for d in filtered:
                raw_id = d.get("context_id")
                if raw_id is None:
                    continue
                try:
                    candidate_ids.append(int(raw_id))
                except (TypeError, ValueError):
                    pass
        existing_ids: set[int] = set()
        if candidate_ids:
            cur.execute(
                "SELECT id FROM intelligence.contexts WHERE id = ANY(%s)",
                (sorted(set(candidate_ids)),),
            )
            existing_ids = {int(r[0]) for r in cur.fetchall()}
        cleaned_meta: list[tuple[int, list[dict[str, Any]], dict[str, Any]]] = []
        kept_devs = 0
        for cid, filtered, analysis in day_keep_meta:
            live = []
            for d in filtered:
                raw_id = d.get("context_id")
                if raw_id is None:
                    live.append(d)
                    continue
                try:
                    cid_i = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if cid_i in existing_ids:
                    live.append(d)
            kept_devs += len(live)
            cleaned_meta.append((cid, live, _scrub_analysis(analysis, len(live))))
        day_keep_meta = cleaned_meta
        stats["kept_devs"] = kept_devs

        # Drop empty day shells except the newest chronicle (preserve latest summary).
        newest_id = keep_day_ids[0] if keep_day_ids else None
        retain_ids = {
            cid
            for cid, filtered, _ in day_keep_meta
            if filtered or cid == newest_id
        }
        empty_drop = [cid for cid in keep_day_ids if cid not in retain_ids]
        stats["deleted_empty"] = len(empty_drop)

        if dry_run:
            return stats

        for cid, filtered, analysis in day_keep_meta:
            if cid not in retain_ids:
                continue
            momentum = round(min(1.0, len(filtered) * 0.1), 2) if filtered else None
            cur.execute(
                """
                UPDATE intelligence.event_chronicles
                SET developments = %s::jsonb,
                    analysis = %s::jsonb,
                    momentum_score = %s
                WHERE id = %s
                """,
                (json.dumps(filtered), json.dumps(analysis), momentum, cid),
            )

        delete_ids = [r[0] for r in rows if r[0] not in retain_ids]
        if delete_ids:
            cur.execute(
                "DELETE FROM intelligence.event_chronicles WHERE id = ANY(%s)",
                (delete_ids,),
            )

        # Rebuild junction from remaining on-topic context ids for this event.
        remaining_context_ids: list[int] = []
        for cid, filtered, _ in day_keep_meta:
            if cid not in retain_ids:
                continue
            for d in filtered:
                raw_id = d.get("context_id")
                if raw_id is None:
                    continue
                try:
                    remaining_context_ids.append(int(raw_id))
                except (TypeError, ValueError):
                    pass
        remaining_context_ids = sorted(set(remaining_context_ids))
        if remaining_context_ids:
            cur.execute(
                "SELECT id FROM intelligence.contexts WHERE id = ANY(%s)",
                (remaining_context_ids,),
            )
            remaining_context_ids = sorted(int(r[0]) for r in cur.fetchall())

        cur.execute(
            "DELETE FROM intelligence.event_chronicle_contexts WHERE event_id = %s",
            (event_id,),
        )
        if remaining_context_ids:
            try:
                from shared.event_chronicle_contexts import upsert_chronicle_context_links

                upsert_chronicle_context_links(cur, event_id, remaining_context_ids)
            except Exception as e:
                logger.debug("hygiene junction upsert event %s: %s", event_id, e)
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT hygiene_event")
                    cur.execute("SAVEPOINT hygiene_event")
                except Exception:
                    pass
                # Retry after filtering — already filtered; skip junction on failure.
                logger.warning(
                    "hygiene: skipped junction rebuild for event %s (%s)", event_id, e
                )

        from services.tracked_event_narrative_service import (
            refresh_domain_keys_for_tracked_event,
        )

        stats["domain_keys"] = refresh_domain_keys_for_tracked_event(
            conn,
            event_id,
            replace=True,
            event_name=event_name,
        )
    return stats


def hygiene_all_tracked_event_chronicles(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    event_id: int | None = None,
    progress_every: int = 100,
) -> dict[str, Any]:
    """Run hygiene across tracked events. Uses a direct DB connection (caller env)."""
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db_connection"}

    summary = {
        "success": True,
        "dry_run": dry_run,
        "events": 0,
        "deleted_dupes": 0,
        "deleted_empty": 0,
        "filtered_out_devs": 0,
        "kept_devs": 0,
    }
    try:
        with conn.cursor() as cur:
            if event_id is not None:
                cur.execute(
                    "SELECT id, event_name FROM intelligence.tracked_events WHERE id = %s",
                    (event_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, event_name
                    FROM intelligence.tracked_events
                    ORDER BY id
                    """
                    + (" LIMIT %s" if limit is not None else ""),
                    (limit,) if limit is not None else None,
                )
            events = cur.fetchall()

        for i, (eid, ename) in enumerate(events, start=1):
            try:
                with conn.cursor() as cur:
                    cur.execute("SAVEPOINT hygiene_event")
                stats = hygiene_tracked_event_chronicles(
                    conn, int(eid), ename or "", dry_run=dry_run
                )
                with conn.cursor() as cur:
                    cur.execute("RELEASE SAVEPOINT hygiene_event")
            except Exception as e:
                logger.warning("hygiene event %s failed: %s", eid, e)
                try:
                    with conn.cursor() as cur:
                        cur.execute("ROLLBACK TO SAVEPOINT hygiene_event")
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                continue
            summary["events"] += 1
            summary["deleted_dupes"] += stats["deleted_dupes"]
            summary["deleted_empty"] += stats["deleted_empty"]
            summary["filtered_out_devs"] += stats["filtered_out_devs"]
            summary["kept_devs"] += stats["kept_devs"]
            if not dry_run and i % 25 == 0:
                conn.commit()
            if progress_every and i % progress_every == 0:
                logger.info(
                    "hygiene_event_chronicles: %s/%s events (dupes=%s empty=%s filtered_devs=%s)",
                    i,
                    len(events),
                    summary["deleted_dupes"],
                    summary["deleted_empty"],
                    summary["filtered_out_devs"],
                )

        if not dry_run:
            conn.commit()
        return summary
    except Exception as e:
        logger.exception("hygiene_all_tracked_event_chronicles failed")
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e), **summary}
    finally:
        try:
            conn.close()
        except Exception:
            pass
