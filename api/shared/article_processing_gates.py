"""
Shared selection rules for pipeline phases (ML, quality scoring, intelligence.contexts).

Aligns automation_manager queries, backlog_metrics, and context_processor_service so
backlog counts match what each phase actually processes.

**Fulltext-first preprocess:** ``enriched`` and UIE/entity mapping require a real
article body (≥ ``FULLTEXT_MIN_CHARS``, default 900, or ``RSS_FULLTEXT_FETCH_THRESHOLD_CHARS``).
Short RSS teasers stay ``pending`` until ``content_enrichment`` fetches the page;
a fetch that cannot produce that body is ``failed`` (not deleted on first miss).
Failed / inaccessible / headline-only rows never enter unified intake extraction.

**Strict enrichment (optional legacy):** set env ``STRICT_ARTICLE_ENRICHMENT_GATES_SINCE``
to an ISO-8601 UTC instant. Prefer fulltext helpers below for new call sites.

See docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md (section **Quality-first phase contracts** for success, skip, and handoff semantics).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

# Match RSS inline rule: substantial body without a separate fetch (legacy path)
SUBSTANTIAL_CONTENT_LENGTH = 500
MIN_CONTENT_LENGTH_ML = 100
MIN_CONTENT_LENGTH_CONTEXT = 100
DEFAULT_FULLTEXT_MIN_CHARS = 900


def fulltext_min_chars() -> int:
    """Minimum plaintext length to count as a full article (enriched + entity mapping)."""
    raw = env_str("FULLTEXT_MIN_CHARS", "").strip() or env_str(
        "RSS_FULLTEXT_FETCH_THRESHOLD_CHARS", str(DEFAULT_FULLTEXT_MIN_CHARS)
    )
    try:
        return max(200, int(raw))
    except ValueError:
        return DEFAULT_FULLTEXT_MIN_CHARS


def body_is_fulltext(text: str | None) -> bool:
    """True when stored/fetched plaintext is a real article, not a headline/teaser."""
    return len((text or "").strip()) >= fulltext_min_chars()


def strict_enrichment_cutoff_utc() -> datetime | None:
    """
    If ``STRICT_ARTICLE_ENRICHMENT_GATES_SINCE`` is set to a valid ISO-8601 datetime,
    articles at or after this instant use stricter enrichment gates. Unset = legacy only.
    """
    raw = env_str("STRICT_ARTICLE_ENRICHMENT_GATES_SINCE", "").strip()
    if not raw:
        return None
    s = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        logger.warning(
            "STRICT_ARTICLE_ENRICHMENT_GATES_SINCE invalid (%r); strict gates disabled",
            raw,
        )
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def strict_enrichment_applies(created_at: datetime | None) -> bool:
    """True when ``created_at`` is on or after the strict cutoff (and cutoff is configured)."""
    cutoff = strict_enrichment_cutoff_utc()
    if cutoff is None or created_at is None:
        return False
    ca = created_at
    if ca.tzinfo is None:
        ca = ca.replace(tzinfo=timezone.utc)
    else:
        ca = ca.astimezone(timezone.utc)
    return ca >= cutoff


def _legacy_ml_inner(table_alias: str) -> str:
    a = f"{table_alias}." if table_alias else ""
    return f"""{a}content IS NOT NULL
      AND LENGTH({a}content) > {MIN_CONTENT_LENGTH_ML}
      AND (
        {a}enrichment_status = 'enriched'
        OR ({a}enrichment_status IS NULL AND LENGTH({a}content) >= {SUBSTANTIAL_CONTENT_LENGTH})
      )"""


def _strict_ml_inner(table_alias: str) -> str:
    a = f"{table_alias}." if table_alias else ""
    return f"""{a}content IS NOT NULL
      AND LENGTH({a}content) > {MIN_CONTENT_LENGTH_ML}
      AND {a}enrichment_status = 'enriched'"""


def _legacy_context_inner(alias: str) -> str:
    return f"""LENGTH(COALESCE({alias}.content, '')) > {MIN_CONTENT_LENGTH_CONTEXT}
      AND (
        LENGTH(COALESCE({alias}.content, '')) >= {SUBSTANTIAL_CONTENT_LENGTH}
        OR COALESCE({alias}.enrichment_status, '') IN ('enriched', 'failed', 'inaccessible')
      )"""


def _strict_context_inner(alias: str) -> str:
    return f"""LENGTH(COALESCE({alias}.content, '')) > {MIN_CONTENT_LENGTH_CONTEXT}
      AND COALESCE({alias}.enrichment_status, '') IN ('enriched', 'failed', 'inaccessible')"""


def sql_ml_ready_and_content_bounds(table_alias: str = "") -> str:
    """SQL fragment: enrichment gate + LENGTH(content) > MIN (for WHERE on articles)."""
    cutoff = strict_enrichment_cutoff_utc()
    if cutoff is None:
        return _legacy_ml_inner(table_alias)
    lit = cutoff.isoformat().replace("'", "''")
    ts = f"{table_alias}.created_at" if table_alias else "created_at"
    return f"""(
  (COALESCE({ts}, '-infinity'::timestamptz) < '{lit}'::timestamptz AND ({_legacy_ml_inner(table_alias)}))
  OR (COALESCE({ts}, '-infinity'::timestamptz) >= '{lit}'::timestamptz AND ({_strict_ml_inner(table_alias)}))
)"""


def sql_context_sync_article_ready(alias: str = "a") -> str:
    """SQL fragment for articles eligible for first-time context backfill."""
    cutoff = strict_enrichment_cutoff_utc()
    if cutoff is None:
        return _legacy_context_inner(alias)
    lit = cutoff.isoformat().replace("'", "''")
    ts = f"{alias}.created_at"
    return f"""(
  (COALESCE({ts}, '-infinity'::timestamptz) < '{lit}'::timestamptz AND ({_legacy_context_inner(alias)}))
  OR (COALESCE({ts}, '-infinity'::timestamptz) >= '{lit}'::timestamptz AND ({_strict_context_inner(alias)}))
)"""


def article_eligible_for_ml(
    content: str | None,
    enrichment_status: str | None,
    created_at: datetime | None = None,
) -> bool:
    """
    ML / heavy analysis: legacy allows ``NULL`` enrichment + long body; strict cutoff requires
    ``enriched``. If ``created_at`` is omitted, legacy rules apply (callers with a row should pass it).
    """
    c = (content or "").strip()
    if len(c) <= MIN_CONTENT_LENGTH_ML:
        return False
    es = (enrichment_status or "").strip()
    if strict_enrichment_applies(created_at):
        return es == "enriched"
    if es == "enriched":
        return True
    if es == "" and len(c) >= SUBSTANTIAL_CONTENT_LENGTH:
        return True
    return False


def article_eligible_for_context(
    content: str | None,
    enrichment_status: str | None,
    created_at: datetime | None = None,
) -> bool:
    """
    Create or expose intelligence.contexts only when we have usable text and (legacy) either
    substantial body or terminal enrichment; strict cutoff requires terminal enrichment status
    (or enriched) — not ``NULL`` + 500 chars alone.
    """
    c = (content or "").strip()
    if len(c) <= MIN_CONTENT_LENGTH_CONTEXT:
        return False
    es = (enrichment_status or "").strip()
    if strict_enrichment_applies(created_at):
        return es in ("enriched", "failed", "inaccessible")
    if len(c) >= SUBSTANTIAL_CONTENT_LENGTH:
        return True
    if es in ("enriched", "failed", "inaccessible"):
        return True
    return False


def finalize_rss_enrichment_after_inline(
    body: str,
    *,
    created_at: datetime,
    url: str | None,
    trafilatura_attempted: bool,
    trafilatura_ok: bool,
) -> tuple[str, int]:
    """
    After RSS inline enrichment attempt: (enrichment_status, enrichment_attempts).

    When strict gates apply and the feed already provided a long body without a fetch,
    status is ``pending`` so ``content_enrichment`` can fast-path to ``enriched`` without
    re-fetching. Short bodies without a successful fetch remain ``failed`` when a fetch
    was attempted, else legacy ``enriched`` for edge cases (no URL).
    """
    b = (body or "").strip()
    if trafilatura_attempted:
        if trafilatura_ok:
            return "enriched", 0
        return "failed", 1
    if len(b) >= SUBSTANTIAL_CONTENT_LENGTH:
        if strict_enrichment_applies(created_at):
            return "pending", 0
        return "enriched", 0
    # Short body and no trafilatura attempt (e.g. missing URL) — match historical default
    return "enriched", 0


def rss_item_passes_ingest_gates(
    title: str | None, content: str | None, url: str | None
) -> tuple[bool, str | None]:
    """
    Minimal ingest validation before insert. Returns (ok, reason_code).
    Quality/impact filters in the collector still apply first.
    """
    t = (title or "").strip()
    if not t:
        return False, "empty_title"
    c = (content or "").strip()
    u = (url or "").strip()
    if not u:
        return False, "missing_url"
    if len(c) < 20 and len(t) < 10:
        return False, "thin_item"
    return True, None
