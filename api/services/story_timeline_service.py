"""
Story Timeline Service
Automatically tracks story evolution and creates timelines
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class StoryTimelineService:
    def __init__(self, db: Session):
        self.db = db

    def generate_story_id(self, title: str, content: str = None) -> str:
        """Generate a unique story ID based on title and content"""
        # Create a hash from title and first 200 chars of content
        text_to_hash = title
        if content:
            text_to_hash += content[:200]

        # Remove common words and create hash
        cleaned_text = re.sub(
            r"\b(the|a|an|and|or|but|in|on|at|to|for|of|with|by)\b", "", text_to_hash.lower()
        )
        story_hash = hashlib.md5(cleaned_text.encode()).hexdigest()[:12]
        return f"story_{story_hash}"

    def find_related_stories(self, title: str, content: str = None) -> list[str]:
        """Find related stories based on title and content similarity"""
        try:
            # Extract key terms from title
            key_terms = self._extract_key_terms(title)
            if not key_terms:
                return []

            # Search for stories with similar terms
            query = text("""
                SELECT DISTINCT story_id, title
                FROM story_timelines
                WHERE last_updated >= :cutoff_date
                AND (
                    LOWER(title) LIKE ANY(:terms) OR
                    LOWER(summary) LIKE ANY(:terms)
                )
                ORDER BY last_updated DESC
                LIMIT 10
            """)

            terms = [f"%{term}%" for term in key_terms]
            cutoff_date = datetime.now() - timedelta(days=7)

            result = self.db.execute(query, {"terms": terms, "cutoff_date": cutoff_date})

            related_stories = []
            for row in result:
                related_stories.append({"story_id": row.story_id, "title": row.title})

            return related_stories
        except Exception as e:
            logger.error(f"Error finding related stories: {e}")
            return []

    def _extract_key_terms(self, text: str) -> list[str]:
        """Extract key terms from text for similarity matching"""
        # Remove common words and extract meaningful terms
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
            "being",
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
            "must",
            "can",
            "this",
            "that",
            "these",
            "those",
        }

        # Extract words longer than 3 characters
        words = re.findall(r"\b\w{4,}\b", text.lower())
        key_terms = [word for word in words if word not in stop_words]

        # Return top 5 most relevant terms
        return key_terms[:5]

    def create_or_update_timeline(self, article_data: dict[str, Any]) -> str | None:
        """Create or update a story timeline based on article data"""
        try:
            title = article_data.get("title", "")
            content = article_data.get("content", "")
            article_data.get("source", "")
            article_data.get("url", "")

            if not title:
                return None

            # Generate story ID
            story_id = self.generate_story_id(title, content)

            # Check if timeline exists
            existing_query = text(
                "SELECT id, article_count FROM story_timelines WHERE story_id = :story_id"
            )
            existing = self.db.execute(existing_query, {"story_id": story_id}).fetchone()

            if existing:
                # Update existing timeline
                self._update_timeline(story_id, article_data)
            else:
                # Create new timeline
                self._create_timeline(story_id, article_data)

            # Add event for this article
            self._add_article_event(story_id, article_data)

            return story_id
        except Exception as e:
            logger.error(f"Error creating/updating timeline: {e}")
            return None

    def _create_timeline(self, story_id: str, article_data: dict[str, Any]):
        """Create a new story timeline"""
        title = article_data.get("title", "")
        content = article_data.get("content", "")
        article_data.get("source", "")

        # Find related stories
        related_stories = self.find_related_stories(title, content)

        # Create summary from content
        summary = self._create_summary(content)

        insert_query = text("""
            INSERT INTO story_timelines (
                story_id, title, summary, first_seen, last_updated,
                article_count, source_count, related_stories
            )
            VALUES (
                :story_id, :title, :summary, :first_seen, :last_updated,
                :article_count, :source_count, :related_stories
            )
        """)

        now = datetime.now()
        self.db.execute(
            insert_query,
            {
                "story_id": story_id,
                "title": title,
                "summary": summary,
                "first_seen": now,
                "last_updated": now,
                "article_count": 1,
                "source_count": 1,
                "related_stories": related_stories,
            },
        )

    def _update_timeline(self, story_id: str, article_data: dict[str, Any]):
        """Update existing story timeline"""
        article_data.get("source", "")

        # Update counts and last_updated
        update_query = text("""
            UPDATE story_timelines
            SET
                last_updated = :now,
                article_count = article_count + 1,
                source_count = CASE
                    WHEN source_count = 1 OR source_count IS NULL THEN 1
                    ELSE source_count + 1
                END
            WHERE story_id = :story_id
        """)

        self.db.execute(update_query, {"now": datetime.now(), "story_id": story_id})

    def _add_article_event(self, story_id: str, article_data: dict[str, Any]):
        """Add an event for this article"""
        title = article_data.get("title", "")
        source = article_data.get("source", "")
        url = article_data.get("url", "")

        # Determine event type based on source
        event_type = "new_source" if source else "update"
        event_title = f"New article from {source}" if source else "Story update"

        # Calculate significance score based on source and content
        significance_score = self._calculate_significance_score(article_data)

        insert_query = text("""
            INSERT INTO story_events (
                story_id, event_type, event_title, event_description,
                source_url, source_name, significance_score, event_timestamp
            )
            VALUES (
                :story_id, :event_type, :event_title, :event_description,
                :source_url, :source_name, :significance_score, :event_timestamp
            )
        """)

        self.db.execute(
            insert_query,
            {
                "story_id": story_id,
                "event_type": event_type,
                "event_title": event_title,
                "event_description": title,
                "source_url": url,
                "source_name": source,
                "significance_score": significance_score,
                "event_timestamp": datetime.now(),
            },
        )

    def _create_summary(self, content: str) -> str:
        """Create a summary from article content"""
        if not content:
            return ""

        # Simple extractive summary - take first 200 characters
        summary = content[:200].strip()
        if len(content) > 200:
            summary += "..."

        return summary

    def _calculate_significance_score(self, article_data: dict[str, Any]) -> float:
        """Calculate significance score for an article"""
        score = 0.0

        # Base score
        score += 0.3

        # Source credibility bonus
        source = article_data.get("source", "").lower()
        credible_sources = ["reuters", "ap", "bbc", "cnn", "fox news", "nytimes", "washington post"]
        if any(credible in source for credible in credible_sources):
            score += 0.2

        # Content length bonus
        content = article_data.get("content", "")
        if len(content) > 500:
            score += 0.2
        elif len(content) > 200:
            score += 0.1

        # Title keywords bonus
        title = article_data.get("title", "").lower()
        important_keywords = [
            "breaking",
            "urgent",
            "exclusive",
            "major",
            "significant",
            "important",
        ]
        if any(keyword in title for keyword in important_keywords):
            score += 0.3

        return min(score, 1.0)  # Cap at 1.0

    def get_trending_stories(self, hours_back: int = 24, limit: int = 10) -> list[dict[str, Any]]:
        """Get trending stories based on recent activity"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours_back)

            query = text("""
                SELECT
                    st.story_id,
                    st.title,
                    st.article_count,
                    st.source_count,
                    st.last_updated,
                    COUNT(se.id) as recent_events
                FROM story_timelines st
                LEFT JOIN story_events se ON st.story_id = se.story_id
                    AND se.event_timestamp >= :cutoff_time
                WHERE st.last_updated >= :cutoff_time
                GROUP BY st.story_id, st.title, st.article_count, st.source_count, st.last_updated
                ORDER BY recent_events DESC, st.article_count DESC
                LIMIT :limit
            """)

            result = self.db.execute(query, {"cutoff_time": cutoff_time, "limit": limit})

            trending_stories = []
            for row in result:
                trending_stories.append(
                    {
                        "story_id": row.story_id,
                        "title": row.title,
                        "article_count": row.article_count,
                        "source_count": row.source_count,
                        "last_updated": row.last_updated.isoformat() if row.last_updated else None,
                        "recent_events": row.recent_events,
                    }
                )

            return trending_stories
        except Exception as e:
            logger.error(f"Error getting trending stories: {e}")
            return []
