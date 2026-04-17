"""
Intelligence products API — daily brief, generate_brief, alert_digest (P2).
Content feedback (usefulness, not interested) and briefing_feed for Briefings UI.
See docs/DATA_PIPELINE_ENHANCEMENTS_ROADMAP.md.
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Path, Query

logger = logging.getLogger(__name__)


def _sanitize_briefing_line_text(text: str) -> str:
    try:
        from shared.llm_text_sanitize import strip_llm_wrapping_artifacts

        return strip_llm_wrapping_artifacts(text, max_length=2000)
    except Exception:
        return (text or "").strip()


def _build_llm_lead_prompt(key_developments: dict[str, Any], domain: str) -> str:
    """Build context string for LLM briefing lead. Marks recent vs older items so the LLM can prioritize today's developments."""
    parts = []
    editorial_ledes = key_developments.get("editorial_ledes") or []
    if editorial_ledes:
        ledes = []
        for lede_item in editorial_ledes[:4]:
            if lede_item.get("lede"):
                tag = " [recent]" if lede_item.get("recent") else ""
                ledes.append(f"- {lede_item.get('title', '')}{tag}: {lede_item.get('lede', '')}")
        if ledes:
            parts.append("Storyline editorial ledes (prefer [recent]):\n" + "\n".join(ledes))
    headlines = key_developments.get("top_headlines") or []
    if headlines:
        head_lines = [
            f"- {(h.get('title') or '').strip()}"
            + (f": {(h.get('summary') or '')[:150]}" if h.get("summary") else "")
            for h in headlines[:6]
            if (h.get("title") or "").strip()
        ]
        if head_lines:
            parts.append("Key headlines:\n" + "\n".join(head_lines))
    storylines_list = key_developments.get("top_storylines") or []
    if storylines_list:
        story_lines = []
        for s in storylines_list[:5]:
            t = (s.get("title") or "").strip()
            if t:
                tag = " [recent activity]" if s.get("recent") else " [older]"
                story_lines.append("- " + t + tag)
        if story_lines:
            parts.append(
                "Storylines (prefer those with recent activity):\n" + "\n".join(story_lines)
            )
    event_briefings = key_developments.get("event_briefings") or []
    if event_briefings:
        ev_lines = [
            f"- {e.get('headline') or e.get('event_name', '')}"
            for e in event_briefings[:4]
            if e.get("headline") or e.get("event_name")
        ]
        if ev_lines:
            parts.append("Events:\n" + "\n".join(ev_lines))
    return "\n\n".join(parts) if parts else ""


router = APIRouter(prefix="/api", tags=["Intelligence products"])


def _brief_to_content(brief: dict[str, Any]) -> str:
    """Turn briefing sections into a single narrative for the UI. Clear sections: what's new (ledes/headlines), storylines (with recency), events, then metrics. Uses last 3 days of data."""
    sections = brief.get("sections") or {}
    parts = []
    days = brief.get("days_window", 3)

    kd = sections.get("key_developments") or {}
    if kd.get("has_content"):
        # --- What's new (editorial ledes or top headlines) ---
        editorial_ledes = kd.get("editorial_ledes") or []
        headlines = kd.get("top_headlines") or []
        if editorial_ledes:
            ledes = []
            for item in editorial_ledes[:3]:
                raw = (item.get("lede") or "").strip()
                if not raw:
                    continue
                cleaned = _sanitize_briefing_line_text(raw)
                if cleaned:
                    ledes.append(cleaned)
            if ledes:
                parts.append("What's new\n" + "\n".join("• " + lede for lede in ledes))
        elif headlines:
            lead_items = [
                (h.get("title") or "").strip()
                for h in headlines[:5]
                if (h.get("title") or "").strip()
            ]
            if lead_items:
                parts.append("What's new\n" + "\n".join("• " + t for t in lead_items))

        # --- Storylines (with recency when available) ---
        storylines_list = kd.get("top_storylines") or []
        if storylines_list:
            story_lines = []
            for s in storylines_list[:6]:
                title = (s.get("title") or "").strip()
                if not title:
                    continue
                recency = ""
                if s.get("recent"):
                    recency = " (recent)"
                elif s.get("last_article_at"):
                    recency = " (latest article in window)"
                story_lines.append("• " + title + recency)
            if story_lines:
                parts.append("Storylines\n" + "\n".join(story_lines))

        # --- Events ---
        event_briefings = kd.get("event_briefings") or []
        if event_briefings:
            event_lines = []
            for eb in event_briefings[:4]:
                headline = (eb.get("headline") or eb.get("event_name") or "").strip()
                excerpt = (eb.get("briefing_excerpt") or "").strip()
                if headline:
                    event_lines.append("• " + headline + (": " + excerpt[:120] if excerpt else ""))
            if event_lines:
                parts.append("Events\n" + "\n".join(event_lines))

    # --- Metrics ---
    metric_parts = []
    so = sections.get("system_overview") or {}
    if so and "error" not in so:
        metric_parts.append(
            "System overview (last {} days): {} new articles, {} updated.".format(
                days, so.get("today_new_articles", 0), so.get("today_updated_articles", 0)
            )
        )
    ca = sections.get("content_analysis") or {}
    if ca and "error" not in ca:
        total = ca.get(
            "total_articles_analyzed",
            sum(c.get("count", 0) for c in ca.get("category_distribution", [])),
        )
        metric_parts.append(
            "Content (last {} days): {} categories, {} articles analyzed.".format(
                days, len(ca.get("category_distribution", [])), total
            )
        )
    sa = sections.get("storyline_analysis") or {}
    if sa and "error" not in sa:
        daily_summary = (sa.get("daily_summary") or "").strip()
        if daily_summary:
            metric_parts.append("Summary: " + daily_summary[:500])
        metric_parts.append(
            "Storyline analysis: {} articles in topic cloud.".format(sa.get("article_count", 0))
        )
    qm = sections.get("quality_metrics") or {}
    if qm and "error" not in qm:
        score = qm.get("overall_quality_score")
        metric_parts.append("Quality: {} avg score.".format(score if score is not None else "N/A"))
    rec = sections.get("recommendations") or {}
    actions = (
        rec.get("priority_actions", [])
        + rec.get("content_quality", [])
        + rec.get("story_monitoring", [])
        + rec.get("system_optimization", [])
    )
    if actions:
        metric_parts.append("Recommendations: " + " ".join(actions[:3]))
    if metric_parts:
        parts.append("Metrics\n" + "\n".join(metric_parts))
    return (
        "\n\n".join(parts)
        if parts
        else f"Daily briefing generated (last {days} days). No sections available."
    )


def _get_daily_briefing_service():
    """Lazy init DailyBriefingService with shared db_config."""
    from modules.ml.daily_briefing_service import DailyBriefingService
    from shared.database.connection import get_db_config

    return DailyBriefingService(get_db_config())


@router.post("/products/generate_brief")
def post_generate_brief(
    date: str | None = Body(None, embed=True, description="YYYY-MM-DD; default today"),
    domain: str | None = Body(None, embed=True),
    include_anomalies: bool = Body(True, embed=True),
    include_storylines: bool = Body(True, embed=True),
    include_deduplication: bool = Body(True, embed=True),
) -> dict[str, Any]:
    """Generate a daily brief on demand. Returns brief sections and generated_at."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = (
            datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        )
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
    domain: str = Path(..., description="Domain key (e.g. politics, finance, artificial-intelligence)"),
    date: str | None = Body(None, embed=True, description="YYYY-MM-DD; default today"),
    use_llm_lead: bool = Body(
        True,
        embed=True,
        description="If true and key developments exist, prepend an LLM-generated lead paragraph",
    ),
) -> dict[str, Any]:
    """Generate an AI summary of today's developments for the given domain. Used by Briefings UI."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = (
            datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        )
        briefing_date_dt = datetime.combine(briefing_date, datetime.min.time())
        brief = svc.generate_daily_briefing(
            briefing_date_dt,
            include_deduplication=True,
            include_storylines=True,
            domain=domain,
        )
        if "error" in brief:
            return {
                "success": False,
                "error": brief["error"],
                "data": None,
                "message": brief["error"],
            }
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
                        lead = _sanitize_briefing_line_text((result["summary"] or "").strip())
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
        return {
            "success": True,
            "data": data,
            "content": content,
            "article_count": article_count,
            "message": None,
        }
    except Exception as e:
        logger.warning("domain daily briefing failed: %s", e)
        return {"success": False, "error": str(e), "data": None, "message": str(e)}


@router.get("/products/daily_brief")
def get_daily_brief(
    date: str | None = Query(None, description="YYYY-MM-DD; default today"),
) -> dict[str, Any]:
    """Return daily brief for the given date (generated on demand)."""
    try:
        svc = _get_daily_briefing_service()
        briefing_date = (
            datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
        )
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
    week_start: str | None = Query(None, description="YYYY-MM-DD (Monday) for a specific week"),
    limit: int = Query(10, ge=1, le=52),
) -> dict[str, Any]:
    """Return stored weekly digests. If week_start given, return that week's digest if present."""
    from services.digest_automation_service import get_digest_service

    svc = get_digest_service()
    if week_start:
        try:
            datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "data": None, "message": "Invalid week_start; use YYYY-MM-DD"}
        digests = [
            d for d in svc.get_latest_weekly_digests(limit=52) if d.get("week_start") == week_start
        ]
        if not digests:
            return {"success": True, "data": {"digests": [], "count": 0}, "message": None}
        return {
            "success": True,
            "data": {"digests": digests, "count": len(digests)},
            "message": None,
        }
    digests = svc.get_latest_weekly_digests(limit=limit)
    return {"success": True, "data": {"digests": digests, "count": len(digests)}, "message": None}


@router.get("/products/alert_digest")
def get_alert_digest(
    since: int | None = Query(None, description="Only alerts from last N hours"),
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
) -> dict[str, Any]:
    """Alert digest: watchlist alerts (and optionally event alerts) bundled."""
    from services.watchlist_service import WatchlistService
    from shared.database.connection import get_db_connection

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

            alerts = [
                a
                for a in alerts
                if _parsed(a.get("created_at")) and _parsed(a["created_at"]) >= cutoff
            ]
        conn.close()

        # Build editorial digest summary from alert content
        digest_summary = ""
        if alerts:
            alert_descriptions = [
                (a.get("description") or a.get("title") or a.get("alert_type", "")).strip()
                for a in alerts[:5]
                if a.get("description") or a.get("title")
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


# -----------------------------------------------------------------------------
# Content feedback and briefing feed (for Briefings UI)
# -----------------------------------------------------------------------------


@router.post("/{domain}/intelligence/feedback")
def post_content_feedback(
    domain: str = Path(..., description="Domain key (e.g. politics, finance, artificial-intelligence)"),
    item_type: str = Body(..., embed=True, description="article | storyline | briefing"),
    item_id: int | None = Body(None, embed=True),
    rating: int | None = Body(None, embed=True, ge=1, le=5),
    not_interested: bool = Body(False, embed=True),
) -> dict[str, Any]:
    """Submit usefulness (1-5) or 'not interested' for an article, storyline, or whole briefing."""
    from services.content_feedback_service import submit_feedback

    result = submit_feedback(
        domain, item_type, item_id, rating=rating, not_interested=not_interested
    )
    if result.get("success"):
        return {"success": True, "data": None, "message": "Feedback recorded"}
    return {"success": False, "data": None, "message": result.get("error", "Unknown error")}


def _get_schema_for_domain(domain: str) -> str | None:
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.debug("schema for domain %s: %s", domain, e)
        return None
    finally:
        conn.close()


@router.get("/{domain}/intelligence/briefing_feed")
def get_briefing_feed(
    domain: str = Path(..., description="Domain key (e.g. politics, finance, artificial-intelligence)"),
    articles_limit: int = Query(10, ge=1, le=50),
    storylines_limit: int = Query(6, ge=1, le=30),
) -> dict[str, Any]:
    """Return articles and storylines for Briefings page, reordered: not_interested excluded, sports/celebrity demoted."""
    from psycopg2.extras import RealDictCursor
    from services.briefing_filter_helper import sort_briefing_items_by_priority
    from services.content_feedback_service import get_not_interested_ids
    from shared.database.connection import get_db_connection

    schema = _get_schema_for_domain(domain)
    if not schema:
        return {"success": False, "data": None, "message": "Domain not found"}

    conn = get_db_connection()
    if not conn:
        return {"success": False, "data": None, "message": "Database unavailable"}

    try:
        not_art = get_not_interested_ids(domain, "article")
        not_story = get_not_interested_ids(domain, "storyline")

        articles = []
        storylines = []
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"""
                SELECT id, title, summary, url, published_at, source_domain, created_at
                FROM {schema}.articles
                WHERE title IS NOT NULL AND TRIM(title) != ''
                ORDER BY COALESCE(quality_tier, 4) ASC, COALESCE(quality_score, 0) DESC, published_at DESC NULLS LAST, created_at DESC
                LIMIT %s
                """,
                (articles_limit + len(not_art),),
            )
            for row in cur.fetchall():
                if row["id"] in not_art:
                    continue
                d = dict(row)
                d["source"] = d.get("source_domain")
                d["published_date"] = d.get("published_at")
                articles.append(d)
            articles = sort_briefing_items_by_priority(
                articles, title_key="title", summary_key="summary"
            )[:articles_limit]

            cur.execute(
                f"""
                SELECT id, title, description, updated_at, article_count, status, editorial_document
                FROM {schema}.storylines
                WHERE title IS NOT NULL AND TRIM(title) != ''
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (storylines_limit + len(not_story),),
            )
            storyline_rows = []
            for row in cur.fetchall():
                if row["id"] in not_story:
                    continue
                storyline_rows.append(dict(row))
            storyline_rows = sort_briefing_items_by_priority(
                storyline_rows, title_key="title", summary_key="description"
            )[:storylines_limit]
            storyline_ids = [s["id"] for s in storyline_rows]
            top_entities_by_storyline = {sid: [] for sid in storyline_ids}
            if storyline_ids:
                cur.execute(
                    f"""
                    WITH article_entities_agg AS (
                        SELECT sa.storyline_id, ae.canonical_entity_id, COUNT(*) AS cnt
                        FROM {schema}.storyline_articles sa
                        JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                        WHERE sa.storyline_id = ANY(%s)
                        GROUP BY sa.storyline_id, ae.canonical_entity_id
                    ),
                    ranked AS (
                        SELECT storyline_id, canonical_entity_id,
                               ROW_NUMBER() OVER (PARTITION BY storyline_id ORDER BY cnt DESC) AS rn
                        FROM article_entities_agg
                    )
                    SELECT r.storyline_id, ec.canonical_name, ec.entity_type, ec.description
                    FROM ranked r
                    JOIN {schema}.entity_canonical ec ON ec.id = r.canonical_entity_id
                    WHERE r.rn <= 3
                    """,
                    (storyline_ids,),
                )
                for r in cur.fetchall():
                    desc = r[3]
                    top_entities_by_storyline.setdefault(r[0], []).append(
                        {
                            "name": r[1] or "",
                            "type": r[2] or "subject",
                            "description_short": (desc[:100] + "…")
                            if desc and len(desc) > 100
                            else (desc or ""),
                        }
                    )
            for s in storyline_rows:
                s["top_entities"] = top_entities_by_storyline.get(s["id"], [])
                if "editorial_document" not in s or s["editorial_document"] is None:
                    s["editorial_document"] = None
            storylines = storyline_rows

        conn.close()
        return {
            "success": True,
            "data": {"articles": articles, "storylines": storylines},
            "message": None,
        }
    except Exception as e:
        logger.warning("briefing_feed failed: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "data": None, "message": str(e)}
