"""
Finance Domain Routes
Handles finance-specific endpoints: market trends, patterns, corporate announcements,
and infrastructure data (FRED series, market data store).

Domain validation rule:
- _check_domain(): Use for routes that ONLY touch finance-silo infrastructure
  (SQLite, FRED API, ChromaDB, local files). These work without main PostgreSQL.
- validate_domain(): Use for routes that read/write the main PostgreSQL database.
  Do NOT migrate those to _check_domain — it would hide legitimate DB dependency failures.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection
from shared.domain_registry import ACTIVE_DOMAIN_KEYS_SET, DOMAIN_PATH_PATTERN
from shared.services.domain_aware_service import validate_domain

from domains.finance.orchestrator_types import TaskPriority, TaskType

logger = logging.getLogger(__name__)


def _validate_commodity(commodity: str) -> None:
    """Raise HTTP 400 if commodity is not in the registry."""
    try:
        from domains.finance.commodity_registry import get_commodity_ids

        ids = get_commodity_ids()
        if (commodity or "").lower() not in [x.lower() for x in ids]:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown commodity: {commodity}. Valid: {', '.join(ids)}",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Commodity registry check failed: %s", e)
        raise HTTPException(status_code=500, detail="Commodity registry unavailable")


# Timeframe to timedelta for market endpoints
_TIMEFRAME_MAP = {"1d": 1, "7d": 7, "30d": 30, "90d": 90, "1y": 365}


def _parse_timeframe(timeframe: str) -> timedelta:
    """Return timedelta(days=N) for timeframe string."""
    days = _TIMEFRAME_MAP.get((timeframe or "7d").lower(), 7)
    return timedelta(days=days)


def _get_recent_finance_articles(days: int, limit: int = 200) -> list[dict[str, Any]]:
    """Fetch recent finance-domain articles. Returns list of dicts with id, title, summary, url, published_at, category."""
    try:
        from domains.news_aggregation.services.article_service import ArticleService

        svc = ArticleService(domain="finance")
        published_after = datetime.now(timezone.utc) - timedelta(days=days)
        res = svc.get_articles(
            limit=limit,
            offset=0,
            include_content=False,
            filters={"published_after": published_after},
        )
        data = res.get("data") or {}
        articles = data.get("articles") or []
        return [dict(a) for a in articles]
    except Exception as e:
        logger.warning("_get_recent_finance_articles failed: %s", e)
        return []


router = APIRouter(prefix="/api", tags=["Finance"], responses={404: {"description": "Not found"}})


def _check_domain(domain: str) -> None:
    """Validate domain; finance infrastructure endpoints work without main DB."""
    if domain not in ACTIVE_DOMAIN_KEYS_SET:
        raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")


# ---------------------------------------------------------------------------
# Infrastructure data (FRED, market store, cache)
# ---------------------------------------------------------------------------


@router.get("/{domain}/finance/tasks")  # List tasks with filters
async def list_finance_tasks(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    status: str | None = Query(
        None,
        description="Filter by status: queued, planning, executing, evaluating, revising, complete, failed",
    ),
    task_type: str | None = Query(
        None, description="Filter by type: refresh, ingest, analysis, report, scheduled_refresh"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List orchestrator tasks with optional filters. Paginated."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    data = orch.list_tasks(status=status, task_type=task_type, limit=limit, offset=offset)
    return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}


@router.get("/{domain}/finance/tasks/{task_id}")  # Task status and result (polling)
async def get_finance_task(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    task_id: str = Path(..., description="Orchestrator task ID (e.g. fin-abc123)"),
):
    """Poll task status. Returns result if complete."""
    logger.debug("Finance task poll: domain=%s task_id=%s", domain, task_id)
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        logger.warning(
            "Finance task poll rejected: orchestrator not available (domain=%s task_id=%s)",
            domain,
            task_id,
        )
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    status = orch.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    result = orch.get_task_result(task_id)
    out = {"status": status}
    if result:
        out["result"] = {
            "output": result.output,
            "confidence": result.confidence,
            "iterations_used": result.iterations_used,
            "duration_ms": result.duration_ms,
            "sources_consulted": result.sources_consulted,
            "sources_succeeded": result.sources_succeeded,
            "sources_failed": result.sources_failed,
        }
        if result.verification_summary:
            vr = result.verification_summary
            out["result"]["verification"] = {
                "verified": vr.verified,
                "unsupported": vr.unsupported,
                "fabricated": vr.fabricated,
            }
            if vr.details:
                out["result"]["verification"]["claims"] = [
                    {"claim_text": c.claim_text, "ref_id": c.ref_id, "verdict": c.verdict.value}
                    for c in vr.details
                ]
        if result.provenance:
            out["result"]["provenance"] = [
                {
                    "ref_id": e.ref_id,
                    "source": e.source,
                    "identifier": e.identifier,
                    "date": str(e.date),
                    "value": e.value,
                    "unit": e.unit,
                }
                for e in result.provenance[:100]
            ]
    return {"success": True, "data": out, "timestamp": datetime.now().isoformat()}


@router.get(
    "/{domain}/finance/evidence/preview"
)  # On-demand evidence bundle (RSS + optional API summary + RAG)
async def finance_evidence_preview(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    query: str | None = Query(None, description="Optional query for RAG"),
    topic: str = Query("gold", description="Topic (e.g. gold) for API summary"),
    hours: int = Query(168, ge=1, le=720, description="RSS lookback hours"),
    max_rss: int = Query(15, ge=1, le=50),
    include_rss: bool = Query(True),
    include_api_summary: bool = Query(False),
    include_rag: bool = Query(False),
):
    """Preview evidence bundle from evidence collector (RSS, optional API summary, optional RAG)."""
    validate_domain(domain)
    try:
        from domains.finance.evidence_collector import collect as evidence_collect

        bundle = evidence_collect(
            query=query,
            topic=topic,
            hours=hours,
            max_rss=max_rss,
            include_rss=include_rss,
            include_api_summary=include_api_summary,
            include_rag=include_rag,
        )
        return {"success": True, "data": bundle, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.warning("Evidence preview failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{domain}/finance/evidence"
)  # Paginated evidence index (provenance from completed tasks)
async def list_finance_evidence(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    source: str | None = Query(None, description="Filter by source: gold, fred, edgar_10k"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List evidence index entries (provenance) from completed tasks."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    data = orch.list_evidence_index(source=source, limit=limit, offset=offset)
    return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}


@router.get("/{domain}/finance/verification")  # Paginated verification history
async def list_finance_verification(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List verification results from completed analysis tasks."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    data = orch.list_verifications(limit=limit, offset=offset)
    return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}


@router.get(
    "/{domain}/finance/trace/{task_id}"
)  # Task execution trace (spans, decisions, LLM calls)
async def get_finance_trace(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    task_id: str = Path(..., description="Orchestrator task ID"),
):
    """Reconstruct task trace: spans, orchestrator decisions, LLM interactions."""
    _check_domain(domain)
    try:
        from shared.logging.trace_logger import get_traces_for_task

        spans = get_traces_for_task(task_id)
        decisions = []
        llm_calls = []
        try:
            import json
            from pathlib import Path

            from config.paths import LOG_DIR

            log_dir = Path(LOG_DIR)
            for fname in ("orchestrator_decisions.jsonl", "orchestrator_decisions_outcomes.jsonl"):
                p = log_dir / fname
                if p.exists():
                    with open(p) as f:
                        for line in f:
                            if task_id in line:
                                try:
                                    decisions.append(json.loads(line.strip()))
                                except json.JSONDecodeError:
                                    pass
            p = log_dir / "llm_interactions.jsonl"
            if p.exists():
                with open(p) as f:
                    for line in f:
                        if task_id in line:
                            try:
                                llm_calls.append(json.loads(line.strip()))
                            except json.JSONDecodeError:
                                pass
        except Exception:
            pass
        return {
            "success": True,
            "task_id": task_id,
            "spans": spans,
            "decisions": decisions,
            "llm_interactions": llm_calls,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.warning("Trace fetch failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{domain}/finance/tasks/{task_id}/ledger"
)  # Ledger entries for this task (activity log)
async def get_finance_task_ledger(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    task_id: str = Path(..., description="Orchestrator task ID"),
):
    """Get evidence ledger entries for a task. Used for live activity log during processing."""
    _check_domain(domain)
    try:
        from domains.finance.data.evidence_ledger import get_by_report

        report_id = f"orchestrator_{task_id}"
        entries = get_by_report(report_id)
        return {
            "success": True,
            "data": {"entries": entries},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.warning("Task ledger fetch failed: %s", e)
        return {"success": True, "data": {"entries": []}, "timestamp": datetime.now().isoformat()}


@router.get("/{domain}/finance/tasks/{task_id}/status")  # Status only (for polling)
async def get_finance_task_status(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    task_id: str = Path(..., description="Orchestrator task ID"),
):
    """Get task status only. Use GET /tasks/{id} for status + result when complete."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    status = orch.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"success": True, "data": status, "timestamp": datetime.now().isoformat()}


@router.get("/{domain}/finance/schedule")  # Schedule status
async def get_finance_schedule(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Get scheduled task status: next run times, last run results."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    try:
        status = orch.get_schedule_status()
        return {"success": True, "data": status, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error("Error fetching schedule: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/sources/status")  # Source health with last success/failure
async def get_finance_source_status(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Get source health status: last success, last failure, next scheduled refresh."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    try:
        from domains.finance.data.evidence_ledger import get_recent_by_source

        schedule = orch.get_schedule_status()
        recent = get_recent_by_source(limit_per_source=10)

        # Map schedule task names to source IDs
        name_to_source = {"gold_refresh": "gold", "edgar_ingest": "edgar"}

        sources: list[dict] = []
        seen = set()

        for item in schedule.get("tasks", []):
            name = item.get("name", "")
            src_id = name_to_source.get(name, name.replace("_", ""))
            if src_id not in seen:
                seen.add(src_id)
            recents = recent.get(src_id, [])
            last_success = None
            last_failure = None
            last_error = None
            for r in recents:
                st = r.get("status")
                if st == "success" and not last_success:
                    last_success = r.get("created_at")
                elif st == "error" and not last_failure:
                    last_failure = r.get("created_at")
                    last_error = r.get("error")

            if not last_success and item.get("last_run"):
                last_success = item["last_run"]

            status = "healthy" if last_success else ("degraded" if last_failure else "unknown")
            if last_failure and not last_success:
                status = "down"

            sources.append(
                {
                    "source_id": src_id,
                    "name": name.replace("_", " ").title(),
                    "status": status,
                    "last_success": last_success,
                    "last_failure": last_failure,
                    "last_error": last_error,
                    "data_freshness": last_success or "never",
                    "next_scheduled_refresh": item.get("next_run"),
                }
            )

        # Add fred if in ledger but not in schedule
        if "fred" not in seen and "fred" in recent:
            recents = recent["fred"]
            last_success = next(
                (r["created_at"] for r in recents if r.get("status") == "success"), None
            )
            last_failure = next(
                (r["created_at"] for r in recents if r.get("status") == "error"), None
            )
            last_error = next((r.get("error") for r in recents if r.get("status") == "error"), None)
            status = "healthy" if last_success else ("degraded" if last_failure else "unknown")
            sources.append(
                {
                    "source_id": "fred",
                    "name": "FRED",
                    "status": status,
                    "last_success": last_success,
                    "last_failure": last_failure,
                    "last_error": last_error,
                    "data_freshness": last_success or "never",
                    "next_scheduled_refresh": None,
                }
            )

        return {
            "success": True,
            "data": {"sources": sources},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error fetching source status: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/data-sources")  # Infrastructure: YAML only
async def get_finance_data_sources(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """List available data sources and their configured symbols (from sources.yaml)."""
    _check_domain(domain)
    try:
        import yaml
        from config.paths import SOURCES_YAML

        if not SOURCES_YAML.exists():
            return {
                "success": True,
                "data": {"sources": []},
                "timestamp": datetime.now().isoformat(),
            }
        with open(SOURCES_YAML) as f:
            cfg = yaml.safe_load(f) or {}
        sources = []
        for k, v in cfg.items():
            if isinstance(v, dict):
                datasets = v.get("datasets") or {}
                sources.append(
                    {
                        "id": k,
                        "name": v.get("name", k),
                        "type": v.get("type", "api"),
                        "symbols": list(datasets.keys()),
                        "symbol_count": len(datasets),
                    }
                )
        return {
            "success": True,
            "data": {"sources": sources},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching data sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/market-data")  # Infrastructure: SQLite market store
async def get_finance_market_data(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    source: str = Query("fred", description="Data source (fred)"),
    symbol: str | None = Query(None, description="Symbol filter"),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
):
    """Get stored market data from finance market_data store."""
    _check_domain(domain)
    try:
        from domains.finance.data.market_data_store import get_series, list_symbols

        if symbol:
            r = get_series(source, symbol, start_date, end_date)
            if not r.success:
                raise HTTPException(status_code=503, detail=f"Market data unavailable: {r.error}")
            return {
                "success": True,
                "data": {"source": source, "symbol": symbol, "observations": r.data or []},
                "timestamp": datetime.now().isoformat(),
            }
        symbols = list_symbols(source)
        return {
            "success": True,
            "data": {"source": source, "symbols": symbols},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching market data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/gold")  # Infrastructure: gold amalgam + SQLite
async def get_gold_data(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    source: str | None = Query(
        None, description="Source: freegoldapi, fred_iq12260, or omit for unified"
    ),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
    fetch: bool = Query(False, description="Fetch from sources if stored data empty"),
):
    """Get gold data from amalgamator. Unified view prefers USD/oz (freegoldapi)."""
    _check_domain(domain)
    try:
        from domains.finance.gold_amalgamator import get_stored, get_unified, list_sources

        if source:
            stored = get_stored(source_id=source, start=start_date, end=end_date)
            data = {"source": source, "observations": stored.get(source, [])}
        else:
            obs = get_unified(
                prefer_unit="USD/oz",
                start=start_date,
                end=end_date,
                fetch_if_empty=fetch,
            )
            data = {
                "unified": True,
                "prefer_unit": "USD/oz",
                "observations": obs,
                "sources": list_sources(),
            }
        return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching gold data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/finance/gold/fetch")  # Infrastructure: gold sources via orchestrator
async def trigger_gold_fetch(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
):
    """Fetch gold from all amalgamator sources via orchestrator. Submits refresh task, runs to completion."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    try:
        task_id = orch.submit_task(
            TaskType.refresh,
            {"topic": "gold", "start_date": start_date, "end_date": end_date},
            priority=TaskPriority.high,
        )
        result = await orch.run_task(task_id)
        if not result or (hasattr(result.status, "value") and result.status.value == "failed"):
            raise HTTPException(
                status_code=503,
                detail=result.warnings[0] if result and result.warnings else "Refresh failed",
            )
        data = result.output or {}
        src = data.get("sources", {})
        counts = {k: v.get("count", v.get("chunks_embedded", 0)) for k, v in src.items()}
        return {
            "success": True,
            "data": {
                "sources": counts,
                "total": data.get("total_observations", sum(counts.values())),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching gold: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/gold/history")
async def get_gold_history(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    days: int = Query(90, ge=1, le=1825, description="Number of days of history"),
    fetch_if_empty: bool = Query(True, description="Fetch from sources if stored data empty"),
):
    """Historical daily gold prices for commodity chart. Prefers metals_dev then freegoldapi then FRED."""
    _check_domain(domain)
    try:
        from domains.finance.gold_amalgamator import get_history

        obs = get_history(days=days, fetch_if_empty=fetch_if_empty)
        return {
            "success": True,
            "data": {"observations": obs, "days": days},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching gold history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/gold/spot")
async def get_gold_spot(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Current gold spot price (bid/ask/high/low/change). From metals.dev when key set, else amalgamator unified."""
    _check_domain(domain)
    try:
        from domains.finance.data_sources.metals_dev import fetch_spot

        res = fetch_spot(metal="gold", currency="USD")
        if res.success and res.data:
            return {"success": True, "data": res.data, "timestamp": datetime.now().isoformat()}
        from domains.finance.gold_amalgamator import get_unified

        obs = get_unified(prefer_unit="USD/oz", fetch_if_empty=True)
        if not obs:
            return {
                "success": True,
                "data": {"price": None, "unit": "USD/oz"},
                "timestamp": datetime.now().isoformat(),
            }
        latest = obs[-1]
        return {
            "success": True,
            "data": {
                "price": latest.get("value"),
                "unit": latest.get("unit", "USD/oz"),
                "source_id": latest.get("source_id"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching gold spot: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/gold/authority")
async def get_gold_authority(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    authorities: str | None = Query(
        "lbma,mcx,ibja", description="Comma-separated: lbma, mcx, ibja"
    ),
):
    """Regional authority gold prices (LBMA London, MCX India, IBJA India) for geographic comparison."""
    _check_domain(domain)
    try:
        from domains.finance.data_sources.metals_dev import fetch_authority

        out = {}
        for auth in (authorities or "lbma,mcx,ibja").split(","):
            auth = auth.strip().lower()
            if not auth:
                continue
            res = fetch_authority(authority=auth, currency="USD")
            if res.success and res.data:
                out[auth] = res.data
        return {"success": True, "data": out, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error fetching gold authority: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/gold/geo-events")
async def get_gold_geo_events(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=200),
):
    """Finance-domain tracked events relevant to gold (event_name/scope matched to gold topic keywords)."""
    _check_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        fetch_limit = limit * 3
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date, geographic_scope, domain_keys
                FROM intelligence.tracked_events
                WHERE %s = ANY(domain_keys)
                ORDER BY start_date DESC NULLS LAST
                LIMIT %s
                """,
                (domain, fetch_limit),
            )
            rows = cur.fetchall()
        conn.close()
        events = [
            {
                "id": r[0],
                "event_type": r[1],
                "event_name": r[2],
                "start_date": str(r[3]) if r[3] else None,
                "end_date": str(r[4]) if r[4] else None,
                "geographic_scope": r[5],
                "domain_keys": list(r[6]) if r[6] else [],
            }
            for r in rows
        ]
        from domains.finance.news_orchestrator import is_relevant_to_commodity

        combined = [
            (ev, (ev.get("event_name") or "") + " " + (ev.get("geographic_scope") or ""))
            for ev in events
        ]
        events = [ev for ev, text in combined if is_relevant_to_commodity(text, "gold")][:limit]
        by_region = {}
        for ev in events:
            scope = (ev.get("geographic_scope") or "").strip()
            if not scope:
                continue
            for part in scope.replace(",", " ").split():
                region = part.strip()
                if len(region) < 2:
                    continue
                by_region.setdefault(region, []).append(ev["id"])
        return {
            "success": True,
            "data": {"events": events, "by_region": by_region},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching gold geo-events: {e}", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/finance/gold/fetch-history")
async def trigger_gold_fetch_history(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    days: int = Query(90, ge=1, le=1825),
):
    """Trigger historical gold data fetch from metals.dev and amalgamator (admin)."""
    _check_domain(domain)
    try:
        from domains.finance.gold_amalgamator import fetch_all, get_history

        end_dt = datetime.now(timezone.utc).date()
        start_dt = end_dt - timedelta(days=days)
        fetch_all(
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            store=True,
        )
        obs = get_history(days=days, fetch_if_empty=False)
        return {
            "success": True,
            "data": {"observations_count": len(obs), "days": days},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching gold history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodities")
async def get_commodities_list(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
):
    """Return commodity list from registry for dashboard/nav (id, label)."""
    _check_domain(domain)
    try:
        from domains.finance.commodity_registry import get_commodity_list_for_api

        return {
            "success": True,
            "data": get_commodity_list_for_api(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error fetching commodities list: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/{commodity}/news")
async def get_commodity_news(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    commodity: str = Path(..., description="Commodity id (e.g. gold, silver, platinum)"),
    hours: int = Query(168, ge=24, le=720),
    max_items: int = Query(20, ge=1, le=50),
):
    """Commodity-relevant news and contexts (financial relevance filter applied)."""
    _check_domain(domain)
    _validate_commodity(commodity)
    try:
        from domains.finance.news_orchestrator import get_shortlist

        shortlist = get_shortlist(
            topic=commodity.lower(), hours=hours, max_items=max_items, include_contexts=True
        )
        return {
            "success": True,
            "data": {"items": shortlist},
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching commodity news for %s: %s", commodity, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/{commodity}/supply-chain")
async def get_commodity_supply_chain(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    commodity: str = Path(..., description="Commodity id (e.g. gold, silver, platinum)"),
    hours: int = Query(168, ge=24, le=720),
    max_items: int = Query(15, ge=1, le=50),
):
    """Commodity-relevant contexts (mining, EDGAR, supply-chain). Financial relevance filter applied."""
    _check_domain(domain)
    _validate_commodity(commodity)
    try:
        from domains.finance.news_orchestrator import get_supply_chain_items

        items = get_supply_chain_items(commodity.lower(), hours=hours, max_items=max_items)
        return {
            "success": True,
            "data": {"items": items},
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error fetching commodity supply-chain for %s: %s", commodity, e, exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/{commodity}/history")
async def get_commodity_history(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    commodity: str = Path(..., description="Commodity id (e.g. gold, silver, platinum)"),
    days: int = Query(90, ge=1, le=1825),
    fetch_if_empty: bool = Query(True),
):
    """Historical daily prices for one commodity.
    Gold: amalgamator. Others: FRED from registry first; metals (silver/platinum) fall back to manual store. Oil/gas: FRED only.
    """
    _check_domain(domain)
    _validate_commodity(commodity)
    try:
        from domains.finance.commodity_registry import get_metals_dev

        cid = commodity.lower()
        if cid == "gold":
            from domains.finance.gold_amalgamator import get_history

            obs = get_history(days=days, fetch_if_empty=fetch_if_empty)
        else:
            from domains.finance.data_sources.fred_commodity import (
                fetch_commodity_history_from_fred,
            )

            end_dt = datetime.now(timezone.utc).date()
            start_dt = end_dt - timedelta(days=max(1, days))
            start = start_dt.strftime("%Y-%m-%d")
            end = end_dt.strftime("%Y-%m-%d")
            fred_result = fetch_commodity_history_from_fred(cid, start=start, end=end, store=False)
            if fred_result.success and fred_result.data:
                obs = fred_result.data
            elif get_metals_dev(cid):
                from domains.finance.commodity_store import get_manual_history

                obs = get_manual_history(cid, days=days)
            else:
                obs = []
        return {
            "success": True,
            "data": {"observations": obs, "days": days},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error fetching %s history: %s", commodity, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/{commodity}/spot")
async def get_commodity_spot(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    commodity: str = Path(..., description="Commodity id (e.g. gold, silver, platinum, oil, gas)"),
):
    """Current spot price. FRED from registry first; metals use metals.dev; gold also amalgamator. Unit from registry."""
    _check_domain(domain)
    _validate_commodity(commodity)
    try:
        from domains.finance.commodity_registry import get_metals_dev, get_unit
        from domains.finance.data_sources.fred_commodity import fetch_commodity_spot_from_fred

        cid = commodity.lower()
        default_unit = get_unit(cid)
        fred_spot = fetch_commodity_spot_from_fred(cid)
        if fred_spot.success and fred_spot.data:
            return {
                "success": True,
                "data": {
                    "price": fred_spot.data.get("price"),
                    "unit": fred_spot.data.get("unit", default_unit),
                    "source_id": fred_spot.data.get("source_id", "fred"),
                },
                "timestamp": datetime.now().isoformat(),
            }
        if get_metals_dev(cid):
            from domains.finance.commodity_store import upsert_manual_observations
            from domains.finance.data_sources.metals_dev import fetch_spot

            res = fetch_spot(metal=cid, currency="USD")
            if res.success and res.data:
                data = res.data
                date_str = (data.get("timestamp") or datetime.now(timezone.utc).isoformat())[:10]
                obs = [
                    {
                        "date": date_str,
                        "value": data.get("price"),
                        "metadata": {
                            "unit": data.get("unit", default_unit),
                            "source_id": "metals_dev_spot",
                            "raw": data,
                        },
                    }
                ]
                try:
                    upsert_manual_observations(cid, obs)
                except Exception:
                    logger.debug("Failed to upsert %s spot into manual store", cid, exc_info=True)
                return {"success": True, "data": data, "timestamp": datetime.now().isoformat()}
            if cid == "gold":
                from domains.finance.gold_amalgamator import get_unified

                unified = get_unified(prefer_unit="USD/oz", fetch_if_empty=True)
                if unified:
                    latest = unified[-1]
                    return {
                        "success": True,
                        "data": {
                            "price": latest.get("value"),
                            "unit": latest.get("unit", default_unit),
                            "source_id": latest.get("source_id"),
                        },
                        "timestamp": datetime.now().isoformat(),
                    }
        return {
            "success": True,
            "data": {"price": None, "unit": default_unit},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error("Error fetching %s spot: %s", commodity, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/{commodity}/authority")
async def get_commodity_authority(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    commodity: str = Path(..., description="Commodity id (e.g. gold, silver, platinum)"),
    authorities: str | None = Query("lbma,mcx,ibja"),
):
    """Regional authority prices (LBMA, MCX, IBJA). Same endpoint for all metals; API may return metal-specific rates."""
    _check_domain(domain)
    _validate_commodity(commodity)
    try:
        from domains.finance.commodity_registry import get_metals_dev

        if not get_metals_dev(commodity.lower()):
            return {"success": True, "data": {}, "timestamp": datetime.now().isoformat()}
        from domains.finance.data_sources.metals_dev import fetch_authority

        out = {}
        for auth in (authorities or "lbma,mcx,ibja").split(","):
            auth = auth.strip().lower()
            if not auth:
                continue
            res = fetch_authority(authority=auth, currency="USD")
            if res.success and res.data:
                out[auth] = res.data
        return {"success": True, "data": out, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error("Error fetching %s authority: %s", commodity, e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/commodity/geo-events")
async def get_commodity_geo_events(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=200),
    commodity: str | None = Query(
        None,
        description="Filter to events relevant to this commodity (gold, silver, platinum). Omit to return all finance events.",
    ),
):
    """Finance-domain tracked events with geographic_scope for choropleth.
    When commodity is set (gold/silver/platinum), only events whose name/scope match that commodity's
    topic keywords are returned, so the timeline is specific to the metal rather than all market news.
    """
    _check_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        # Fetch more rows if we filter by commodity so we still have enough after filtering
        try:
            from domains.finance.commodity_registry import get_commodity_ids

            valid_ids = [x.lower() for x in get_commodity_ids()]
        except Exception:
            valid_ids = ["gold", "silver", "platinum"]
        fetch_limit = limit * 3 if commodity and (commodity or "").lower() in valid_ids else limit
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date, geographic_scope, domain_keys
                FROM intelligence.tracked_events
                WHERE %s = ANY(domain_keys)
                ORDER BY start_date DESC NULLS LAST
                LIMIT %s
                """,
                (domain, fetch_limit),
            )
            rows = cur.fetchall()
        conn.close()
        events = [
            {
                "id": r[0],
                "event_type": r[1],
                "event_name": r[2],
                "start_date": str(r[3]) if r[3] else None,
                "end_date": str(r[4]) if r[4] else None,
                "geographic_scope": r[5],
                "domain_keys": list(r[6]) if r[6] else [],
            }
            for r in rows
        ]
        if commodity and (commodity or "").lower() in valid_ids:
            from domains.finance.news_orchestrator import is_relevant_to_commodity

            combined = [
                (ev, (ev.get("event_name") or "") + " " + (ev.get("geographic_scope") or ""))
                for ev in events
            ]
            events = [ev for ev, text in combined if is_relevant_to_commodity(text, commodity)][
                :limit
            ]
        by_region = {}
        for ev in events:
            scope = (ev.get("geographic_scope") or "").strip()
            if not scope:
                continue
            for part in scope.replace(",", " ").split():
                region = part.strip()
                if len(region) < 2:
                    continue
                by_region.setdefault(region, []).append(ev["id"])
        return {
            "success": True,
            "data": {"events": events, "by_region": by_region},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching commodity geo-events: {e}", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


REGULATORY_EVENT_TYPES = ("regulatory", "policy", "government_bond")


@router.get("/{domain}/finance/commodity/regulatory-events")
async def get_commodity_regulatory_events(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(20, ge=1, le=100),
    commodity: str | None = Query(
        None,
        description="Filter to events relevant to this commodity (gold, silver, platinum). Omit to return all regulatory events.",
    ),
):
    """Finance-domain tracked events with event_type regulatory, policy, or government_bond.
    Used by the commodity dashboard 'National & regulatory' panel. Optionally filtered by commodity keywords.
    """
    _check_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        try:
            from domains.finance.commodity_registry import get_commodity_ids

            reg_ids = [x.lower() for x in get_commodity_ids()]
        except Exception:
            reg_ids = ["gold", "silver", "platinum"]
        fetch_limit = limit * 3 if commodity and (commodity or "").lower() in reg_ids else limit
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, event_type, event_name, start_date, end_date, geographic_scope, domain_keys
                FROM intelligence.tracked_events
                WHERE %s = ANY(domain_keys)
                  AND event_type = ANY(%s)
                ORDER BY start_date DESC NULLS LAST
                LIMIT %s
                """,
                (domain, list(REGULATORY_EVENT_TYPES), fetch_limit),
            )
            rows = cur.fetchall()
        conn.close()
        events = [
            {
                "id": r[0],
                "event_type": r[1],
                "event_name": r[2],
                "start_date": str(r[3]) if r[3] else None,
                "end_date": str(r[4]) if r[4] else None,
                "geographic_scope": r[5],
                "domain_keys": list(r[6]) if r[6] else [],
            }
            for r in rows
        ]
        if commodity and (commodity or "").lower() in reg_ids:
            from domains.finance.news_orchestrator import is_relevant_to_commodity

            combined = [
                (ev, (ev.get("event_name") or "") + " " + (ev.get("geographic_scope") or ""))
                for ev in events
            ]
            events = [ev for ev, text in combined if is_relevant_to_commodity(text, commodity)][
                :limit
            ]
        return {
            "success": True,
            "data": {"events": events},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching commodity regulatory-events: {e}", exc_info=True)
        try:
            conn.close()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/finance/edgar/ingest")  # Infrastructure: EDGAR 10-K via orchestrator
async def trigger_edgar_ingest(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    filings_per_company: int = Query(1, ge=1, le=5, description="10-K filings per company"),
):
    """Fetch 10-K filings for mining companies via orchestrator. Refresh+ingest task."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    try:
        task_id = orch.submit_task(
            TaskType.ingest,
            {"source": "edgar", "filings_per_company": filings_per_company},
            priority=TaskPriority.high,
        )
        result = await orch.run_task(task_id)
        if not result or (hasattr(result.status, "value") and result.status.value == "failed"):
            raise HTTPException(
                status_code=503,
                detail=result.warnings[0] if result and result.warnings else "EDGAR ingest failed",
            )
        data = result.output or {}
        return {
            "success": True,
            "data": {
                "chunks_embedded": data.get("chunks_embedded", 0),
                "chunk_ids": data.get("chunk_ids", [])[:50],
            },
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting EDGAR: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/finance/analyze")  # Analysis task via orchestrator
async def trigger_analysis(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    query: str = Query(..., description="Analysis query (e.g. gold price trend)"),
    topic: str = Query("gold", description="Data topic: gold, all, fred"),
    start_date: str | None = Query(None, description="Date range start YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Date range end YYYY-MM-DD"),
    wait: bool = Query(
        True, description="If True, await completion; if False, return task_id for polling"
    ),
    deep: bool = Query(
        False, description="If True, pull more RSS, RAG, and historic expansions for richer context"
    ),
):
    """Submit analysis task. Use wait=false to get task_id and poll GET /tasks/{id}. Use deep=true for more evidence (RAG, more news, historic expansions)."""
    logger.info(
        "Finance analyze request: domain=%s query=%r topic=%s wait=%s deep=%s start_date=%s end_date=%s",
        domain,
        query[:80] if query else "",
        topic,
        wait,
        deep,
        start_date,
        end_date,
    )
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    params: dict = {"query": query, "topic": topic}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if deep:
        params["deep"] = True
    if start_date and end_date:
        logger.info("Historic context will run: date range %s to %s", start_date, end_date)
    try:
        task_id = orch.submit_task(
            TaskType.analysis,
            params,
            priority=TaskPriority.high,
        )
        if not wait:
            return {
                "success": True,
                "data": {"task_id": task_id},
                "timestamp": datetime.now().isoformat(),
            }
        result = await orch.run_task(task_id)
        if not result:
            raise HTTPException(status_code=503, detail="Analysis task failed")
        if hasattr(result.status, "value") and result.status.value == "failed":
            raise HTTPException(
                status_code=503, detail=result.warnings[0] if result.warnings else "Analysis failed"
            )
        data = result.output or {}
        out = {
            "response": data.get("response", ""),
            "query": data.get("query", query),
            "task_id": task_id,
        }
        if data.get("verification"):
            out["verification"] = data["verification"]
        if result.confidence is not None:
            out["confidence"] = result.confidence
        return {"success": True, "data": out, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in analysis: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{domain}/finance/analyze/enhance")
async def trigger_analysis_enhance(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    query: str = Query(..., description="Same analysis query to run with more context"),
    topic: str = Query("gold", description="Data topic: gold, silver, platinum, all, fred"),
    start_date: str | None = Query(None, description="Date range start YYYY-MM-DD"),
    end_date: str | None = Query(None, description="Date range end YYYY-MM-DD"),
    wait: bool = Query(
        True, description="If True, await completion; if False, return task_id for polling"
    ),
):
    """
    Re-run analysis with more data: more RSS (35), RAG on, historic context with 2 expansions.
    Use after an initial analysis when you want the system to review and pull in more evidence.
    Returns same shape as POST /analyze.
    """
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    params: dict = {"query": query, "topic": topic, "deep": True}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    try:
        task_id = orch.submit_task(TaskType.analysis, params, priority=TaskPriority.high)
        if not wait:
            return {
                "success": True,
                "data": {"task_id": task_id, "enhance": True},
                "timestamp": datetime.now().isoformat(),
            }
        result = await orch.run_task(task_id)
        if not result:
            raise HTTPException(status_code=503, detail="Enhance analysis failed")
        if hasattr(result.status, "value") and result.status.value == "failed":
            raise HTTPException(
                status_code=503, detail=result.warnings[0] if result.warnings else "Enhance failed"
            )
        data = result.output or {}
        out = {
            "response": data.get("response", ""),
            "query": data.get("query", query),
            "task_id": task_id,
            "enhance": True,
        }
        if data.get("verification"):
            out["verification"] = data["verification"]
        if result.confidence is not None:
            out["confidence"] = result.confidence
        return {"success": True, "data": out, "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Enhance analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Research topics (saved analyses for continual refinement)
# ---------------------------------------------------------------------------


@router.get("/{domain}/finance/research-topics")
async def list_research_topics(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    last_refined_task_id: str | None = Query(
        None, description="Return topic whose last refinement is this task"
    ),
):
    """List saved research topics (analyses that can be refined over time)."""
    validate_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if last_refined_task_id:
                cur.execute(
                    """
                    SELECT id, name, query, topic, date_range_start, date_range_end, summary,
                           source_task_id, last_refined_task_id, last_refined_at, created_at, updated_at
                    FROM finance.research_topics
                    WHERE last_refined_task_id = %s
                    LIMIT 1
                    """,
                    (last_refined_task_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, name, query, topic, date_range_start, date_range_end, summary,
                           source_task_id, last_refined_task_id, last_refined_at, created_at, updated_at
                    FROM finance.research_topics
                    ORDER BY updated_at DESC NULLS LAST, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            rows = cur.fetchall()
        return {
            "success": True,
            "data": {"topics": [dict(r) for r in rows]},
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.exception("list_research_topics failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.get("/{domain}/finance/research-topics/{topic_id}")
async def get_research_topic(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
):
    """Get a single research topic by id."""
    validate_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, query, topic, date_range_start, date_range_end, summary,
                       source_task_id, last_refined_task_id, last_refined_at, created_at, updated_at
                FROM finance.research_topics WHERE id = %s
                """,
                (topic_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Research topic not found")
        return {"success": True, "data": dict(row), "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_research_topic failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{domain}/finance/research-topics")
async def create_research_topic(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    body: dict = Body(...),
):
    """
    Save a completed analysis as a research topic for continual refinement.
    Body: task_id (required), name (required), query (required), topic (optional), date_range (optional {start,end}).
    Summary is taken from the task result when available.
    """
    logger.info(
        "create_research_topic: domain=%s body_keys=%s task_id=%s name_present=%s query_len=%s",
        domain,
        list(body.keys()) if isinstance(body, dict) else type(body).__name__,
        body.get("task_id") if isinstance(body, dict) else None,
        bool((body.get("name") or "").strip()) if isinstance(body, dict) else False,
        len((body.get("query") or "").strip()) if isinstance(body, dict) else 0,
    )
    validate_domain(domain)
    task_id = body.get("task_id")
    name = (body.get("name") or "").strip()
    query = (body.get("query") or "").strip()
    if not task_id or not name or not query:
        missing = []
        if not task_id:
            missing.append("task_id")
        if not name:
            missing.append("name")
        if not query:
            missing.append("query")
        detail = f"task_id, name, and query are required; missing: {', '.join(missing)}"
        logger.warning("create_research_topic validation failed: %s", detail)
        raise HTTPException(status_code=400, detail=detail)
    topic = (body.get("topic") or "gold").strip() or "gold"
    date_range = body.get("date_range") or {}
    start_date = date_range.get("start") if isinstance(date_range, dict) else None
    end_date = date_range.get("end") if isinstance(date_range, dict) else None

    summary = body.get("summary")
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if orch:
        result = orch.get_task_result(task_id)
        if result and result.output:
            if not summary:
                summary = result.output.get("response") or ""
            # Use task's commodity (topic) when not provided so platinum analyses save as platinum
            if (not body.get("topic") or (topic or "").strip() == "gold") and result.output.get(
                "topic"
            ):
                topic = (result.output.get("topic") or "gold").strip() or "gold"
            if not start_date and result.output.get("start_date"):
                start_date = result.output.get("start_date")
            if not end_date and result.output.get("end_date"):
                end_date = result.output.get("end_date")

    if not summary:
        summary = ""

    conn = get_db_connection()
    if not conn:
        logger.warning("create_research_topic: no DB connection (503)")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable. Set DB_PASSWORD in project-root .env and restart the API (e.g. ./start_system.sh or restart uvicorn).",
        )
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO finance.research_topics
                (name, query, topic, date_range_start, date_range_end, summary, source_task_id, last_refined_at)
                VALUES (%s, %s, %s, %s::date, %s::date, %s, %s, NULL)
                RETURNING id, name, query, topic, date_range_start, date_range_end, summary,
                          source_task_id, last_refined_task_id, last_refined_at, created_at, updated_at
                """,
                (
                    name,
                    query,
                    topic,
                    start_date or None,
                    end_date or None,
                    summary or None,
                    task_id,
                ),
            )
            row = cur.fetchone()
            conn.commit()
        return {"success": True, "data": dict(row), "timestamp": datetime.now().isoformat()}
    except Exception as e:
        conn.rollback()
        logger.exception("create_research_topic failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{domain}/finance/research-topics/{topic_id}/refine")
async def refine_research_topic(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
):
    """
    Re-run analysis for this topic (same query, topic, date range) and return the new task_id.
    User can poll the task and then update the topic from the result (PATCH with task_id).
    """
    validate_domain(domain)
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT id, query, topic, date_range_start, date_range_end, last_refined_task_id
                   FROM finance.research_topics WHERE id = %s""",
                (topic_id,),
            )
            row = cur.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Research topic not found")
        conn.close()

        # Guard: don't start another refinement if one is already queued or running
        last_task_id = row.get("last_refined_task_id")
        orch = getattr(request.app.state, "finance_orchestrator", None)
        if not orch:
            raise HTTPException(status_code=503, detail="Finance orchestrator not available")
        if last_task_id:
            existing = orch.get_task_status(last_task_id)
            if existing:
                status = (existing.get("status") or "").lower()
                if status in ("queued", "planning", "executing", "evaluating", "revising"):
                    return JSONResponse(
                        status_code=409,
                        content={
                            "detail": "Refinement already in progress",
                            "task_id": last_task_id,
                            "status": status,
                        },
                    )

        query = row["query"]
        topic = row["topic"] or "gold"
        start_date = str(row["date_range_start"]) if row.get("date_range_start") else None
        end_date = str(row["date_range_end"]) if row.get("date_range_end") else None

        params = {"query": query, "topic": topic}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        new_task_id = orch.submit_task(TaskType.analysis, params, priority=TaskPriority.high)

        conn = get_db_connection()
        if not conn:
            return {
                "success": True,
                "data": {
                    "task_id": new_task_id,
                    "message": "Refinement started; update topic from result when complete.",
                },
                "timestamp": datetime.now().isoformat(),
            }
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE finance.research_topics
                    SET last_refined_task_id = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (new_task_id, topic_id),
                )
                conn.commit()
        finally:
            conn.close()

        return {
            "success": True,
            "data": {
                "task_id": new_task_id,
                "message": "Refinement started; open the result and use 'Update topic' to save the new summary.",
            },
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("refine_research_topic failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{domain}/finance/research-topics/{topic_id}")
async def update_research_topic_from_task(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    topic_id: int = Path(..., ge=1),
    body: dict = Body(...),
):
    """
    Update a research topic's summary (and last_refined_*) from a completed task result.
    Body: task_id (required). Optionally name to rename the topic.
    """
    validate_domain(domain)
    task_id = body.get("task_id")
    name = body.get("name")
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    summary = None
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if orch:
        result = orch.get_task_result(task_id)
        if result and result.output:
            summary = result.output.get("response")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=503, detail="Database unavailable")
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM finance.research_topics WHERE id = %s", (topic_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Research topic not found")
            updates = [
                "last_refined_task_id = %s",
                "last_refined_at = CURRENT_TIMESTAMP",
                "updated_at = CURRENT_TIMESTAMP",
            ]
            args = [task_id]
            if summary is not None:
                updates.insert(0, "summary = %s")
                args.insert(0, summary)
            if name is not None and str(name).strip():
                updates.insert(0, "name = %s")
                args.insert(0, str(name).strip())
            args.append(topic_id)
            cur.execute(
                "UPDATE finance.research_topics SET " + ", ".join(updates) + " WHERE id = %s",
                args,
            )
            conn.commit()
            cur.execute(
                "SELECT id, name, query, topic, summary, last_refined_task_id, last_refined_at, updated_at FROM finance.research_topics WHERE id = %s",
                (topic_id,),
            )
            row = cur.fetchone()
        return {"success": True, "data": dict(row), "timestamp": datetime.now().isoformat()}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        logger.exception("update_research_topic_from_task failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.post("/{domain}/finance/fetch-fred")  # Infrastructure: FRED via orchestrator
async def trigger_fred_fetch(
    request: Request,
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    symbol: str = Query(..., description="FRED series ID (e.g. IQ12260, DCOILWTICO)"),
    start_date: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end_date: str | None = Query(None, description="End date YYYY-MM-DD"),
):
    """Trigger FRED fetch via orchestrator. Requires FRED_API_KEY."""
    _check_domain(domain)
    orch = getattr(request.app.state, "finance_orchestrator", None)
    if not orch:
        raise HTTPException(status_code=503, detail="Finance orchestrator not available")
    try:
        task_id = orch.submit_task(
            TaskType.refresh,
            {"topic": "fred", "symbol": symbol, "start_date": start_date, "end_date": end_date},
            priority=TaskPriority.high,
        )
        result = await orch.run_task(task_id)
        if not result or (hasattr(result.status, "value") and result.status.value == "failed"):
            raise HTTPException(
                status_code=503,
                detail=result.warnings[0] if result and result.warnings else "FRED fetch failed",
            )
        data = result.output or {}
        src = data.get("sources", {})
        fred_info = src.get("fred", {})
        count = fred_info.get("count", 0)
        return {
            "success": True,
            "data": {"symbol": symbol, "observations_fetched": count},
            "timestamp": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching FRED: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{domain}/finance/market-trends")  # PostgreSQL: validate_domain
async def get_market_trends(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    timeframe: str | None = Query("7d", description="Timeframe: 1d, 7d, 30d, 90d, 1y"),
    sector: str | None = Query(None, description="Filter by sector"),
):
    """
    Get market trends: article volume by day and optional gold summary.
    Minimal implementation using finance-domain articles and stored gold.
    """
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        delta = _parse_timeframe(timeframe or "7d")
        days = max(1, delta.days)
        articles = _get_recent_finance_articles(days=days, limit=500)

        # Article count by date (date string key)
        by_date = Counter()
        for a in articles:
            pub = a.get("published_at") or a.get("published_date")
            if pub:
                d = (
                    pub.date()
                    if hasattr(pub, "date")
                    else (pub[:10] if isinstance(pub, str) else None)
                )
                if d:
                    by_date[str(d)] += 1

        trends = [{"date": d, "article_count": c} for d, c in sorted(by_date.items())]

        # Optional: latest gold from store
        gold_latest = None
        try:
            from domains.finance.gold_amalgamator import get_stored

            end = datetime.now(timezone.utc).date()
            start = end - timedelta(days=min(days, 31))
            stored = get_stored(start=str(start), end=str(end))
            if stored:
                for obs_list in stored.values():
                    if obs_list and isinstance(obs_list, list):
                        with_val = [o for o in obs_list if o.get("value") is not None]
                        if with_val:
                            gold_latest = with_val[-1].get("value")
                            break
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "timeframe": timeframe or "7d",
                "sector": sector,
                "trends": trends,
                "total_articles": len(articles),
                "gold_latest": gold_latest,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Simple stopwords for title-word patterns (minimal set)
_STOP = frozenset(
    "a an the and or but in on at to for of with by from as is was are were be been being".split()
)


@router.get("/{domain}/finance/market-patterns")
async def get_market_patterns(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    pattern_type: str | None = Query(None, description="Pattern type filter"),
    min_confidence: float | None = Query(
        0.5, ge=0.0, le=1.0, description="Minimum confidence score"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get market patterns: simple keyword/category aggregates from recent finance articles.
    Minimal implementation.
    """
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        articles = _get_recent_finance_articles(days=30, limit=300)

        # Category counts if present
        by_category = Counter()
        for a in articles:
            cat = a.get("category") or a.get("processing_status") or "uncategorized"
            if isinstance(cat, str):
                by_category[cat] += 1

        # Top words from titles (alphanumeric, length > 2, not stopwords)
        word_counts = Counter()
        for a in articles:
            title = (a.get("title") or "").lower()
            for word in re.findall(r"[a-z0-9]+", title):
                if len(word) > 2 and word not in _STOP:
                    word_counts[word] += 1

        patterns = [
            {"name": "category:" + k, "count": v, "type": "category"}
            for k, v in by_category.most_common(15)
        ] + [
            {"name": "keyword:" + k, "count": v, "type": "keyword"}
            for k, v in word_counts.most_common(20)
        ]
        patterns = patterns[offset : offset + limit]

        return {
            "success": True,
            "data": {
                "patterns": patterns,
                "pattern_type": pattern_type,
                "min_confidence": min_confidence,
                "total": len(by_category) + len(word_counts),
                "total_articles": len(articles),
                "limit": limit,
                "offset": offset,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching market patterns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Keywords that suggest corporate-announcement content (minimal set)
_ANNOUNCEMENT_KEYWORDS = [
    "earnings",
    "acquisition",
    "dividend",
    "ceo",
    "merger",
    "revenue",
    "forecast",
    "guidance",
    "ipo",
    "buyback",
    "layoff",
    "restructuring",
    "sec",
    "filings",
    "quarterly",
    "annual report",
    "board",
    "cfo",
    "executive",
]


@router.get("/{domain}/finance/corporate-announcements")
async def get_corporate_announcements(
    domain: str = Path(..., pattern=DOMAIN_PATH_PATTERN),
    company: str | None = Query(None, description="Filter by company name"),
    announcement_type: str | None = Query(None, description="Filter by announcement type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Get corporate announcements: finance articles matching announcement-related keywords.
    Minimal implementation; filters title/summary by keyword presence.
    """
    try:
        if not validate_domain(domain):
            raise HTTPException(status_code=400, detail=f"Invalid domain: {domain}")

        articles = _get_recent_finance_articles(days=30, limit=300)
        combined = _ANNOUNCEMENT_KEYWORDS

        announcements = []
        for a in articles:
            title = (a.get("title") or "").lower()
            summary = (a.get("summary") or "").lower()
            text = title + " " + summary
            matched = [kw for kw in combined if kw in text]
            if not matched:
                continue
            if company and company.lower() not in text:
                continue
            snippet = (a.get("summary") or a.get("title") or "")[:200]
            pub = a.get("published_at") or a.get("published_date")
            announcements.append(
                {
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "published_at": pub.isoformat()
                    if hasattr(pub, "isoformat")
                    else str(pub)
                    if pub
                    else None,
                    "snippet": snippet,
                    "matched_keywords": matched,
                }
            )

        total = len(announcements)
        announcements = announcements[offset : offset + limit]

        return {
            "success": True,
            "data": {
                "announcements": announcements,
                "company": company,
                "announcement_type": announcement_type,
                "total": total,
                "limit": limit,
                "offset": offset,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching corporate announcements: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
