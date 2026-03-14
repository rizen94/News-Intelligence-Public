"""
Automated Daily Briefing Service for News Intelligence System
Generates scheduled daily intelligence reports with topic clouds and breaking news
Uses local processing only - no external AI services
"""

import logging
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import psycopg2
from shared.database.connection import get_db_connection
from .storyline_tracker import StorylineTracker
from modules.deduplication.advanced_deduplication_service import (
    AdvancedDeduplicationService,
    get_deduplication_service
)

logger = logging.getLogger(__name__)

class DailyBriefingService:
    """
    Service for generating automated daily intelligence briefings
    """
    
    def __init__(self, db_config: Dict):
        """
        Initialize the daily briefing service
        
        Args:
            db_config: Database configuration dictionary
        """
        self.db_config = db_config
        self.storyline_tracker = StorylineTracker(db_config)
        self.deduplication_service = get_deduplication_service(db_config)
        
    def generate_daily_briefing(self, 
                               briefing_date: Optional[datetime] = None,
                               include_deduplication: bool = True,
                               include_storylines: bool = True) -> Dict[str, any]:
        """
        Generate a comprehensive daily intelligence briefing
        
        Args:
            briefing_date: Date for the briefing (defaults to today)
            include_deduplication: Whether to include deduplication stats
            include_storylines: Whether to include storyline analysis
            
        Returns:
            Dictionary containing the daily briefing
        """
        try:
            briefing_date = briefing_date or datetime.now()
            briefing_date_str = briefing_date.strftime('%Y-%m-%d')
            
            logger.info(f"Generating daily briefing for {briefing_date_str}")
            
            # Initialize briefing structure
            briefing = {
                "briefing_date": briefing_date_str,
                "generated_at": datetime.now().isoformat(),
                "briefing_type": "daily_intelligence",
                "sections": {}
            }
            
            # Generate system overview
            briefing["sections"]["system_overview"] = self._generate_system_overview(briefing_date)
            
            # Generate content analysis
            briefing["sections"]["content_analysis"] = self._generate_content_analysis(briefing_date)
            
            # Generate topic cloud and breaking news
            if include_storylines:
                briefing["sections"]["storyline_analysis"] = self._generate_storyline_analysis(briefing_date)
            
            # Generate deduplication report
            if include_deduplication:
                briefing["sections"]["deduplication_report"] = self._generate_deduplication_report()
            
            # Generate quality metrics
            briefing["sections"]["quality_metrics"] = self._generate_quality_metrics(briefing_date)
            
            # Generate recommendations
            briefing["sections"]["recommendations"] = self._generate_recommendations(briefing)
            
            # Calculate briefing statistics
            briefing["statistics"] = self._calculate_briefing_statistics(briefing)
            
            logger.info(f"Daily briefing generated successfully for {briefing_date_str}")
            return briefing
            
        except Exception as e:
            logger.error(f"Error generating daily briefing: {e}")
            return {"error": str(e)}
    
    def generate_weekly_briefing(self, 
                                week_start_date: Optional[datetime] = None) -> Dict[str, any]:
        """
        Generate a weekly intelligence briefing
        
        Args:
            week_start_date: Start of the week (defaults to Monday of current week)
            
        Returns:
            Dictionary containing the weekly briefing
        """
        try:
            if week_start_date is None:
                # Get Monday of current week
                today = datetime.now()
                days_since_monday = today.weekday()
                week_start_date = today - timedelta(days=days_since_monday)
            
            week_end_date = week_start_date + timedelta(days=6)
            
            logger.info(f"Generating weekly briefing for {week_start_date.strftime('%Y-%m-%d')} to {week_end_date.strftime('%Y-%m-%d')}")
            
            # Generate daily briefings for the week
            daily_briefings = []
            current_date = week_start_date
            
            while current_date <= week_end_date:
                daily_briefing = self.generate_daily_briefing(current_date, include_deduplication=False)
                if "error" not in daily_briefing:
                    daily_briefings.append(daily_briefing)
                current_date += timedelta(days=1)
            
            # Generate weekly summary
            weekly_briefing = {
                "briefing_type": "weekly_intelligence",
                "week_start": week_start_date.strftime('%Y-%m-%d'),
                "week_end": week_end_date.strftime('%Y-%m-%d'),
                "generated_at": datetime.now().isoformat(),
                "daily_briefings": daily_briefings,
                "weekly_summary": self._generate_weekly_summary(daily_briefings),
                "trend_analysis": self._generate_trend_analysis(daily_briefings)
            }
            
            return weekly_briefing
            
        except Exception as e:
            logger.error(f"Error generating weekly briefing: {e}")
            return {"error": str(e)}
    
    def _generate_system_overview(self, briefing_date: datetime) -> Dict[str, any]:
        """Generate system overview section"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get system statistics
            cursor.execute("SELECT COUNT(*) FROM articles")
            total_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= %s", (briefing_date.date(),))
            today_articles = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM articles WHERE updated_at >= %s", (briefing_date.date(),))
            today_updated = cursor.fetchone()[0]
            
            # Get source count
            cursor.execute("SELECT COUNT(DISTINCT source) FROM articles WHERE source IS NOT NULL")
            total_sources = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "total_articles": total_articles,
                "today_new_articles": today_articles,
                "today_updated_articles": today_updated,
                "total_sources": total_sources,
                "system_status": "operational",
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating system overview: {e}")
            return {"error": str(e)}
    
    def _generate_content_analysis(self, briefing_date: datetime) -> Dict[str, any]:
        """Generate content analysis section"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get content statistics for the day
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(*) as count,
                    AVG(COALESCE(quality_score, 0.5)) as avg_quality
                FROM articles 
                WHERE created_at >= %s 
                GROUP BY category 
                ORDER BY count DESC
            """, (briefing_date.date(),))
            
            category_stats = cursor.fetchall()
            
            # Get top sources for the day
            cursor.execute("""
                SELECT 
                    source,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= %s 
                AND source IS NOT NULL
                GROUP BY source 
                ORDER BY count DESC 
                LIMIT 10
            """, (briefing_date.date(),))
            
            source_stats = cursor.fetchall()
            
            conn.close()
            
            return {
                "category_distribution": [
                    {
                        "category": row[0] or "uncategorized",
                        "count": row[1],
                        "avg_quality": round(float(row[2]), 3)
                    }
                    for row in category_stats
                ],
                "top_sources": [
                    {
                        "source": row[0],
                        "count": row[1]
                    }
                    for row in source_stats
                ],
                "analysis_date": briefing_date.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            logger.error(f"Error generating content analysis: {e}")
            return {"error": str(e)}
    
    def _generate_storyline_analysis(self, briefing_date: datetime) -> Dict[str, any]:
        """Generate storyline analysis section"""
        try:
            # Get topic cloud for the day
            topic_cloud = self.storyline_tracker.generate_topic_cloud(days=1)
            
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
                    "sources": topic_cloud.get("topic_cloud", {}).get("sources", {})
                },
                "breaking_topics": breaking_topics,
                "daily_summary": topic_cloud.get("daily_summary", ""),
                "article_count": topic_cloud.get("article_count", 0)
            }
            
        except Exception as e:
            logger.error(f"Error generating storyline analysis: {e}")
            return {"error": str(e)}
    
    def _generate_deduplication_report(self) -> Dict[str, any]:
        """Generate deduplication report section"""
        try:
            dedup_stats = self.deduplication_service.get_deduplication_stats()
            
            if "error" in dedup_stats:
                return {"error": dedup_stats["error"]}
            
            # Get recent duplicate detection (async method, but we'll skip for now in sync context)
            # Note: detect_duplicates is async, but this method is sync
            # For now, just use stats
            recent_detection = {"duplicates_found": 0, "message": "Async detection skipped in sync context"}
            
            return {
                "statistics": dedup_stats,
                "recent_detection": recent_detection if "error" not in recent_detection else {},
                "recommendations": self._generate_deduplication_recommendations(dedup_stats)
            }
            
        except Exception as e:
            logger.error(f"Error generating deduplication report: {e}")
            return {"error": str(e)}
    
    def _generate_quality_metrics(self, briefing_date: datetime) -> Dict[str, any]:
        """Generate quality metrics section"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Get quality distribution for the day
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN COALESCE(quality_score, 0.5) >= 0.8 THEN 'high'
                        WHEN COALESCE(quality_score, 0.5) >= 0.6 THEN 'medium'
                        ELSE 'low'
                    END as quality_level,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= %s 
                GROUP BY quality_level
                ORDER BY quality_level DESC
            """, (briefing_date.date(),))
            
            quality_distribution = cursor.fetchall()
            
            # Get average quality by category
            cursor.execute("""
                SELECT 
                    category,
                    AVG(COALESCE(quality_score, 0.5)) as avg_quality,
                    COUNT(*) as count
                FROM articles 
                WHERE created_at >= %s 
                GROUP BY category 
                HAVING COUNT(*) >= 3
                ORDER BY avg_quality DESC
            """, (briefing_date.date(),))
            
            category_quality = cursor.fetchall()
            
            conn.close()
            
            return {
                "quality_distribution": [
                    {
                        "level": row[0],
                        "count": row[1]
                    }
                    for row in quality_distribution
                ],
                "category_quality": [
                    {
                        "category": row[0] or "uncategorized",
                        "avg_quality": round(float(row[1]), 3),
                        "count": row[2]
                    }
                    for row in category_quality
                ],
                "overall_quality_score": self._calculate_overall_quality(quality_distribution)
            }
            
        except Exception as e:
            logger.error(f"Error generating quality metrics: {e}")
            return {"error": str(e)}
    
    def _generate_recommendations(self, briefing: Dict) -> Dict[str, any]:
        """Generate recommendations based on briefing data"""
        try:
            recommendations = {
                "content_quality": [],
                "system_optimization": [],
                "story_monitoring": [],
                "priority_actions": []
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
                recommendations["priority_actions"].append("Review and improve low-quality content sources")
            if recommendations["story_monitoring"]:
                recommendations["priority_actions"].append("Monitor breaking stories and emerging trends")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return {"error": str(e)}
    
    def _calculate_briefing_statistics(self, briefing: Dict) -> Dict[str, any]:
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
                "success_rate": round(((total_sections - error_count) / total_sections) * 100, 1) if total_sections > 0 else 0,
                "total_articles": system_overview.get("total_articles", 0) if "error" not in system_overview else 0,
                "today_articles": system_overview.get("today_new_articles", 0) if "error" not in system_overview else 0,
                "breaking_stories": len(storyline_analysis.get("breaking_topics", [])) if "error" not in storyline_analysis else 0,
                "categories_covered": len(content_analysis.get("category_distribution", [])) if "error" not in content_analysis else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error calculating briefing statistics: {e}")
            return {"error": str(e)}
    
    def _generate_weekly_summary(self, daily_briefings: List[Dict]) -> Dict[str, any]:
        """Generate weekly summary from daily briefings"""
        try:
            if not daily_briefings:
                return {"error": "No daily briefings available"}
            
            # Aggregate weekly statistics
            total_articles = sum(b.get("statistics", {}).get("total_articles", 0) for b in daily_briefings)
            total_breaking = sum(b.get("statistics", {}).get("breaking_stories", 0) for b in daily_briefings)
            
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
                "average_articles_per_day": round(total_articles / len(daily_briefings), 1) if daily_briefings else 0
            }
            
        except Exception as e:
            logger.error(f"Error generating weekly summary: {e}")
            return {"error": str(e)}
    
    def _generate_trend_analysis(self, daily_briefings: List[Dict]) -> Dict[str, any]:
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
                
                article_trends.append({
                    "date": date,
                    "articles": stats.get("total_articles", 0),
                    "breaking": stats.get("breaking_stories", 0)
                })
                
                if "error" not in content_analysis:
                    avg_quality = sum(cat["avg_quality"] for cat in content_analysis.get("category_distribution", []))
                    cat_count = len(content_analysis.get("category_distribution", []))
                    if cat_count > 0:
                        quality_trends.append({
                            "date": date,
                            "avg_quality": round(avg_quality / cat_count, 3)
                        })
            
            return {
                "article_trends": article_trends,
                "quality_trends": quality_trends,
                "trend_analysis": self._analyze_trends(article_trends, quality_trends)
            }
            
        except Exception as e:
            logger.error(f"Error generating trend analysis: {e}")
            return {"error": str(e)}
    
    def _analyze_trends(self, article_trends: List[Dict], quality_trends: List[Dict]) -> Dict[str, any]:
        """Analyze trends in the data"""
        try:
            if not article_trends or not quality_trends:
                return {"error": "Insufficient trend data"}
            
            # Article volume trend
            article_counts = [t["articles"] for t in article_trends]
            article_trend = "increasing" if article_counts[-1] > article_counts[0] else "decreasing" if article_counts[-1] < article_counts[0] else "stable"
            
            # Quality trend
            quality_scores = [t["avg_quality"] for t in quality_trends]
            quality_trend = "improving" if quality_scores[-1] > quality_scores[0] else "declining" if quality_scores[-1] < quality_scores[0] else "stable"
            
            return {
                "article_volume_trend": article_trend,
                "quality_trend": quality_trend,
                "recommendations": self._generate_trend_recommendations(article_trend, quality_trend)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {"error": str(e)}
    
    def _generate_trend_recommendations(self, article_trend: str, quality_trend: str) -> List[str]:
        """Generate recommendations based on trends"""
        recommendations = []
        
        if article_trend == "decreasing":
            recommendations.append("Article volume is decreasing - investigate content sources and RSS feeds")
        elif article_trend == "increasing":
            recommendations.append("Article volume is increasing - monitor for quality maintenance")
        
        if quality_trend == "declining":
            recommendations.append("Content quality is declining - review content sources and filtering")
        elif quality_trend == "improving":
            recommendations.append("Content quality is improving - maintain current content strategies")
        
        return recommendations
    
    def _generate_deduplication_recommendations(self, dedup_stats: Dict) -> List[str]:
        """Generate deduplication recommendations"""
        recommendations = []
        
        dedup_rate = dedup_stats.get("deduplication_rate", 0)
        total_articles = dedup_stats.get("total_articles", 0)
        
        if dedup_rate > 20:
            recommendations.append("High duplicate rate detected - consider adjusting similarity thresholds")
        elif dedup_rate < 5:
            recommendations.append("Low duplicate rate - current deduplication is effective")
        
        if total_articles > 1000:
            recommendations.append("Large article database - consider batch deduplication processing")
        
        return recommendations
    
    def _calculate_overall_quality(self, quality_distribution: List) -> float:
        """Calculate overall quality score"""
        try:
            if not quality_distribution:
                return 0.0
            
            total_articles = sum(row[1] for row in quality_distribution)
            if total_articles == 0:
                return 0.0
            
            # Weighted quality score
            quality_scores = {
                "high": 0.9,
                "medium": 0.7,
                "low": 0.3
            }
            
            weighted_sum = sum(quality_scores.get(row[0], 0.5) * row[1] for row in quality_distribution)
            return round(weighted_sum / total_articles, 3)
            
        except Exception as e:
            logger.error(f"Error calculating overall quality: {e}")
            return 0.0
