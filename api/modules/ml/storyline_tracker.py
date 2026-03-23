"""
Storyline Tracker for News Intelligence System
Manages story evolution, topic clustering, and dossier generation
Uses local processing only - no external AI services
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from shared.database.connection import get_ephemeral_db_connection_context

logger = logging.getLogger(__name__)


class StorylineTracker:
    """
    Tracks story evolution and generates comprehensive dossiers
    """

    def __init__(self, db_config: dict):
        """
        Initialize the Storyline Tracker

        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.topic_weights = {"breaking": 1.0, "developing": 0.8, "ongoing": 0.6, "resolved": 0.3}

    def generate_topic_cloud(self, days: int = 1, schema: str | None = None) -> dict[str, any]:
        """
        Generate a topic cloud/summary of breaking issues and topics.

        Args:
            days: Number of days to analyze (default: 1 for daily briefing)
            schema: Optional schema name (e.g. politics, finance) to query that domain's articles table

        Returns:
            Dictionary containing topic cloud and breaking news summary
        """
        try:
            with get_ephemeral_db_connection_context() as conn:
                cursor = conn.cursor()

                articles_from = f"{schema}.articles" if schema else "articles"
                cutoff_date = datetime.now() - timedelta(days=days)
                cursor.execute(
                    f"""
                    SELECT id, title, content, summary, category, source, published_at,
                           metadata AS ml_data, quality_score, created_at
                    FROM {articles_from}
                    WHERE created_at >= %s
                    AND metadata->>'summary' IS NOT NULL AND metadata->>'summary' <> ''
                    AND quality_score >= 0.3
                    ORDER BY published_at DESC, quality_score DESC
                """,
                    (cutoff_date,),
                )

                articles = cursor.fetchall()

            if not articles:
                return {
                    "topic_cloud": {},
                    "breaking_topics": [],
                    "daily_summary": "No significant articles found for the specified period.",
                    "article_count": 0,
                    "generated_at": datetime.now().isoformat(),
                }

            # Analyze topics and generate cloud
            topic_analysis = self._analyze_topics(articles)
            breaking_topics = self._identify_breaking_topics(articles, topic_analysis)
            daily_summary = self._generate_daily_summary(articles, breaking_topics)

            return {
                "topic_cloud": topic_analysis,
                "breaking_topics": breaking_topics,
                "daily_summary": daily_summary,
                "article_count": len(articles),
                "time_period": f"Last {days} day(s)",
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating topic cloud: {e}")
            return {"error": str(e)}

    def create_story_dossier(self, story_id: str, include_rag: bool = True) -> dict[str, any]:
        """
        Create a comprehensive dossier for a specific story/topic

        Args:
            story_id: Identifier for the story (can be topic, keyword, or cluster ID)
            include_rag: Whether to include RAG-enhanced analysis

        Returns:
            Dictionary containing comprehensive story dossier
        """
        try:
            with get_ephemeral_db_connection_context() as conn:
                cursor = conn.cursor()

                # Get all articles related to this story
                cursor.execute(
                    """
                    SELECT id, title, content, summary, category, source, published_at,
                           metadata AS ml_data, quality_score, created_at
                    FROM articles
                    WHERE (
                        LOWER(title) LIKE LOWER(%s) OR
                        LOWER(content) LIKE LOWER(%s) OR
                        LOWER(summary) LIKE LOWER(%s) OR
                        category = %s
                    )
                    AND metadata->>'summary' IS NOT NULL AND metadata->>'summary' <> ''
                    AND quality_score >= 0.4
                    ORDER BY published_at DESC, quality_score DESC
                """,
                    (f"%{story_id}%", f"%{story_id}%", f"%{story_id}%", story_id),
                )

                articles = cursor.fetchall()

            if not articles:
                return {
                    "story_id": story_id,
                    "dossier": "No articles found for this story.",
                    "article_count": 0,
                    "generated_at": datetime.now().isoformat(),
                }

            # Generate comprehensive dossier
            dossier = self._generate_comprehensive_dossier(articles, story_id, include_rag)

            return {
                "story_id": story_id,
                "dossier": dossier,
                "article_count": len(articles),
                "time_span": self._calculate_time_span(articles),
                "sources": self._extract_sources(articles),
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error creating story dossier: {e}")
            return {"error": str(e)}

    def track_story_evolution(self, story_id: str, days: int = 7) -> dict[str, any]:
        """
        Track how a story has evolved over time

        Args:
            story_id: Identifier for the story
            days: Number of days to track back

        Returns:
            Dictionary containing story evolution timeline
        """
        try:
            with get_ephemeral_db_connection_context() as conn:
                cursor = conn.cursor()

                cutoff_date = datetime.now() - timedelta(days=days)
                cursor.execute(
                    """
                    SELECT id, title, content, summary, source, published_at,
                           metadata AS ml_data, quality_score
                    FROM articles
                    WHERE (
                        LOWER(title) LIKE LOWER(%s) OR
                        LOWER(content) LIKE LOWER(%s) OR
                        LOWER(summary) LIKE LOWER(%s)
                    )
                    AND published_at >= %s
                    AND metadata->>'summary' IS NOT NULL AND metadata->>'summary' <> ''
                    ORDER BY published_at ASC
                """,
                    (f"%{story_id}%", f"%{story_id}%", f"%{story_id}%", cutoff_date),
                )

                articles = cursor.fetchall()

            if not articles:
                return {
                    "story_id": story_id,
                    "evolution": "No articles found for this story in the specified period.",
                    "timeline": [],
                    "generated_at": datetime.now().isoformat(),
                }

            # Create evolution timeline
            timeline = self._create_evolution_timeline(articles)
            evolution_summary = self._summarize_evolution(articles, timeline)

            return {
                "story_id": story_id,
                "evolution_summary": evolution_summary,
                "timeline": timeline,
                "article_count": len(articles),
                "time_span": f"{days} days",
                "generated_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error tracking story evolution: {e}")
            return {"error": str(e)}

    def _analyze_topics(self, articles: list) -> dict[str, any]:
        """Analyze topics from articles using content and ML data when available."""
        try:
            topic_frequency = Counter()
            category_frequency = Counter()
            source_frequency = Counter()
            quality_scores = defaultdict(list)
            key_points_collected = []

            for article in articles:
                title = article[1] or ""
                content = article[2] or ""
                summary = article[3] or ""
                category = article[4] or "general"
                source = article[5] or "unknown"
                ml_data = article[7] if len(article) > 7 else None
                quality_score = article[8] or 0.0

                # Use ML key_points if available; otherwise fall back to title+content word extraction
                if ml_data and isinstance(ml_data, dict):
                    ml_summary = ml_data.get("summary", "")
                    for kp in ml_data.get("key_points") or []:
                        if isinstance(kp, str) and kp.strip():
                            key_points_collected.append(kp.strip())
                            words = kp.lower().split()
                            for word in words:
                                if len(word) > 3:
                                    topic_frequency[word] += 1
                    if ml_summary:
                        for word in ml_summary.lower().split():
                            if len(word) > 3:
                                topic_frequency[word] += 1

                # Always extract from title + content body (not just summary)
                text_to_analyze = title + " " + (summary or content[:500])
                stop_words = {
                    "the",
                    "a",
                    "an",
                    "and",
                    "or",
                    "but",
                    "in",
                    "on",
                    "at",
                    "to",
                    "for",
                    "of",
                    "with",
                    "by",
                    "is",
                    "are",
                    "was",
                    "were",
                    "be",
                    "been",
                    "have",
                    "has",
                    "had",
                    "do",
                    "does",
                    "did",
                    "will",
                    "would",
                    "could",
                    "should",
                    "may",
                    "might",
                    "can",
                    "this",
                    "that",
                    "these",
                    "those",
                    "i",
                    "you",
                    "he",
                    "she",
                    "it",
                    "we",
                    "they",
                    "news",
                    "report",
                    "says",
                    "said",
                    "also",
                    "more",
                    "than",
                    "from",
                    "about",
                    "into",
                    "over",
                    "after",
                    "before",
                    "between",
                    "under",
                    "there",
                    "their",
                    "them",
                    "then",
                    "when",
                    "what",
                    "which",
                    "who",
                    "how",
                    "where",
                    "just",
                    "like",
                    "been",
                    "being",
                    "other",
                    "some",
                    "most",
                    "only",
                    "very",
                    "much",
                    "many",
                }

                words = text_to_analyze.lower().split()
                for word in words:
                    cleaned = word.strip(".,!?;:()[]\"'")
                    if len(cleaned) > 3 and cleaned not in stop_words:
                        topic_frequency[cleaned] += 1

                category_frequency[category] += 1
                source_frequency[source] += 1
                quality_scores[category].append(quality_score)

            avg_quality = {cat: sum(scores) / len(scores) for cat, scores in quality_scores.items()}

            return {
                "top_topics": dict(topic_frequency.most_common(20)),
                "categories": dict(category_frequency.most_common(10)),
                "sources": dict(source_frequency.most_common(10)),
                "average_quality": avg_quality,
                "total_articles": len(articles),
                "key_points": key_points_collected[:15],
            }

        except Exception as e:
            logger.error(f"Error analyzing topics: {e}")
            return {}

    def _identify_breaking_topics(self, articles: list, topic_analysis: dict) -> list[dict]:
        """Identify breaking/trending topics"""
        try:
            breaking_topics = []

            # Get recent articles (last 6 hours)
            recent_cutoff = datetime.now() - timedelta(hours=6)

            for article in articles:
                published_at = article[6]
                if published_at and published_at >= recent_cutoff:
                    quality_score = article[8] or 0.0
                    if quality_score >= 0.5:  # High quality threshold for breaking news
                        breaking_topics.append(
                            {
                                "title": article[1],
                                "summary": article[3],
                                "source": article[5],
                                "published_at": published_at.isoformat() if published_at else None,
                                "quality_score": quality_score,
                                "urgency": "high" if quality_score >= 0.7 else "medium",
                            }
                        )

            # Sort by quality score and recency
            breaking_topics.sort(
                key=lambda x: (x["quality_score"], x["published_at"]), reverse=True
            )

            return breaking_topics[:10]  # Top 10 breaking topics

        except Exception as e:
            logger.error(f"Error identifying breaking topics: {e}")
            return []

    def _generate_daily_summary(self, articles: list, breaking_topics: list) -> str:
        """Generate a daily summary incorporating article content and breaking story details."""
        try:
            if not articles:
                return "No significant news activity today."

            total_articles = len(articles)
            breaking_count = len(breaking_topics)

            categories = Counter(article[4] or "general" for article in articles)
            top_category = categories.most_common(1)[0][0] if categories else "general"

            parts = []
            parts.append(f"Today's coverage: {total_articles} articles, led by {top_category}.")

            # Lead with breaking story titles if available
            if breaking_count > 0 and breaking_topics:
                top_breaking = [
                    bt.get("title", "") for bt in breaking_topics[:3] if bt.get("title")
                ]
                if top_breaking:
                    parts.append(f"Breaking: {'; '.join(top_breaking)}.")
                else:
                    parts.append(f"{breaking_count} breaking stories identified.")

            # Surface top headlines from highest-quality articles
            top_articles = sorted(articles, key=lambda a: a[8] or 0.0, reverse=True)[:3]
            top_titles = [a[1] for a in top_articles if a[1]]
            if top_titles:
                parts.append(f"Top stories: {'; '.join(top_titles)}.")

            return " ".join(parts)

        except Exception as e:
            logger.error(f"Error generating daily summary: {e}")
            return "Error generating daily summary."

    def _generate_comprehensive_dossier(
        self, articles: list, story_id: str, include_rag: bool
    ) -> str:
        """Generate comprehensive dossier for a story"""
        try:
            if not articles:
                return "No articles available for dossier generation."

            # Sort articles by date and quality
            articles.sort(key=lambda x: (x[6] or datetime.min, x[8] or 0.0), reverse=True)

            dossier = f"# COMPREHENSIVE DOSSIER: {story_id.upper()}\n\n"
            dossier += f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            dossier += f"**Article Count**: {len(articles)}\n"
            dossier += f"**Time Span**: {self._calculate_time_span(articles)}\n\n"

            # Executive Summary — use ML summary or content excerpt from best article
            dossier += "## EXECUTIVE SUMMARY\n\n"
            if articles:
                best_article = max(articles, key=lambda x: x[8] or 0.0)
                ml_data = best_article[7] if len(best_article) > 7 else None
                if ml_data and isinstance(ml_data, dict) and ml_data.get("summary"):
                    dossier += f"{ml_data['summary']}\n\n"
                elif best_article[3]:
                    dossier += f"{best_article[3]}\n\n"
                elif best_article[2]:
                    dossier += f"{best_article[2][:500]}\n\n"
                else:
                    dossier += "No summary available.\n\n"

            # Timeline of Events — include content excerpts
            dossier += "## TIMELINE OF EVENTS\n\n"
            for i, article in enumerate(articles[:10], 1):
                published_at = article[6]
                date_str = published_at.strftime("%Y-%m-%d") if published_at else "Unknown date"
                dossier += f"**{i}. {date_str}** - {article[1]}\n"
                dossier += f"   Source: {article[5]}\n"
                # Include a content excerpt
                summary = article[3] or ""
                content = article[2] or ""
                excerpt = summary or content[:300]
                if excerpt:
                    dossier += f"   {excerpt[:300]}\n\n"
                else:
                    dossier += "\n"

            # Key Sources
            dossier += "## KEY SOURCES\n\n"
            sources = Counter(article[5] for article in articles if article[5])
            for source, count in sources.most_common(5):
                dossier += f"- **{source}**: {count} articles\n"
            dossier += "\n"

            # Quality Analysis
            dossier += "## QUALITY ANALYSIS\n\n"
            quality_scores = [article[8] or 0.0 for article in articles]
            avg_quality = sum(quality_scores) / len(quality_scores)
            high_quality_count = sum(1 for score in quality_scores if score >= 0.7)

            dossier += f"- **Average Quality Score**: {avg_quality:.2f}\n"
            dossier += f"- **High Quality Articles** (≥0.7): {high_quality_count}/{len(articles)}\n"
            dossier += f"- **Quality Distribution**: {self._analyze_quality_distribution(quality_scores)}\n\n"

            # Recommendations
            dossier += "## RECOMMENDATIONS\n\n"
            if avg_quality >= 0.7:
                dossier += "- **High Confidence**: Story has high-quality coverage across multiple sources\n"
            elif avg_quality >= 0.5:
                dossier += (
                    "- **Medium Confidence**: Story has adequate coverage, monitor for updates\n"
                )
            else:
                dossier += (
                    "- **Low Confidence**: Limited quality coverage, seek additional sources\n"
                )

            if len(articles) >= 10:
                dossier += (
                    "- **Comprehensive Coverage**: Sufficient articles for thorough analysis\n"
                )
            else:
                dossier += "- **Limited Coverage**: Consider monitoring for additional articles\n"

            return dossier

        except Exception as e:
            logger.error(f"Error generating dossier: {e}")
            return f"Error generating dossier: {str(e)}"

    def _create_evolution_timeline(self, articles: list) -> list[dict]:
        """Create timeline of story evolution"""
        try:
            timeline = []

            for article in articles:
                published_at = article[6]
                date_str = published_at.strftime("%Y-%m-%d %H:%M") if published_at else "Unknown"

                timeline.append(
                    {
                        "date": date_str,
                        "title": article[1],
                        "source": article[5],
                        "quality_score": article[8] or 0.0,
                        "summary": article[3] or "No summary available",
                    }
                )

            return timeline

        except Exception as e:
            logger.error(f"Error creating timeline: {e}")
            return []

    def _summarize_evolution(self, articles: list, timeline: list) -> str:
        """Summarize story evolution"""
        try:
            if not articles:
                return "No evolution data available."

            # Calculate evolution metrics
            quality_trend = self._calculate_quality_trend(articles)
            source_diversity = len(set(article[5] for article in articles if article[5]))
            time_span = self._calculate_time_span(articles)

            parts = []
            parts.append(
                f"Story tracked across {len(articles)} articles over {time_span} from {source_diversity} sources."
            )

            # Surface the key narrative shifts using article titles
            if timeline and len(timeline) >= 2:
                first_title = timeline[0].get("title", "")
                last_title = timeline[-1].get("title", "")
                if first_title and last_title:
                    parts.append(
                        f'Coverage began with "{first_title}" and most recently "{last_title}".'
                    )

            if quality_trend:
                parts.append(f"Quality trend: {quality_trend}.")

            return " ".join(parts)

        except Exception as e:
            logger.error(f"Error summarizing evolution: {e}")
            return "Error summarizing evolution."

    def _calculate_time_span(self, articles: list) -> str:
        """Calculate time span of articles"""
        try:
            if not articles:
                return "No articles"

            dates = [article[6] for article in articles if article[6]]
            if not dates:
                return "Unknown time span"

            min_date = min(dates)
            max_date = max(dates)

            if min_date.date() == max_date.date():
                return "Same day"
            else:
                days = (max_date - min_date).days
                return f"{days} days"

        except Exception as e:
            logger.error(f"Error calculating time span: {e}")
            return "Unknown"

    def _extract_sources(self, articles: list) -> list[str]:
        """Extract unique sources from articles"""
        try:
            sources = list(set(article[5] for article in articles if article[5]))
            return sorted(sources)
        except Exception as e:
            logger.error(f"Error extracting sources: {e}")
            return []

    def _analyze_quality_distribution(self, quality_scores: list[float]) -> str:
        """Analyze quality score distribution"""
        try:
            if not quality_scores:
                return "No quality data"

            high = sum(1 for score in quality_scores if score >= 0.7)
            medium = sum(1 for score in quality_scores if 0.4 <= score < 0.7)
            low = sum(1 for score in quality_scores if score < 0.4)
            total = len(quality_scores)

            return f"High: {high} ({high / total * 100:.1f}%), Medium: {medium} ({medium / total * 100:.1f}%), Low: {low} ({low / total * 100:.1f}%)"

        except Exception as e:
            logger.error(f"Error analyzing quality distribution: {e}")
            return "Error analyzing quality"

    def _calculate_quality_trend(self, articles: list) -> str:
        """Calculate quality trend over time"""
        try:
            if len(articles) < 2:
                return "Insufficient data"

            # Sort by date
            sorted_articles = sorted(articles, key=lambda x: x[6] or datetime.min)

            # Calculate average quality for first and second half
            mid_point = len(sorted_articles) // 2
            first_half_avg = (
                sum(article[8] or 0.0 for article in sorted_articles[:mid_point]) / mid_point
            )
            second_half_avg = sum(article[8] or 0.0 for article in sorted_articles[mid_point:]) / (
                len(sorted_articles) - mid_point
            )

            if second_half_avg > first_half_avg + 0.1:
                return "Improving"
            elif second_half_avg < first_half_avg - 0.1:
                return "Declining"
            else:
                return "Stable"

        except Exception as e:
            logger.error(f"Error calculating quality trend: {e}")
            return "Unknown"
