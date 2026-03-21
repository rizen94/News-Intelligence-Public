"""
Automated Daily Briefing Service for News Intelligence System
Generates scheduled daily intelligence reports with topic clouds and breaking news
Uses local processing only - no external AI services
"""

import logging
import os
from datetime import datetime, timedelta

from modules.deduplication.advanced_deduplication_service import get_deduplication_service
from shared.database.connection import get_db_connection

from .storyline_tracker import StorylineTracker

logger = logging.getLogger(__name__)

# Briefing uses this many days of collected data (rolling window from briefing_date backward)
BRIEFING_DAYS_WINDOW = 3


# Allowed schema names (from domains table) to avoid injection when formatting SQL
def _get_schema_for_domain(conn, domain: str | None) -> str | None:
    """Resolve schema_name from domain key. Returns None if domain is None or not found."""
    if not domain:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM domains WHERE domain_key = %s", (domain,))
            row = cur.fetchone()
            return row[0] if row else None
    except Exception as e:
        logger.warning("Could not resolve schema for domain %s: %s", domain, e)
        return None


class DailyBriefingService:
    """
    Service for generating automated daily intelligence briefings
    """

    def __init__(self, db_config: dict):
        """
        Initialize the daily briefing service

        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.storyline_tracker = StorylineTracker(db_config)
        self.deduplication_service = get_deduplication_service(db_config)

    def generate_daily_briefing(
        self,
        briefing_date: datetime | None = None,
        include_deduplication: bool = True,
        include_storylines: bool = True,
        days_window: int = BRIEFING_DAYS_WINDOW,
        domain: str | None = None,
    ) -> dict[str, any]:
        """
        Generate a comprehensive daily intelligence briefing from the past N days of data.

        Uses a rolling window (default 3 days). When domain is provided, queries that
        domain's schema (e.g. politics.articles); otherwise uses default schema.

        Args:
            briefing_date: End of window (defaults to now)
            include_deduplication: Whether to include deduplication stats
            include_storylines: Whether to include storyline analysis
            days_window: Number of days of data to include (default 3)
            domain: Domain key (e.g. politics, finance, science-tech) to scope articles to that schema

        Returns:
            Dictionary containing the daily briefing
        """
        try:
            briefing_date = briefing_date or datetime.now()
            start_date = briefing_date - timedelta(days=days_window)
            briefing_date_str = briefing_date.strftime("%Y-%m-%d")
            start_date_str = start_date.strftime("%Y-%m-%d")

            # Resolve domain schema so we query the correct articles table
            schema = None
            if domain:
                conn = get_db_connection()
                if conn:
                    try:
                        schema = _get_schema_for_domain(conn, domain)
                        if schema:
                            logger.info("Briefing using domain %s (schema %s)", domain, schema)
                    finally:
                        conn.close()

            articles_table = f"{schema}.articles" if schema else "articles"

            logger.info(
                f"Generating daily briefing for {briefing_date_str} (data window: {start_date_str} to {briefing_date_str}, {days_window} days)"
            )

            # Initialize briefing structure
            briefing = {
                "briefing_date": briefing_date_str,
                "start_date": start_date_str,
                "days_window": days_window,
                "domain": domain,
                "generated_at": datetime.now().isoformat(),
                "briefing_type": "daily_intelligence",
                "sections": {},
            }

            # Generate system overview (last N days)
            briefing["sections"]["system_overview"] = self._generate_system_overview(
                briefing_date, start_date, articles_table
            )

            # Generate content analysis (last N days)
            briefing["sections"]["content_analysis"] = self._generate_content_analysis(
                briefing_date, start_date, articles_table
            )

            # Generate topic cloud and breaking news (last N days)
            if include_storylines:
                briefing["sections"]["storyline_analysis"] = self._generate_storyline_analysis(
                    briefing_date, days_window, schema
                )

            # Generate deduplication report
            if include_deduplication:
                briefing["sections"]["deduplication_report"] = self._generate_deduplication_report()

            # Generate quality metrics (last N days)
            briefing["sections"]["quality_metrics"] = self._generate_quality_metrics(
                briefing_date, start_date, articles_table
            )

            # Editorial layer: key developments (headlines + storylines) for narrative, not just metrics
            if schema:
                require_quality = os.environ.get(
                    "BRIEFING_REQUIRE_QUALITY_TIER_1_2", ""
                ).lower() in ("1", "true", "yes")
                briefing["sections"]["key_developments"] = self._extract_key_developments(
                    start_date,
                    articles_table,
                    schema,
                    domain=domain,
                    require_quality_tier_1_2=require_quality,
                )

            # Generate recommendations
            briefing["sections"]["recommendations"] = self._generate_recommendations(briefing)

            # Calculate briefing statistics (uses window counts)
            briefing["statistics"] = self._calculate_briefing_statistics(briefing)

            logger.info(f"Daily briefing generated successfully for {briefing_date_str}")
            return briefing

        except Exception as e:
            logger.error(f"Error generating daily briefing: {e}")
            return {"error": str(e)}

    def _merge_daily_briefings(self, briefings: list[dict]) -> dict[str, any]:
        """Merge multiple domain briefings (same day) into one. Sums counts, combines lists. Skips briefings with error."""
        valid = [b for b in briefings if b and "error" not in b]
        if not valid:
            return {"error": "No valid domain briefings to merge", "sections": {}, "statistics": {}}
        if len(valid) == 1:
            return valid[0]

        base = valid[0].copy()
        so = base.get("sections", {}).get("system_overview", {})
        if "error" in so:
            so = {}
        for b in valid[1:]:
            o = b.get("sections", {}).get("system_overview", {})
            if "error" in o:
                continue
            so["total_articles"] = so.get("total_articles", 0) + o.get("total_articles", 0)
            so["today_new_articles"] = so.get("today_new_articles", 0) + o.get(
                "today_new_articles", 0
            )
            so["today_updated_articles"] = so.get("today_updated_articles", 0) + o.get(
                "today_updated_articles", 0
            )
            so["all_time_articles"] = so.get("all_time_articles", 0) + o.get("all_time_articles", 0)
            so["total_sources"] = so.get("total_sources", 0) + o.get("total_sources", 0)
        base.setdefault("sections", {})["system_overview"] = so

        # content_analysis: merge category_distribution
        cat_counts = {}
        total_analyzed = 0
        for b in valid:
            ca = b.get("sections", {}).get("content_analysis", {})
            if "error" in ca:
                continue
            total_analyzed += ca.get("total_articles_analyzed", 0)
            for c in ca.get("category_distribution", []):
                cat = c.get("category", "Other")
                cat_counts[cat] = cat_counts.get(cat, 0) + c.get("count", 0)
        if base.get("sections", {}).get("content_analysis", {}).get("error") != "error":
            base["sections"]["content_analysis"] = base.get("sections", {}).get(
                "content_analysis", {}
            )
            base["sections"]["content_analysis"]["total_articles_analyzed"] = total_analyzed
            base["sections"]["content_analysis"]["category_distribution"] = [
                {"category": k, "count": v, "avg_quality": 0.5}
                for k, v in sorted(cat_counts.items(), key=lambda x: -x[1])[:15]
            ]

        # key_developments: concatenate (dedupe by id)
        seen_ids = set()
        top_headlines = []
        top_storylines = []
        editorial_ledes = []
        event_briefings = []
        for b in valid:
            kd = b.get("sections", {}).get("key_developments", {})
            if "error" in kd:
                continue
            for h in kd.get("top_headlines", [])[:10]:
                hid = h.get("id") or h.get("title", "")
                if hid not in seen_ids:
                    seen_ids.add(hid)
                    top_headlines.append(h)
            for s in kd.get("top_storylines", [])[:10]:
                sid = s.get("id")
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    top_storylines.append(s)
            editorial_ledes.extend(kd.get("editorial_ledes", [])[:5])
            event_briefings.extend(kd.get("event_briefings", [])[:5])
        if "sections" in base and "key_developments" in base["sections"]:
            base["sections"]["key_developments"]["top_headlines"] = top_headlines[:20]
            base["sections"]["key_developments"]["top_storylines"] = top_storylines[:20]
            base["sections"]["key_developments"]["editorial_ledes"] = editorial_ledes[:15]
            base["sections"]["key_developments"]["event_briefings"] = event_briefings[:15]
            base["sections"]["key_developments"]["has_content"] = bool(
                top_headlines or top_storylines or editorial_ledes or event_briefings
            )

        # storyline_analysis: merge breaking_topics
        breaking = []
        for b in valid:
            sa = b.get("sections", {}).get("storyline_analysis", {})
            if "error" not in sa:
                breaking.extend(sa.get("breaking_topics", [])[:5])
        if base.get("sections", {}).get("storyline_analysis", {}).get("error") != "error":
            base.setdefault("sections", {})["storyline_analysis"] = base.get("sections", {}).get(
                "storyline_analysis", {}
            )
            base["sections"]["storyline_analysis"]["breaking_topics"] = breaking[:15]

        # statistics
        base["statistics"] = {
            "total_articles": sum(b.get("statistics", {}).get("total_articles", 0) for b in valid),
            "today_articles": sum(b.get("statistics", {}).get("today_articles", 0) for b in valid),
            "breaking_stories": sum(
                b.get("statistics", {}).get("breaking_stories", 0) for b in valid
            ),
            "categories_covered": sum(
                b.get("statistics", {}).get("categories_covered", 0) for b in valid
            ),
            "total_sections": base.get("statistics", {}).get("total_sections", 0),
            "sections_with_errors": base.get("statistics", {}).get("sections_with_errors", 0),
            "success_rate": base.get("statistics", {}).get("success_rate", 0),
        }
        base["domain"] = "all"
        return base

    def generate_weekly_briefing(self, week_start_date: datetime | None = None) -> dict[str, any]:
        """
        Generate a weekly intelligence briefing (single schema / legacy).
        Prefer generate_weekly_briefing_aggregate() so the digest uses all domains.
        """
        try:
            if week_start_date is None:
                today = datetime.now()
                days_since_monday = today.weekday()
                week_start_date = today - timedelta(days=days_since_monday)
            week_end_date = week_start_date + timedelta(days=6)
            logger.info(
                f"Generating weekly briefing for {week_start_date.strftime('%Y-%m-%d')} to {week_end_date.strftime('%Y-%m-%d')}"
            )
            daily_briefings = []
            current_date = week_start_date
            while current_date <= week_end_date:
                daily_briefing = self.generate_daily_briefing(
                    current_date, include_deduplication=False
                )
                if "error" not in daily_briefing:
                    daily_briefings.append(daily_briefing)
                current_date += timedelta(days=1)
            weekly_briefing = {
                "briefing_type": "weekly_intelligence",
                "week_start": week_start_date.strftime("%Y-%m-%d"),
                "week_end": week_end_date.strftime("%Y-%m-%d"),
                "generated_at": datetime.now().isoformat(),
                "daily_briefings": daily_briefings,
                "weekly_summary": self._generate_weekly_summary(daily_briefings),
                "trend_analysis": self._generate_trend_analysis(daily_briefings),
            }
            return weekly_briefing
        except Exception as e:
            logger.error(f"Error generating weekly briefing: {e}")
            return {"error": str(e)}

    def generate_weekly_briefing_aggregate(
        self, week_start_date: datetime | None = None
    ) -> dict[str, any]:
        """
        Generate a weekly briefing by aggregating daily briefings from all domains
        (politics, finance, science-tech). Use this for digest so data is not limited to public schema.
        """
        try:
            if week_start_date is None:
                today = datetime.now()
                days_since_monday = today.weekday()
                week_start_date = today - timedelta(days=days_since_monday)
            week_end_date = week_start_date + timedelta(days=6)
            logger.info(
                f"Generating weekly briefing (all domains) for {week_start_date.strftime('%Y-%m-%d')} to {week_end_date.strftime('%Y-%m-%d')}"
            )
            daily_briefings = []
            current_date = week_start_date
            while current_date <= week_end_date:
                per_domain = []
                for domain in ("politics", "finance", "science-tech"):
                    b = self.generate_daily_briefing(
                        current_date, include_deduplication=False, domain=domain
                    )
                    if b and "error" not in b:
                        per_domain.append(b)
                merged = self._merge_daily_briefings(per_domain)
                if "error" not in merged:
                    daily_briefings.append(merged)
                current_date += timedelta(days=1)
            weekly_briefing = {
                "briefing_type": "weekly_intelligence",
                "week_start": week_start_date.strftime("%Y-%m-%d"),
                "week_end": week_end_date.strftime("%Y-%m-%d"),
                "generated_at": datetime.now().isoformat(),
                "daily_briefings": daily_briefings,
                "weekly_summary": self._generate_weekly_summary(daily_briefings),
                "trend_analysis": self._generate_trend_analysis(daily_briefings),
            }
            return weekly_briefing
        except Exception as e:
            logger.error(f"Error generating weekly briefing (aggregate): {e}")
            return {"error": str(e)}

    def _generate_system_overview(
        self, briefing_date: datetime, start_date: datetime, articles_table: str = "articles"
    ) -> dict[str, any]:
        """Generate system overview section for the window [start_date, briefing_date]."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Window: articles created/updated in the last N days
            cursor.execute(
                f"SELECT COUNT(*) FROM {articles_table} WHERE created_at >= %s", (start_date,)
            )
            window_new = cursor.fetchone()[0]

            cursor.execute(
                f"SELECT COUNT(*) FROM {articles_table} WHERE updated_at >= %s", (start_date,)
            )
            window_updated = cursor.fetchone()[0]

            # Total in DB (for context)
            cursor.execute(f"SELECT COUNT(*) FROM {articles_table}")
            total_articles = cursor.fetchone()[0]

            # Distinct sources in window
            cursor.execute(
                f"SELECT COUNT(DISTINCT source) FROM {articles_table} WHERE source IS NOT NULL AND created_at >= %s",
                (start_date,),
            )
            window_sources = cursor.fetchone()[0]

            conn.close()

            return {
                "total_articles": window_new,  # briefing stats use this for "N articles"
                "today_new_articles": window_new,
                "today_updated_articles": window_updated,
                "total_sources": window_sources,
                "all_time_articles": total_articles,
                "system_status": "operational",
                "last_updated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating system overview: {e}")
            return {"error": str(e)}

    def _generate_content_analysis(
        self, briefing_date: datetime, start_date: datetime, articles_table: str = "articles"
    ) -> dict[str, any]:
        """Generate content analysis section for the window [start_date, briefing_date]."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT
                    category,
                    COUNT(*) as count,
                    AVG(COALESCE(quality_score, 0.5)) as avg_quality
                FROM {articles_table}
                WHERE created_at >= %s
                GROUP BY category
                ORDER BY count DESC
            """,
                (start_date,),
            )

            category_stats = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT
                    source,
                    COUNT(*) as count
                FROM {articles_table}
                WHERE created_at >= %s
                AND source IS NOT NULL
                GROUP BY source
                ORDER BY count DESC
                LIMIT 10
            """,
                (start_date,),
            )

            source_stats = cursor.fetchall()

            total_analyzed = sum(row[1] for row in category_stats)

            conn.close()

            return {
                "category_distribution": [
                    {
                        "category": row[0] or "uncategorized",
                        "count": row[1],
                        "avg_quality": round(float(row[2]), 3),
                    }
                    for row in category_stats
                ],
                "top_sources": [{"source": row[0], "count": row[1]} for row in source_stats],
                "total_articles_analyzed": total_analyzed,
                "analysis_date": briefing_date.strftime("%Y-%m-%d"),
                "start_date": start_date.strftime("%Y-%m-%d"),
            }

        except Exception as e:
            logger.error(f"Error generating content analysis: {e}")
            return {"error": str(e)}

    def _generate_storyline_analysis(
        self, briefing_date: datetime, days_window: int, schema: str | None = None
    ) -> dict[str, any]:
        """Generate storyline analysis section for the last days_window days."""
        try:
            topic_cloud = self.storyline_tracker.generate_topic_cloud(
                days=days_window, schema=schema
            )

            if "error" in topic_cloud:
                return {"error": topic_cloud["error"]}

            # Get breaking topics
            breaking_topics = topic_cloud.get("breaking_topics", [])

            # Get trending topics (top 5)
            top_topics = list(topic_cloud.get("topic_cloud", {}).get("top_topics", {}).items())[:5]

            return {
                "topic_cloud": {
                    "top_topics": dict(top_topics),
                    "categories": topic_cloud.get("topic_cloud", {}).get("categories", {}),
                    "sources": topic_cloud.get("topic_cloud", {}).get("sources", {}),
                },
                "breaking_topics": breaking_topics,
                "daily_summary": topic_cloud.get("daily_summary", ""),
                "article_count": topic_cloud.get("article_count", 0),
            }

        except Exception as e:
            logger.error(f"Error generating storyline analysis: {e}")
            return {"error": str(e)}

    def _generate_deduplication_report(self) -> dict[str, any]:
        """Generate deduplication report section"""
        try:
            dedup_stats = self.deduplication_service.get_deduplication_stats()

            if "error" in dedup_stats:
                return {"error": dedup_stats["error"]}

            # Get recent duplicate detection (async method, but we'll skip for now in sync context)
            # Note: detect_duplicates is async, but this method is sync
            # For now, just use stats
            recent_detection = {
                "duplicates_found": 0,
                "message": "Async detection skipped in sync context",
            }

            return {
                "statistics": dedup_stats,
                "recent_detection": recent_detection if "error" not in recent_detection else {},
                "recommendations": self._generate_deduplication_recommendations(dedup_stats),
            }

        except Exception as e:
            logger.error(f"Error generating deduplication report: {e}")
            return {"error": str(e)}

    def _generate_quality_metrics(
        self, briefing_date: datetime, start_date: datetime, articles_table: str = "articles"
    ) -> dict[str, any]:
        """Generate quality metrics section for the window [start_date, briefing_date]."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT
                    CASE
                        WHEN COALESCE(quality_score, 0.5) >= 0.8 THEN 'high'
                        WHEN COALESCE(quality_score, 0.5) >= 0.6 THEN 'medium'
                        ELSE 'low'
                    END as quality_level,
                    COUNT(*) as count
                FROM {articles_table}
                WHERE created_at >= %s
                GROUP BY quality_level
                ORDER BY quality_level DESC
            """,
                (start_date,),
            )

            quality_distribution = cursor.fetchall()

            cursor.execute(
                f"""
                SELECT
                    category,
                    AVG(COALESCE(quality_score, 0.5)) as avg_quality,
                    COUNT(*) as count
                FROM {articles_table}
                WHERE created_at >= %s
                GROUP BY category
                HAVING COUNT(*) >= 3
                ORDER BY avg_quality DESC
            """,
                (start_date,),
            )

            category_quality = cursor.fetchall()

            conn.close()

            return {
                "quality_distribution": [
                    {"level": row[0], "count": row[1]} for row in quality_distribution
                ],
                "category_quality": [
                    {
                        "category": row[0] or "uncategorized",
                        "avg_quality": round(float(row[1]), 3),
                        "count": row[2],
                    }
                    for row in category_quality
                ],
                "overall_quality_score": self._calculate_overall_quality(quality_distribution),
            }

        except Exception as e:
            logger.error(f"Error generating quality metrics: {e}")
            return {"error": str(e)}

    def _extract_key_developments(
        self,
        start_date: datetime,
        articles_table: str,
        schema: str,
        domain: str | None = None,
        require_quality_tier_1_2: bool = False,
    ) -> dict[str, any]:
        """Extract editorial narratives, headlines, and storyline titles for briefings. Uses editorial_document when available. Applies user feedback and low-priority (sports/celebrity) demotion. When require_quality_tier_1_2 is True, only tier 1–2 articles are used for headlines (fewer items OK)."""
        try:
            conn = get_db_connection()
            if not conn:
                return {
                    "top_headlines": [],
                    "top_storylines": [],
                    "editorial_ledes": [],
                    "event_briefings": [],
                    "error": "No connection",
                }
            cursor = conn.cursor()
            top_headlines = []
            top_storylines = []
            editorial_ledes = []
            event_briefings = []

            # Top headlines: prefer quality_tier 1–2 (intelligence-grade/standard), then quality_score; optionally require tier <= 2
            headline_where = "created_at >= %s AND title IS NOT NULL AND TRIM(title) != ''"
            headline_params: list = [start_date]
            if require_quality_tier_1_2:
                headline_where += " AND COALESCE(quality_tier, 4) <= 2"
            try:
                cursor.execute(
                    f"""
                    SELECT id, title, source_domain, summary
                    FROM {articles_table}
                    WHERE {headline_where}
                    ORDER BY COALESCE(quality_tier, 4) ASC, COALESCE(quality_score, 0) DESC, created_at DESC
                    LIMIT 15
                    """,
                    tuple(headline_params),
                )
                for row in cursor.fetchall():
                    top_headlines.append(
                        {
                            "id": row[0],
                            "title": (row[1] or "").strip(),
                            "source": (row[2] or "").strip(),
                            "summary": (row[3] or "").strip() if len(row) > 3 else "",
                        }
                    )
            except Exception as e:
                logger.debug("key_developments headlines: %s", e)

            # Storylines: prefer those with recent article activity (last article published in window)
            # Order by last_article_at DESC so "what's happening now" appears first; fallback to updated_at
            storylines_table = f"{schema}.storylines"
            articles_table_schema = f"{schema}.articles"
            sa_table = f"{schema}.storyline_articles"
            try:
                cursor.execute(
                    f"""
                    SELECT s.id, s.title,
                           COALESCE(s.total_articles, s.article_count, 0),
                           s.updated_at,
                           s.editorial_document, s.document_status,
                           (SELECT MAX(a.published_at) FROM {sa_table} sa2
                            JOIN {articles_table_schema} a ON a.id = sa2.article_id
                            WHERE sa2.storyline_id = s.id AND a.published_at >= %s) AS last_article_at
                    FROM {storylines_table} s
                    WHERE s.updated_at >= %s AND s.title IS NOT NULL AND TRIM(s.title) != ''
                    ORDER BY last_article_at DESC NULLS LAST, s.updated_at DESC
                    LIMIT 10
                    """,
                    (start_date, start_date),
                )
                for row in cursor.fetchall():
                    sid = row[0]
                    stitle = (row[1] or "").strip()
                    ed = row[4] if len(row) > 4 else None
                    last_article_at = row[6] if len(row) > 6 else None
                    recency_24h = False
                    if last_article_at:
                        try:
                            from datetime import timezone

                            now = datetime.now(timezone.utc)
                            dt = (
                                last_article_at.astimezone(timezone.utc)
                                if getattr(last_article_at, "tzinfo", None)
                                else last_article_at
                            )
                            recency_24h = (now - dt).total_seconds() < 86400  # 24h
                        except Exception:
                            pass
                    top_storylines.append(
                        {
                            "id": sid,
                            "title": stitle,
                            "article_count": int(row[2]) if row[2] is not None else 0,
                            "updated_at": row[3].isoformat()
                            if hasattr(row[3], "isoformat")
                            else str(row[3])
                            if row[3]
                            else None,
                            "document_status": row[5] if len(row) > 5 else None,
                            "last_article_at": last_article_at.isoformat()
                            if hasattr(last_article_at, "isoformat")
                            else str(last_article_at)
                            if last_article_at
                            else None,
                            "recent": bool(recency_24h),
                        }
                    )
                    # Extract lede from editorial_document if present
                    if ed and isinstance(ed, dict) and ed.get("lede"):
                        editorial_ledes.append(
                            {
                                "storyline_id": sid,
                                "title": stitle,
                                "lede": ed["lede"],
                                "recent": bool(recency_24h),
                            }
                        )
            except Exception as e:
                logger.debug("key_developments storylines: %s", e)
                # Fallback without last_article_at
                try:
                    cursor.execute(
                        f"""
                        SELECT id, title,
                               COALESCE(total_articles, article_count, 0),
                               updated_at,
                               editorial_document, document_status
                        FROM {storylines_table}
                        WHERE updated_at >= %s AND title IS NOT NULL AND TRIM(title) != ''
                        ORDER BY updated_at DESC
                        LIMIT 8
                        """,
                        (start_date,),
                    )
                    for row in cursor.fetchall():
                        sid, stitle = row[0], (row[1] or "").strip()
                        ed = row[4] if len(row) > 4 else None
                        top_storylines.append(
                            {
                                "id": sid,
                                "title": stitle,
                                "article_count": int(row[2]) if row[2] is not None else 0,
                                "updated_at": row[3].isoformat()
                                if hasattr(row[3], "isoformat")
                                else str(row[3])
                                if row[3]
                                else None,
                                "document_status": row[5] if len(row) > 5 else None,
                                "last_article_at": None,
                                "recent": False,
                            }
                        )
                        if ed and isinstance(ed, dict) and ed.get("lede"):
                            editorial_ledes.append(
                                {
                                    "storyline_id": sid,
                                    "title": stitle,
                                    "lede": ed["lede"],
                                    "recent": False,
                                }
                            )
                except Exception as e2:
                    logger.debug("key_developments storylines fallback: %s", e2)

            # Event briefings from tracked_events: prefer domain-scoped and recently updated
            try:
                event_params = [start_date]
                domain_filter = ""
                if domain:
                    domain_filter = (
                        " AND (domain_keys IS NULL OR domain_keys = '{}' OR %s = ANY(domain_keys))"
                    )
                    event_params.append(domain)
                cursor.execute(
                    """
                    SELECT id, event_name, editorial_briefing, editorial_briefing_json, updated_at
                    FROM intelligence.tracked_events
                    WHERE updated_at >= %s
                      AND editorial_briefing IS NOT NULL
                    """
                    + domain_filter
                    + """
                    ORDER BY updated_at DESC
                    LIMIT 8
                    """,
                    tuple(event_params),
                )
                rows = cursor.fetchall()
            except Exception as e:
                logger.debug("key_developments events (with domain filter): %s", e)
                rows = []
                try:
                    cursor.execute(
                        """
                        SELECT id, event_name, editorial_briefing, editorial_briefing_json, updated_at
                        FROM intelligence.tracked_events
                        WHERE updated_at >= %s AND editorial_briefing IS NOT NULL
                        ORDER BY updated_at DESC
                        LIMIT 8
                        """,
                        (start_date,),
                    )
                    rows = cursor.fetchall()
                except Exception as e2:
                    logger.debug("key_developments events fallback: %s", e2)
            for row in rows:
                eid, ename, briefing_text, briefing_json = row[0], row[1], row[2], row[3]
                ev_updated = row[4] if len(row) > 4 else None
                headline = ""
                if briefing_json and isinstance(briefing_json, dict):
                    headline = briefing_json.get("headline", "")
                event_briefings.append(
                    {
                        "event_id": eid,
                        "event_name": (ename or "").strip(),
                        "headline": headline,
                        "briefing_excerpt": (briefing_text or "")[:200],
                        "updated_at": ev_updated.isoformat()
                        if hasattr(ev_updated, "isoformat")
                        else str(ev_updated)
                        if ev_updated
                        else None,
                    }
                )

            conn.close()

            # Apply user feedback (exclude not_interested) and low-priority demotion (sports/celebrity)
            if domain:
                try:
                    from services.briefing_filter_helper import sort_briefing_items_by_priority
                    from services.content_feedback_service import get_not_interested_ids

                    not_art = get_not_interested_ids(domain, "article")
                    not_story = get_not_interested_ids(domain, "storyline")
                    top_headlines = [h for h in top_headlines if h.get("id") not in not_art]
                    top_storylines = [s for s in top_storylines if s.get("id") not in not_story]
                    editorial_ledes = [
                        e for e in editorial_ledes if e.get("storyline_id") not in not_story
                    ]
                    top_headlines = sort_briefing_items_by_priority(
                        top_headlines, title_key="title", summary_key="summary"
                    )
                    top_storylines = sort_briefing_items_by_priority(
                        top_storylines, title_key="title"
                    )
                    editorial_ledes = sort_briefing_items_by_priority(
                        editorial_ledes, title_key="title", lede_key="lede"
                    )
                except Exception as e:
                    logger.debug("Briefing filter/feedback apply: %s", e)

            has_content = (
                len(top_headlines) > 0
                or len(top_storylines) > 0
                or len(editorial_ledes) > 0
                or len(event_briefings) > 0
            )
            return {
                "top_headlines": top_headlines[:10],
                "top_storylines": top_storylines,
                "editorial_ledes": editorial_ledes,
                "event_briefings": event_briefings,
                "has_content": has_content,
            }
        except Exception as e:
            logger.error("Error extracting key developments: %s", e)
            return {
                "top_headlines": [],
                "top_storylines": [],
                "editorial_ledes": [],
                "event_briefings": [],
                "has_content": False,
                "error": str(e),
            }

    def _generate_recommendations(self, briefing: dict) -> dict[str, any]:
        """Generate recommendations based on briefing data"""
        try:
            recommendations = {
                "content_quality": [],
                "system_optimization": [],
                "story_monitoring": [],
                "priority_actions": [],
            }

            # Content quality recommendations
            content_analysis = briefing.get("sections", {}).get("content_analysis", {})
            if "error" not in content_analysis:
                category_dist = content_analysis.get("category_distribution", [])
                for cat in category_dist:
                    if cat["avg_quality"] < 0.6:
                        recommendations["content_quality"].append(
                            f"Improve content quality for {cat['category']} category (current: {cat['avg_quality']})"
                        )

            # System optimization recommendations
            system_overview = briefing.get("sections", {}).get("system_overview", {})
            if "error" not in system_overview:
                if system_overview.get("today_new_articles", 0) < 10:
                    recommendations["system_optimization"].append(
                        "Low article volume today - check RSS feeds and content sources"
                    )

            # Story monitoring recommendations
            storyline_analysis = briefing.get("sections", {}).get("storyline_analysis", {})
            if "error" not in storyline_analysis:
                breaking_count = len(storyline_analysis.get("breaking_topics", []))
                if breaking_count > 5:
                    recommendations["story_monitoring"].append(
                        f"High number of breaking stories ({breaking_count}) - prioritize review"
                    )
                elif breaking_count == 0:
                    recommendations["story_monitoring"].append(
                        "No breaking stories detected - verify monitoring systems"
                    )

            # Priority actions
            if recommendations["content_quality"]:
                recommendations["priority_actions"].append(
                    "Review and improve low-quality content sources"
                )
            if recommendations["story_monitoring"]:
                recommendations["priority_actions"].append(
                    "Monitor breaking stories and emerging trends"
                )

            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return {"error": str(e)}

    def _calculate_briefing_statistics(self, briefing: dict) -> dict[str, any]:
        """Calculate overall briefing statistics"""
        try:
            sections = briefing.get("sections", {})

            # Count sections with errors
            error_count = sum(1 for section in sections.values() if "error" in section)
            total_sections = len(sections)

            # Get key metrics
            system_overview = sections.get("system_overview", {})
            content_analysis = sections.get("content_analysis", {})
            storyline_analysis = sections.get("storyline_analysis", {})

            stats = {
                "total_sections": total_sections,
                "sections_with_errors": error_count,
                "success_rate": round(((total_sections - error_count) / total_sections) * 100, 1)
                if total_sections > 0
                else 0,
                "total_articles": system_overview.get("total_articles", 0)
                if "error" not in system_overview
                else 0,
                "today_articles": system_overview.get("today_new_articles", 0)
                if "error" not in system_overview
                else 0,
                "breaking_stories": len(storyline_analysis.get("breaking_topics", []))
                if "error" not in storyline_analysis
                else 0,
                "categories_covered": len(content_analysis.get("category_distribution", []))
                if "error" not in content_analysis
                else 0,
            }

            return stats

        except Exception as e:
            logger.error(f"Error calculating briefing statistics: {e}")
            return {"error": str(e)}

    def _generate_weekly_summary(self, daily_briefings: list[dict]) -> dict[str, any]:
        """Generate weekly summary from daily briefings"""
        try:
            if not daily_briefings:
                return {"error": "No daily briefings available"}

            # Aggregate weekly statistics
            total_articles = sum(
                b.get("statistics", {}).get("total_articles", 0) for b in daily_briefings
            )
            total_breaking = sum(
                b.get("statistics", {}).get("breaking_stories", 0) for b in daily_briefings
            )

            # Get top categories for the week
            category_counts = {}
            for briefing in daily_briefings:
                content_analysis = briefing.get("sections", {}).get("content_analysis", {})
                if "error" not in content_analysis:
                    for cat in content_analysis.get("category_distribution", []):
                        category = cat["category"]
                        category_counts[category] = category_counts.get(category, 0) + cat["count"]

            top_categories = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)[:5]

            return {
                "total_articles": total_articles,
                "total_breaking_stories": total_breaking,
                "top_categories": dict(top_categories),
                "days_analyzed": len(daily_briefings),
                "average_articles_per_day": round(total_articles / len(daily_briefings), 1)
                if daily_briefings
                else 0,
            }

        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")
            return {"error": str(e)}

    def _generate_trend_analysis(self, daily_briefings: list[dict]) -> dict[str, any]:
        """Generate trend analysis from daily briefings"""
        try:
            if len(daily_briefings) < 2:
                return {"error": "Insufficient data for trend analysis"}

            # Analyze trends over the week
            article_trends = []
            quality_trends = []

            for briefing in daily_briefings:
                date = briefing.get("briefing_date", "unknown")
                stats = briefing.get("statistics", {})
                content_analysis = briefing.get("sections", {}).get("content_analysis", {})

                article_trends.append(
                    {
                        "date": date,
                        "articles": stats.get("total_articles", 0),
                        "breaking": stats.get("breaking_stories", 0),
                    }
                )

                if "error" not in content_analysis:
                    avg_quality = sum(
                        cat["avg_quality"]
                        for cat in content_analysis.get("category_distribution", [])
                    )
                    cat_count = len(content_analysis.get("category_distribution", []))
                    if cat_count > 0:
                        quality_trends.append(
                            {"date": date, "avg_quality": round(avg_quality / cat_count, 3)}
                        )

            return {
                "article_trends": article_trends,
                "quality_trends": quality_trends,
                "trend_analysis": self._analyze_trends(article_trends, quality_trends),
            }

        except Exception as e:
            logger.error(f"Error generating trend analysis: {e}")
            return {"error": str(e)}

    def _analyze_trends(
        self, article_trends: list[dict], quality_trends: list[dict]
    ) -> dict[str, any]:
        """Analyze trends in the data"""
        try:
            if not article_trends or not quality_trends:
                return {"error": "Insufficient trend data"}

            # Article volume trend
            article_counts = [t["articles"] for t in article_trends]
            article_trend = (
                "increasing"
                if article_counts[-1] > article_counts[0]
                else "decreasing"
                if article_counts[-1] < article_counts[0]
                else "stable"
            )

            # Quality trend
            quality_scores = [t["avg_quality"] for t in quality_trends]
            quality_trend = (
                "improving"
                if quality_scores[-1] > quality_scores[0]
                else "declining"
                if quality_scores[-1] < quality_scores[0]
                else "stable"
            )

            return {
                "article_volume_trend": article_trend,
                "quality_trend": quality_trend,
                "recommendations": self._generate_trend_recommendations(
                    article_trend, quality_trend
                ),
            }

        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {"error": str(e)}

    def _generate_trend_recommendations(self, article_trend: str, quality_trend: str) -> list[str]:
        """Generate recommendations based on trends"""
        recommendations = []

        if article_trend == "decreasing":
            recommendations.append(
                "Article volume is decreasing - investigate content sources and RSS feeds"
            )
        elif article_trend == "increasing":
            recommendations.append("Article volume is increasing - monitor for quality maintenance")

        if quality_trend == "declining":
            recommendations.append(
                "Content quality is declining - review content sources and filtering"
            )
        elif quality_trend == "improving":
            recommendations.append(
                "Content quality is improving - maintain current content strategies"
            )

        return recommendations

    def _generate_deduplication_recommendations(self, dedup_stats: dict) -> list[str]:
        """Generate deduplication recommendations"""
        recommendations = []

        dedup_rate = dedup_stats.get("deduplication_rate", 0)
        total_articles = dedup_stats.get("total_articles", 0)

        if dedup_rate > 20:
            recommendations.append(
                "High duplicate rate detected - consider adjusting similarity thresholds"
            )
        elif dedup_rate < 5:
            recommendations.append("Low duplicate rate - current deduplication is effective")

        if total_articles > 1000:
            recommendations.append(
                "Large article database - consider batch deduplication processing"
            )

        return recommendations

    def _calculate_overall_quality(self, quality_distribution: list) -> float:
        """Calculate overall quality score"""
        try:
            if not quality_distribution:
                return 0.0

            total_articles = sum(row[1] for row in quality_distribution)
            if total_articles == 0:
                return 0.0

            # Weighted quality score
            quality_scores = {"high": 0.9, "medium": 0.7, "low": 0.3}

            weighted_sum = sum(
                quality_scores.get(row[0], 0.5) * row[1] for row in quality_distribution
            )
            return round(weighted_sum / total_articles, 3)

        except Exception as e:
            logger.error(f"Error calculating overall quality: {e}")
            return 0.0
