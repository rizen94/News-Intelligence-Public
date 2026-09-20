"""Act-verb chronological_events top-K → package seed (v12 THIN kernel)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config.runtime import env_int
from shared.act_verb_lexicon import count_act_verbs, text_has_act_verb
from shared.database.connection import get_ui_db_connection_context
from shared.hub_denylist import is_blocked_hub_name

logger = logging.getLogger(__name__)


def kernel_top_k(*, default: int = 25) -> int:
    return max(1, min(100, env_int("KERNEL_ACT_VERB_TOP_K", default)))


def score_event_row(title: str | None, description: str | None, event_type: str | None) -> int:
    blob = " ".join(x for x in (title, description, event_type) if x)
    if is_blocked_hub_name(title):
        return 0
    if not text_has_act_verb(blob):
        return 0
    return count_act_verbs(blob)


def list_act_verb_events_for_day(
    *,
    day: date | None = None,
    domain_key: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Rank public.chronological_events for a calendar day by act-verb density.

    Returns [{id, title, event_type, source_article_id, score, event_date}, ...]
    """
    k = limit if limit is not None else kernel_top_k()
    target = day or datetime.now(timezone.utc).date()
    start = datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    sql = """
        SELECT id, title, description, event_type, source_article_id,
               COALESCE(event_date, extraction_timestamp::date) AS ed
        FROM public.chronological_events
        WHERE COALESCE(event_date, extraction_timestamp::date) >= %s::date
          AND COALESCE(event_date, extraction_timestamp::date) < %s::date
        ORDER BY id DESC
        LIMIT %s
    """
    # Prefetch a wider pool then rank in Python (act lexicon is Python-side).
    pool = max(k * 20, 200)
    rows: list[tuple] = []
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (target.isoformat(), (target + timedelta(days=1)).isoformat(), pool))
            rows = list(cur.fetchall() or [])

    scored: list[dict[str, Any]] = []
    for row in rows:
        eid, title, desc, etype, aid, ed = row
        sc = score_event_row(title, desc, etype)
        if sc <= 0:
            continue
        scored.append(
            {
                "id": int(eid),
                "title": title,
                "event_type": etype,
                "source_article_id": int(aid) if aid is not None else None,
                "score": sc,
                "event_date": ed.isoformat() if hasattr(ed, "isoformat") else str(ed),
                "domain_key": domain_key,
            }
        )
    scored.sort(key=lambda r: (-int(r["score"]), -int(r["id"])))
    return scored[:k]
