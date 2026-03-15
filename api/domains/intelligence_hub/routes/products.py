"""
Intelligence products API — daily brief, generate_brief, alert_digest (P2).
Unifies DailyBriefingService and watchlist/event alerts behind /api/products/*.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body, Path

logger = logging.getLogger(__name__)


def _build_llm_lead_prompt(key_developments: Dict[str, Any], domain: str) -> str:
    """Build context string (editorial ledes, headlines, storylines, event briefings) for LLM briefing lead."""
    parts = []
    # Prefer editorial ledes (richer content from editorial_document)
    editorial_ledes = key_developments.get("editorial_ledes") or []
    if editorial_ledes:
        ledes = [f"- {l.get('title', '')}: {l.get('lede', '')}" for l in editorial_ledes[:4] if l.get("lede")]
        if ledes:
            parts.append("Storyline editorial ledes:\n" + "\n".join(ledes))
    # Headlines with summaries when available
    headlines = key_developments.get("top_headlines") or []
    if headlines:
        head_lines = []
        for h in headlines[:6]:
            t = (h.get("title") or "").strip()
            s = (h.get("summary") or "").strip()
            if t:
                head_lines.append(f"- {t}" + (f": {s[:200]}" if s else ""))
        if head_lines:
            parts.append("Key headlines from the last few days:\n" + "\n".join(head_lines))
    # Storyline titles
    storylines_list = key_developments.get("top_storylines") or []
    story_titles = [ (s.get("title") or "").strip() for s in storylines_list[:5] if (s.get("title") or "").strip() ]
    if story_titles:
        parts.append("Active storylines:\n" + "\n".join("- " + t for t in story_titles))
    # Event briefings
    event_briefings = key_developments.get("event_briefings") or []
    if event_briefings:
        ev_lines = [f"- {e.get('headline') or e.get('event_name', '')}" for e in event_briefings[:3] if e.get("headline") or e.get("event_name")]
        if ev_lines:
            parts.append("Recent events:\n" + "\n".join(ev_lines))
    return "\n\n".join(parts) if parts else ""

router = APIRouter(prefix="/api", tags=["Intelligence products"])


def _brief_to_content(brief: Dict[str, Any]) -> str:
    """Turn briefing sections into a single narrative string for the UI. Leads with editorial (headlines/storylines), then metrics. Uses last 3 days of data."""
    sections = brief.get("sections") or {}
    parts = []
    days = brief.get("days_window", 3)

    # Editorial layer first: editorial ledes (from editorial_document) > headlines > storylines > event briefings
    kd = sections.get("key_developments") or {}
    if kd.get("has_content"):
        # Best: editorial ledes from storylines that have editorial_document populated
        editorial_ledes = kd.get("editorial_ledes") or []
        if editorial_ledes:
            ledes = [l.get("lede", "").strip() for l in editorial_ledes[:3] if l.get("lede", "").strip()]
            if ledes:
                parts.append("Top stories: " + " ".join(ledes))

        # Headlines from articles
        headlines = kd.get("top_headlines") or []
        if headlines and not editorial_ledes:
            lead = " ".join((h.get("title") or "").strip() for h in headlines[:5] if (h.get("title") or "").strip())
            if lead:
                parts.append("Key developments: " + lead)

        # Storyline titles
        storylines_list = kd.get("top_storylines") or []
        if storylines_list:
            titles = [ (s.get("title") or "").strip() for s in storylines_list[:5] if (s.get("title") or "").strip() ]
            if titles:
                parts.append("Leading storylines: " + "; ".join(titles))

        # Event briefings
        event_briefings = kd.get("event_briefings") or []
        if event_briefings:
            event_lines = []
            for eb in event_briefings[:3]:
                headline = (eb.get("headline") or eb.get("event_name") or "").strip()
                excerpt = (eb.get("briefing_excerpt") or "").strip()
                if headline:
                    event_lines.append(headline + (": " + excerpt[:100] if excerpt else ""))
            if event_lines:
                parts.append("Events: " + " | ".join(event_lines))

    # Then supporting metrics
    so = sections.get("system_overview") or {}
    if so and "error" not in so:
        parts.append(
            "System overview (last {} days): {} new articles, {} updated.".format(
                days, so.get("today_new_articles", 0), so.get("today_updated_articles", 0)
            )
        )
    ca = sections.get("content_analysis") or {}
    if ca and "error" not in ca:
        total = ca.get("total_articles_analyzed", sum(c.get("count", 0) for c in ca.get("category_distribution", [])))
        parts.append(
            "Content (last {} days): {} categories, {} articles analyzed.".format(
                days, len(ca.get("category_distribution", [])), total
            )
        )
    sa = sections.get("storyline_analysis") or {}
    if sa and "error" not in sa:
        daily_summary = (sa.get("daily_summary") or "").strip()
        if daily_summary:
            parts.append("Summary: " + daily_summary[:500])
        parts.append("Storyline analysis: {} articles in topic cloud.".format(sa.get("article_count", 0)))
    qm = sections.get("quality_metrics") or {}
    if qm and "error" not in qm:
        score = qm.get("overall_quality_score")
        parts.append("Quality: {} avg score.".format(score if score is not None else "N/A"))
    rec = sections.get("recommendations") or {}
    actions = (
        rec.get("priority_actions", [])
        + rec.get("content_quality", [])
        + rec.get("story_monitoring", [])
        + rec.get("system_optimization", [])
    )
    if actions:
        parts.append("Recommendations: " + " ".join(actions[:3]))
    return "\n\n".join(parts) if parts else "Daily briefing generated (last {} days). No sections available.".format(days)


def _get_daily_briefing_service():
    """Lazy init DailyBriefingService with shared db_config."""
    from shared.database.connection import get_db_config
    from modules.ml.daily_briefing_service import DailyBriefingService
    return DailyBriefingService(get_db_config())


@router.post("/products/generate_brief")
def post_generate_brief(
    date: Optional[str] = Body(None, embed=True, description="YYYY-MM-DD; default today"),
    domain: Optional[str] = Body(None, embed=True),
    include_anomalies: bool = Body(True, embed=True),
    include_storylines: bool = Body(True, embed=True),
    include_deduplication: bool = Body(True, embed=True),
) -> Dict[str, Any]:
    """Generate a daily brief on demand. Returns brief sections and generated_at."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=include_deduplication,
            include_storylines=include_storylines,
        )
        if "error" in brief:
            return {"success": False, "data": None, "message": brief["error"]}
        out = {
            "brief_id": None,
            "sections": brief.get("sections", {}),
            "statistics": brief.get("statistics", {}),
            "generated_at": brief.get("generated_at"),
            "briefing_date": brief.get("briefing_date"),
        }
        if include_anomalies and domain:
            try:
                from services.intelligence_analysis_service import get_intelligence_service
                anomalies = get_intelligence_service().detect_anomalies(domain, hours=24)
                out["anomalies"] = [
                    {
                        "entity_type": a.entity_type,
                        "entity_id": a.entity_id,
                        "severity": a.severity,
                        "description": a.description,
                        "detected_at": a.detected_at.isoformat(),
                    }
                    for a in anomalies[:20]
                ]
            except Exception as e:
                logger.debug("Anomalies in brief failed: %s", e)
                out["anomalies"] = []
        return {"success": True, "data": out, "message": None}
    except Exception as e:
        logger.warning("generate_brief failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.post("/{domain}/intelligence/briefings/daily")
async def post_domain_daily_briefing(
    domain: str = Path(..., description="Domain key (e.g. politics, finance, science-tech)"),
    date: Optional[str] = Body(None, embed=True, description="YYYY-MM-DD; default today"),
    use_llm_lead: bool = Body(True, embed=True, description="If true and key developments exist, prepend an LLM-generated lead paragraph"),
) -> Dict[str, Any]:
    """Generate an AI summary of today's developments for the given domain. Used by Briefings UI."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=True,
            include_storylines=True,
            domain=domain,
        )
        if "error" in brief:
            return {"success": False, "error": brief["error"], "data": None, "message": brief["error"]}
        content = _brief_to_content(brief)
        # Optional: prepend LLM-generated editorial lead when we have key developments
        kd = (brief.get("sections") or {}).get("key_developments") or {}
        if use_llm_lead and kd.get("has_content"):
            context = _build_llm_lead_prompt(kd, domain)
            if context:
                try:
                    from shared.services.llm_service import llm_service
                    result = await llm_service.generate_briefing_lead(context, domain=domain)
                    if result.get("success") and result.get("summary"):
                        lead = (result["summary"] or "").strip()
                        if lead:
                            content = "Lead: " + lead + "\n\n" + content
                except Exception as llm_err:
                    logger.debug("LLM lead for briefing skipped: %s", llm_err)
        stats = brief.get("statistics") or {}
        article_count = stats.get("total_articles", 0)
        data = {
            "content": content,
            "article_count": article_count,
            "briefing_date": brief.get("briefing_date"),
            "generated_at": brief.get("generated_at"),
            "sections": brief.get("sections", {}),
            "statistics": stats,
        }
        return {"success": True, "data": data, "content": content, "article_count": article_count, "message": None}
    except Exception as e:
        logger.warning("domain daily briefing failed: %s", e)
        return {"success": False, "error": str(e), "data": None, "message": str(e)}


@router.get("/products/daily_brief")
def get_daily_brief(
    date: Optional[str] = Query(None, description="YYYY-MM-DD; default today"),
) -> Dict[str, Any]:
    """Return daily brief for the given date (generated on demand)."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=True,
            include_storylines=True,
        )
        if "error" in brief:
            return {"success": False, "data": None, "message": brief["error"]}
        content = _brief_to_content(brief)
        return {
            "success": True,
            "data": {
                "briefing_date": brief.get("briefing_date"),
                "generated_at": brief.get("generated_at"),
                "content": content,
                "sections": brief.get("sections", {}),
                "statistics": brief.get("statistics", {}),
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("daily_brief failed: %s", e)
        return {"success": False, "data": None, "message": str(e)}


@router.get("/products/weekly_digest")
def get_weekly_digest(
    week_start: Optional[str] = Query(None, description="YYYY-MM-DD (Monday) for a specific week"),
    limit: int = Query(10, ge=1, le=52),
) -> Dict[str, Any]:
    """Return stored weekly digests. If week_start given, return that week's digest if present."""
    from services.digest_automation_service import get_digest_service

    svc = get_digest_service()
    if week_start:
        try:
            ws = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "data": None, "message": "Invalid week_start; use YYYY-MM-DD"}
        digests = [d for d in svc.get_latest_weekly_digests(limit=52) if d.get("week_start") == week_start]
        if not digests:
            return {"success": True, "data": {"digests": [], "count": 0}, "message": None}
        return {"success": True, "data": {"digests": digests, "count": len(digests)}, "message": None}
    digests = svc.get_latest_weekly_digests(limit=limit)
    return {"success": True, "data": {"digests": digests, "count": len(digests)}, "message": None}


@router.get("/products/alert_digest")
def get_alert_digest(
    since: Optional[int] = Query(None, description="Only alerts from last N hours"),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
) -> Dict[str, Any]:
    """Alert digest: watchlist alerts (and optionally event alerts) bundled."""
    from shared.database.connection import get_db_connection
    from services.watchlist_service import WatchlistService

    conn = get_db_connection()
    if not conn:
        return {"success": False, "data": None, "message": "Database unavailable"}
    try:
        svc = WatchlistService(conn)
        alerts = svc.get_alerts(unread_only=unread_only, limit=limit)
        if since is not None:
            cutoff = datetime.utcnow() - timedelta(hours=since)
            def _parsed(ts):
                if not ts:
                    return None
                try:
                    return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    return None
            alerts = [a for a in alerts if _parsed(a.get("created_at")) and _parsed(a["created_at"]) >= cutoff]
        conn.close()

        # Build editorial digest summary from alert content
        digest_summary = ""
        if alerts:
            alert_descriptions = [
                (a.get("description") or a.get("title") or a.get("alert_type", "")).strip()
                for a in alerts[:5] if a.get("description") or a.get("title")
            ]
            if alert_descriptions:
                digest_summary = f"{len(alerts)} alerts. Key: {'; '.join(alert_descriptions[:3])}."
            else:
                digest_summary = f"{len(alerts)} watchlist alerts in this period."

        return {
            "success": True,
            "data": {
                "alerts": alerts,
                "count": len(alerts),
                "digest_summary": digest_summary,
                "generated_at": datetime.utcnow().isoformat() + "Z",
            },
            "message": None,
        }
    except Exception as e:
        logger.warning("alert_digest failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "data": None, "message": str(e)}
