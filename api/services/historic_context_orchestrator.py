"""
Historic context orchestrator — multi-source parallel fetch, relevance filter, agreement scoring,
and iterative expansion when a prior significant event is discovered.
"""

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("historic_context")
except Exception:
    logger = logging.getLogger(__name__)

from services.historic_context_sources import (
    fetch_all_sources_parallel,
    Finding,
    SOURCE_ADAPTERS,
)

# Relevance: minimum term-match score (query + topic words in title/snippet) to keep a finding
RELEVANCE_MIN_TERMS = 1
# Agreement: minimum sources mentioning same event to consider it "agreed"
AGREEMENT_MIN_SOURCES = 2
# Expansion: if an event's date is before request start_date and agreement_count >= 2, expand search
EXPANSION_PRIOR_DAYS = 365  # expand back 1 year for prior significant event


def _terms_from_query_and_topic(query: str | None, topic: str | None) -> set[str]:
    """Build set of lowercase terms for relevance scoring."""
    terms = set()
    if topic:
        terms.add((topic or "").lower())
    if query:
        for word in re.findall(r"[a-z0-9]+", (query or "").lower()):
            if len(word) >= 2:
                terms.add(word)
    return terms


def _relevance_score(finding: Finding, terms: set[str]) -> float:
    """Score 0.0–1.0 from term matches in title and snippet."""
    if not terms:
        return 1.0
    text = f"{finding.get('title') or ''} {finding.get('snippet') or ''}".lower()
    if not text:
        return 0.0
    hits = sum(1 for t in terms if t in text)
    return min(1.0, hits / max(1, len(terms) * 0.5))


def _filter_relevant(findings: list[Finding], query: str | None, topic: str | None) -> list[Finding]:
    """Keep findings that meet minimum relevance; add relevance_score to each."""
    terms = _terms_from_query_and_topic(query, topic)
    out = []
    for f in findings:
        score = _relevance_score(f, terms)
        if score > 0 or not terms:
            f = dict(f)
            f["relevance_score"] = round(score, 2)
            out.append(f)
    return out


def _date_from_finding(f: Finding) -> str | None:
    """Return YYYY-MM-DD string for finding's source_date or None."""
    d = f.get("source_date")
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, str) and len(d) >= 10:
        return d[:10]
    return None


def _event_key(date_str: str | None, snippet: str, source_id: str) -> str:
    """Simple key for grouping: date + first 3 significant words of snippet."""
    words = re.findall(r"[a-z0-9]{3,}", (snippet or "").lower())[:5]
    return f"{date_str or 'nodate'}|{source_id}|{' '.join(words[:3])}"


def _cluster_findings_by_agreement(findings_by_source: dict[str, list[Finding]]) -> list[dict[str, Any]]:
    """
    Group findings that refer to the same event (same date) across sources.
    One event per date bucket; agreement_count = number of distinct sources that had a finding on that date.
    Returns list of { event_summary, date_approx, source_ids, agreement_count, finding_ids }.
    """
    all_f: list[tuple[str, Finding, int]] = []
    fid = 0
    for source_id, flist in findings_by_source.items():
        for f in flist:
            fid += 1
            all_f.append((source_id, f, fid))
    by_date: dict[str, list[tuple[str, Finding, int]]] = defaultdict(list)
    for source_id, f, fid in all_f:
        date_str = _date_from_finding(f)
        by_date[date_str or "nodate"].append((source_id, f, fid))
    events: list[dict[str, Any]] = []
    for date_str, group in by_date.items():
        source_ids_in = list(set(g[0] for g in group))
        snippets = [g[1].get("snippet") or g[1].get("title") or "" for g in group]
        event_summary = snippets[0][:400] if snippets else ""
        if len(snippets) > 1:
            event_summary = " | ".join(s[:200] for s in snippets[:3])
        date_approx = None
        if date_str and date_str != "nodate":
            try:
                date_approx = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass
        events.append({
            "event_summary": event_summary[:1000],
            "date_approx": date_approx,
            "source_ids": source_ids_in,
            "agreement_count": len(source_ids_in),
            "finding_ids": [g[2] for g in group],
        })
    return events


def _detect_prior_significant_event(
    events: list[dict[str, Any]],
    request_start_date: str,
) -> dict[str, Any] | None:
    """
    If any event has date before request_start_date and agreement_count >= 2,
    return that event so caller can expand search (e.g. 2021 event when query was 2022-2024).
    """
    try:
        start_d = datetime.strptime(request_start_date, "%Y-%m-%d").date()
    except ValueError:
        return None
    for e in events:
        d = e.get("date_approx")
        if not d:
            continue
        if d < start_d and (e.get("agreement_count") or 0) >= AGREEMENT_MIN_SOURCES:
            return e
    return None


def _build_search_query(query: str | None, topic: str | None, start_date: str, end_date: str) -> str:
    """Build a short search-friendly query for external APIs (News API, Wikipedia) to improve relevance."""
    parts = []
    if topic and topic not in ("all", ""):
        parts.append(topic)
    # Add salient terms from user query (skip long question words)
    if query:
        stop = {"what", "why", "how", "when", "where", "which", "the", "that", "this", "cause", "caused", "causes", "drop", "rise", "change", "trend", "analysis", "explain"}
        words = re.findall(r"[a-z0-9]+", query.lower())
        for w in words:
            if len(w) >= 2 and w not in stop and w not in parts:
                parts.append(w)
                if len(parts) >= 4:
                    break
    # Add year from date range so news/Wikipedia search is date-relevant
    try:
        if start_date and len(start_date) >= 4:
            parts.append(start_date[:4])
        elif end_date and len(end_date) >= 4:
            parts.append(end_date[:4])
    except Exception:
        pass
    return " ".join(parts[:5]) if parts else (query or topic or "finance")


def _get_db():
    try:
        from shared.database.connection import get_db_connection
        return get_db_connection()
    except Exception as e:
        logger.warning("DB not available for historic context: %s", e)
        return None


def _create_request(query: str, topic: str | None, start_date: str, end_date: str, trigger_type: str, trigger_id: str | None) -> int | None:
    conn = _get_db()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO intelligence.historic_context_requests
                   (query, topic, start_date, end_date, trigger_type, trigger_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, 'running')
                   RETURNING id""",
                (query, topic or "", start_date, end_date, trigger_type or "analysis", trigger_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row[0] if row else None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Create historic context request failed: %s", e)
        return None


def _update_request_status(request_id: int, status: str, summary: str | None = None) -> None:
    conn = _get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE intelligence.historic_context_requests
                   SET status = %s, summary = %s, updated_at = NOW(),
                   completed_at = CASE WHEN %s IN ('completed', 'failed', 'partial') THEN NOW() ELSE completed_at END
                   WHERE id = %s""",
                (status, summary, status, request_id),
            )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Update historic context request failed: %s", e)


def _store_findings(request_id: int, findings_by_source: dict[str, list[Finding]]) -> dict[int, int]:
    """Insert findings; return mapping placeholder_id -> real finding id for event linking."""
    conn = _get_db()
    if not conn:
        return {}
    placeholder_to_real: dict[int, int] = {}
    try:
        with conn.cursor() as cur:
            fid = 0
            for source_id, flist in findings_by_source.items():
                for f in flist:
                    fid += 1
                    cur.execute(
                        """INSERT INTO intelligence.historic_context_findings
                           (request_id, source_id, title, snippet, url, source_date, relevance_score, raw_response)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           RETURNING id""",
                        (
                            request_id,
                            source_id,
                            (f.get("title") or "")[:1000],
                            (f.get("snippet") or "")[:5000],
                            (f.get("url") or "")[:2000],
                            f.get("source_date"),
                            f.get("relevance_score"),
                            json.dumps(f.get("raw") or {}),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        placeholder_to_real[fid] = row[0]
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Store historic context findings failed: %s", e)
    return placeholder_to_real


def _store_events(request_id: int, events: list[dict[str, Any]]) -> None:
    conn = _get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            for e in events:
                finding_ids = list(e.get("finding_ids") or [])
                cur.execute(
                    """INSERT INTO intelligence.historic_context_events
                       (request_id, event_summary, date_approx, source_ids, agreement_count, significance_score, finding_ids)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (
                        request_id,
                        e.get("event_summary", "")[:5000],
                        e.get("date_approx"),
                        e.get("source_ids") or [],
                        e.get("agreement_count", 1),
                        min(1.0, (e.get("agreement_count") or 1) / max(1, len(SOURCE_ADAPTERS))),
                        finding_ids,
                    ),
                )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Store historic context events failed: %s", e)


def _store_expansion(parent_request_id: int, child_request_id: int, trigger_reason: str, trigger_event_id: int | None) -> None:
    conn = _get_db()
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO intelligence.historic_context_expansions
                   (parent_request_id, child_request_id, trigger_reason, trigger_event_id)
                   VALUES (%s, %s, %s, %s)""",
                (parent_request_id, child_request_id, trigger_reason, trigger_event_id),
            )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Store historic context expansion failed: %s", e)


def run_historic_context(
    query: str,
    start_date: str,
    end_date: str,
    topic: str | None = None,
    trigger_type: str = "analysis",
    trigger_id: str | None = None,
    source_ids: list[str] | None = None,
    max_expansions: int = 1,
) -> dict[str, Any]:
    """
    Main entry: fetch all sources in parallel, relevance filter, build events and summary.
    If DB is available (migration 149), also persist requests/findings/events. If not, still
    return summary and events so the analysis prompt gets historic context.
    """
    request_id = _create_request(query, topic, start_date, end_date, trigger_type, trigger_id)
    if not request_id:
        logger.warning("Historic context: DB request create failed (migration 149 may not be applied); running fetches in-memory only")

    try:
        # Build a search-friendly query for News API / Wikipedia (topic + key terms + year)
        search_query = _build_search_query(query, topic, start_date, end_date)
        logger.info("Historic context search query: %r", search_query)

        # Parallel fetch from all sources (no DB required)
        raw_by_source = fetch_all_sources_parallel(
            search_query, start_date, end_date,
            source_ids=source_ids,
            limit_per_source=20,
        )
        counts = {sid: len(flist) for sid, flist in raw_by_source.items()}
        logger.info("Historic context raw fetch: %s", counts)

        # Relevance filter per source
        findings_by_source: dict[str, list[Finding]] = {}
        for sid, flist in raw_by_source.items():
            filtered = _filter_relevant(flist, query, topic)
            findings_by_source[sid] = filtered
        filtered_counts = {sid: len(flist) for sid, flist in findings_by_source.items()}
        logger.info("Historic context after relevance filter: %s", filtered_counts)

        # Persist findings only if we have a request_id
        placeholder_to_real: dict[int, int] = {}
        if request_id:
            placeholder_to_real = _store_findings(request_id, findings_by_source)

        # Cluster into events (agreement by date)
        events = _cluster_findings_by_agreement(findings_by_source)
        if request_id:
            for e in events:
                pids = e.get("finding_ids") or []
                e["finding_ids"] = [placeholder_to_real.get(p) for p in pids if placeholder_to_real.get(p)]
            _store_events(request_id, events)

        # Summary: concatenate top events by agreement
        top_events = sorted(events, key=lambda x: (x.get("agreement_count") or 0, len(x.get("source_ids") or [])), reverse=True)[:10]
        summary_parts = [e.get("event_summary", "") for e in top_events]
        summary = "\n".join(summary_parts) if summary_parts else "No historic events found for the given range and query."

        # Expansion: prior significant event? (only when DB available)
        prior = _detect_prior_significant_event(events, start_date)
        if request_id and prior and max_expansions > 0:
            exp_start = (prior["date_approx"] - timedelta(days=EXPANSION_PRIOR_DAYS)).strftime("%Y-%m-%d")
            exp_end = (prior["date_approx"] + timedelta(days=90)).strftime("%Y-%m-%d")
            child_id = _create_request(query, topic, exp_start, exp_end, trigger_type, trigger_id)
            if child_id:
                _store_expansion(request_id, child_id, "significant_prior_event", None)
                run_historic_context(
                    query, exp_start, exp_end,
                    topic=topic, trigger_type=trigger_type, trigger_id=trigger_id,
                    source_ids=source_ids, max_expansions=0,
                )

        if request_id:
            _update_request_status(request_id, "completed", summary)

        return {
            "success": True,
            "request_id": request_id,
            "summary": summary,
            "events": [{"event_summary": e.get("event_summary"), "date_approx": str(e.get("date_approx")) if e.get("date_approx") else None, "agreement_count": e.get("agreement_count"), "source_ids": e.get("source_ids")} for e in top_events],
        }
    except Exception as e:
        logger.exception("Historic context run failed")
        if request_id:
            _update_request_status(request_id, "failed", None)
        return {"success": False, "error": str(e), "request_id": request_id, "summary": "", "events": []}


def get_historic_context_for_analysis(query: str, topic: str | None, start_date: str, end_date: str) -> str:
    """
    Convenience: run orchestrator and return only the summary string for inclusion in analysis prompt.
    """
    result = run_historic_context(
        query, start_date, end_date,
        topic=topic, trigger_type="analysis", trigger_id=None,
        max_expansions=1,
    )
    return result.get("summary") or ""
