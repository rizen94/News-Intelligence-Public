"""
Shared selection rules for pipeline phases (ML, quality scoring, intelligence.contexts).

Aligns automation_manager queries, backlog_metrics, and context_processor_service so
backlog counts match what each phase actually processes.

See docs/PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md.
"""

from __future__ import annotations

# Match RSS inline rule: substantial body without a separate fetch
SUBSTANTIAL_CONTENT_LENGTH = 500
MIN_CONTENT_LENGTH_ML = 100
MIN_CONTENT_LENGTH_CONTEXT = 100


def article_eligible_for_ml(content: str | None, enrichment_status: str | None) -> bool:
    """
    ML / heavy analysis: require real body text and an explicit enrichment success,
    or legacy rows that already have a long body (pre-enrichment-tracking).
    """
    c = (content or "").strip()
    if len(c) <= MIN_CONTENT_LENGTH_ML:
        return False
    es = (enrichment_status or "").strip()
    if es == "enriched":
        return True
    if es == "" and len(c) >= SUBSTANTIAL_CONTENT_LENGTH:
        return True
    return False


def article_eligible_for_context(content: str | None, enrichment_status: str | None) -> bool:
    """
    Create or expose intelligence.contexts only when we have usable text or a terminal
    enrichment outcome (avoids empty contexts while fetch is still pending).
    """
    c = (content or "").strip()
    if len(c) <= MIN_CONTENT_LENGTH_CONTEXT:
        return False
    es = (enrichment_status or "").strip()
    if len(c) >= SUBSTANTIAL_CONTENT_LENGTH:
        return True
    if es in ("enriched", "failed", "inaccessible"):
        return True
    return False


def sql_ml_ready_and_content_bounds(table_alias: str = "") -> str:
    """SQL fragment: enrichment gate + LENGTH(content) > MIN (for WHERE on articles)."""
    a = f"{table_alias}." if table_alias else ""
    return f"""{a}content IS NOT NULL
      AND LENGTH({a}content) > {MIN_CONTENT_LENGTH_ML}
      AND (
        {a}enrichment_status = 'enriched'
        OR ({a}enrichment_status IS NULL AND LENGTH({a}content) >= {SUBSTANTIAL_CONTENT_LENGTH})
      )"""


def sql_context_sync_article_ready(alias: str = "a") -> str:
    """SQL fragment for articles eligible for first-time context backfill."""
    return f"""LENGTH(COALESCE({alias}.content, '')) > {MIN_CONTENT_LENGTH_CONTEXT}
      AND (
        LENGTH(COALESCE({alias}.content, '')) >= {SUBSTANTIAL_CONTENT_LENGTH}
        OR COALESCE({alias}.enrichment_status, '') IN ('enriched', 'failed', 'inaccessible')
      )"""


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
