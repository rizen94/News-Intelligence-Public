#!/usr/bin/env python3
"""
Story Discovery System for News Intelligence System v3.0
Analyzes new content and suggests potential storylines to follow
"""

import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import re
from collections import defaultdict, Counter
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

@dataclass
class StorySuggestion:
    """Suggested story to track"""
    suggestion_id: str
    title: str
    description: str
    confidence_score: float  # 0.0-1.0
    article_count: int
    time_span_days: int
    keywords: List[str]
    entities: List[str]
    geographic_regions: List[str]
    source_diversity: int
    quality_score: float
    trend_direction: str  # 'rising', 'stable', 'declining'
    suggested_priority: int  # 1-10
    sample_articles: List[int]  # Article IDs
    created_at: str

@dataclass
class WeeklyDigest:
    """Weekly digest of story suggestions and analysis"""
    digest_id: str
    week_start: str
    week_end: str
    total_articles_analyzed: int
    new_stories_suggested: int
    existing_stories_updated: int
    top_trending_topics: List[str]
    story_suggestions: List[StorySuggestion]
    quality_metrics: Dict[str, Any]
    created_at: str

class StoryDiscoverySystem:
    """
    System for discovering and suggesting new storylines to track
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize story discovery system
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize database tables
        self._init_database_tables()
        
        # Initialize ML components
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2
        )
        
        self.clustering_model = DBSCAN(
            eps=0.3,
            min_samples=3,
            metric='cosine'
        )
    
    def _init_database_tables(self):
        """Initialize database tables for story discovery"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Story suggestions table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_suggestions (
                    suggestion_id VARCHAR(50) PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
                    article_count INTEGER,
                    time_span_days INTEGER,
                    keywords JSONB,
                    entities JSONB,
                    geographic_regions JSONB,
                    source_diversity INTEGER,
                    quality_score DECIMAL(3,2),
                    trend_direction VARCHAR(20),
                    suggested_priority INTEGER CHECK (suggested_priority >= 1 AND suggested_priority <= 10),
                    sample_articles JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_reviewed BOOLEAN DEFAULT false,
                    is_accepted BOOLEAN DEFAULT false,
                    is_rejected BOOLEAN DEFAULT false
                )
            """)
            
            # Weekly digests table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS weekly_digests (
                    digest_id VARCHAR(50) PRIMARY KEY,
                    week_start TIMESTAMP NOT NULL,
                    week_end TIMESTAMP NOT NULL,
                    total_articles_analyzed INTEGER,
                    new_stories_suggested INTEGER,
                    existing_stories_updated INTEGER,
                    top_trending_topics JSONB,
                    story_suggestions JSONB,
                    quality_metrics JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_generated BOOLEAN DEFAULT false
                )
            """)
            
            # Story trend analysis table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_trend_analysis (
                    analysis_id SERIAL PRIMARY KEY,
                    topic VARCHAR(200) NOT NULL,
                    week_start TIMESTAMP NOT NULL,
                    article_count INTEGER,
                    sentiment_avg DECIMAL(3,2),
                    quality_avg DECIMAL(3,2),
                    source_count INTEGER,
                    geographic_diversity INTEGER,
                    trend_score DECIMAL(5,4),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            
            self.logger.info("Story discovery database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize story discovery database: {e}")
            raise
    
    def generate_weekly_digest(self, week_start: Optional[datetime] = None) -> WeeklyDigest:
        """
        Generate weekly digest of story suggestions and analysis
        
        Args:
            week_start: Start date for the week (defaults to last Monday)
            
        Returns:
            WeeklyDigest object
        """
        try:
            if week_start is None:
                week_start = self._get_last_monday()
            
            week_end = week_start + timedelta(days=7)
            
            self.logger.info(f"Generating weekly digest for {week_start.date()} to {week_end.date()}")
            
            # Get articles from the week
            articles = self._get_articles_for_period(week_start, week_end)
            
            if not articles:
                self.logger.warning("No articles found for the specified period")
                return self._create_empty_digest(week_start, week_end)
            
            # Analyze articles for story suggestions
            story_suggestions = self._analyze_articles_for_stories(articles)
            
            # Get trending topics
            trending_topics = self._get_trending_topics(articles)
            
            # Calculate quality metrics
            quality_metrics = self._calculate_quality_metrics(articles)
            
            # Create digest
            digest = WeeklyDigest(
                digest_id=f"digest_{week_start.strftime('%Y%m%d')}",
                week_start=week_start.isoformat(),
                week_end=week_end.isoformat(),
                total_articles_analyzed=len(articles),
                new_stories_suggested=len(story_suggestions),
                existing_stories_updated=0,  # TODO: Implement existing story updates
                top_trending_topics=trending_topics,
                story_suggestions=story_suggestions,
                quality_metrics=quality_metrics,
                created_at=datetime.now().isoformat()
            )
            
            # Store digest in database
            self._store_weekly_digest(digest)
            
            self.logger.info(f"Generated weekly digest with {len(story_suggestions)} story suggestions")
            return digest
            
        except Exception as e:
            self.logger.error(f"Failed to generate weekly digest: {e}")
            raise
    
    def _analyze_articles_for_stories(self, articles: List[Dict[str, Any]]) -> List[StorySuggestion]:
        """
        Analyze articles to suggest potential stories to track
        
        Args:
            articles: List of article dictionaries
            
        Returns:
            List of StorySuggestion objects
        """
        try:
            if len(articles) < 3:
                return []
            
            # Prepare text data for clustering
            texts = []
            for article in articles:
                text = f"{article.get('title', '')} {article.get('summary', '')} {article.get('content', '')}"
                texts.append(text)
            
            # Vectorize texts
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # Cluster articles
            clusters = self.clustering_model.fit_predict(tfidf_matrix)
            
            # Group articles by cluster
            cluster_groups = defaultdict(list)
            for i, cluster_id in enumerate(clusters):
                if cluster_id != -1:  # Ignore noise points
                    cluster_groups[cluster_id].append(articles[i])
            
            # Generate story suggestions from clusters
            story_suggestions = []
            for cluster_id, cluster_articles in cluster_groups.items():
                if len(cluster_articles) >= 3:  # Minimum cluster size
                    suggestion = self._create_story_suggestion_from_cluster(
                        cluster_id, cluster_articles
                    )
                    if suggestion:
                        story_suggestions.append(suggestion)
            
            # Sort by confidence score
            story_suggestions.sort(key=lambda x: x.confidence_score, reverse=True)
            
            return story_suggestions[:10]  # Return top 10 suggestions
            
        except Exception as e:
            self.logger.error(f"Failed to analyze articles for stories: {e}")
            return []
    
    def _create_story_suggestion_from_cluster(self, cluster_id: int, articles: List[Dict[str, Any]]) -> Optional[StorySuggestion]:
        """
        Create a story suggestion from a cluster of articles
        
        Args:
            cluster_id: ID of the cluster
            articles: List of articles in the cluster
            
        Returns:
            StorySuggestion object or None
        """
        try:
            if len(articles) < 3:
                return None
            
            # Extract common keywords
            keywords = self._extract_common_keywords(articles)
            
            # Extract entities
            entities = self._extract_common_entities(articles)
            
            # Extract geographic regions
            regions = self._extract_geographic_regions(articles)
            
            # Calculate metrics
            article_count = len(articles)
            time_span = self._calculate_time_span(articles)
            source_diversity = len(set(article.get('source', '') for article in articles))
            quality_score = np.mean([article.get('quality_score', 0) for article in articles])
            
            # Determine trend direction
            trend_direction = self._determine_trend_direction(articles)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                article_count, time_span, source_diversity, quality_score, keywords
            )
            
            # Generate title and description
            title = self._generate_story_title(keywords, entities)
            description = self._generate_story_description(articles, keywords, entities)
            
            # Determine suggested priority
            suggested_priority = self._determine_suggested_priority(
                confidence_score, article_count, quality_score, trend_direction
            )
            
            # Get sample articles
            sample_articles = [article['id'] for article in articles[:5]]
            
            suggestion = StorySuggestion(
                suggestion_id=f"suggestion_{cluster_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                title=title,
                description=description,
                confidence_score=confidence_score,
                article_count=article_count,
                time_span_days=time_span,
                keywords=keywords,
                entities=entities,
                geographic_regions=regions,
                source_diversity=source_diversity,
                quality_score=quality_score,
                trend_direction=trend_direction,
                suggested_priority=suggested_priority,
                sample_articles=sample_articles,
                created_at=datetime.now().isoformat()
            )
            
            return suggestion
            
        except Exception as e:
            self.logger.error(f"Failed to create story suggestion from cluster: {e}")
            return None
    
    def _extract_common_keywords(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract common keywords from articles"""
        try:
            # Combine all text
            all_text = " ".join([
                f"{article.get('title', '')} {article.get('summary', '')} {article.get('content', '')}"
                for article in articles
            ]).lower()
            
            # Extract words (simple approach)
            words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text)
            
            # Count word frequency
            word_counts = Counter(words)
            
            # Filter out common stop words
            stop_words = {
                'this', 'that', 'with', 'have', 'will', 'from', 'they', 'been', 'were',
                'said', 'each', 'which', 'their', 'time', 'would', 'there', 'could',
                'other', 'after', 'first', 'well', 'also', 'new', 'want', 'because',
                'any', 'these', 'give', 'day', 'most', 'us', 'is', 'are', 'was', 'be',
                'or', 'an', 'as', 'at', 'by', 'for', 'in', 'of', 'on', 'to', 'the',
                'and', 'a', 'it', 'you', 'he', 'she', 'we', 'they', 'me', 'him', 'her',
                'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'
            }
            
            # Get top keywords
            keywords = [
                word for word, count in word_counts.most_common(20)
                if word not in stop_words and count >= 2
            ]
            
            return keywords[:10]  # Return top 10 keywords
            
        except Exception as e:
            self.logger.error(f"Failed to extract common keywords: {e}")
            return []
    
    def _extract_common_entities(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract common entities from articles"""
        try:
            # Simple entity extraction (in a real system, you'd use NER)
            entities = set()
            
            for article in articles:
                text = f"{article.get('title', '')} {article.get('summary', '')}"
                
                # Look for capitalized words (simple approach)
                words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
                
                # Filter out common words
                common_words = {
                    'The', 'This', 'That', 'With', 'Have', 'Will', 'From', 'They',
                    'Been', 'Were', 'Said', 'Each', 'Which', 'Their', 'Time',
                    'Would', 'There', 'Could', 'Other', 'After', 'First', 'Well',
                    'Also', 'New', 'Want', 'Because', 'Any', 'These', 'Give', 'Day',
                    'Most', 'Us', 'Is', 'Are', 'Was', 'Be', 'Or', 'An', 'As', 'At',
                    'By', 'For', 'In', 'Of', 'On', 'To', 'The', 'And', 'A', 'It',
                    'You', 'He', 'She', 'We', 'They', 'Me', 'Him', 'Her', 'Us',
                    'Them', 'My', 'Your', 'His', 'Her', 'Its', 'Our', 'Their'
                }
                
                for word in words:
                    if word not in common_words and len(word) > 3:
                        entities.add(word)
            
            return list(entities)[:15]  # Return top 15 entities
            
        except Exception as e:
            self.logger.error(f"Failed to extract common entities: {e}")
            return []
    
    def _extract_geographic_regions(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Extract geographic regions from articles"""
        try:
            # Simple geographic region extraction
            regions = set()
            
            # Common country and region names
            geographic_terms = {
                'United States', 'USA', 'US', 'America', 'American',
                'China', 'Chinese', 'Beijing', 'Shanghai',
                'Russia', 'Russian', 'Moscow', 'Kremlin',
                'Ukraine', 'Ukrainian', 'Kyiv', 'Kiev',
                'Germany', 'German', 'Berlin', 'Munich',
                'France', 'French', 'Paris', 'Lyon',
                'United Kingdom', 'UK', 'Britain', 'British', 'London',
                'Japan', 'Japanese', 'Tokyo', 'Osaka',
                'India', 'Indian', 'New Delhi', 'Mumbai',
                'Brazil', 'Brazilian', 'São Paulo', 'Rio de Janeiro',
                'Canada', 'Canadian', 'Toronto', 'Vancouver',
                'Australia', 'Australian', 'Sydney', 'Melbourne',
                'South Korea', 'Korean', 'Seoul', 'Busan',
                'Italy', 'Italian', 'Rome', 'Milan',
                'Spain', 'Spanish', 'Madrid', 'Barcelona',
                'Mexico', 'Mexican', 'Mexico City', 'Guadalajara',
                'Netherlands', 'Dutch', 'Amsterdam', 'Rotterdam',
                'Sweden', 'Swedish', 'Stockholm', 'Gothenburg',
                'Norway', 'Norwegian', 'Oslo', 'Bergen',
                'Denmark', 'Danish', 'Copenhagen', 'Aarhus',
                'Finland', 'Finnish', 'Helsinki', 'Tampere',
                'Poland', 'Polish', 'Warsaw', 'Krakow',
                'Czech Republic', 'Czech', 'Prague', 'Brno',
                'Hungary', 'Hungarian', 'Budapest', 'Debrecen',
                'Romania', 'Romanian', 'Bucharest', 'Cluj',
                'Bulgaria', 'Bulgarian', 'Sofia', 'Plovdiv',
                'Croatia', 'Croatian', 'Zagreb', 'Split',
                'Slovenia', 'Slovenian', 'Ljubljana', 'Maribor',
                'Slovakia', 'Slovak', 'Bratislava', 'Košice',
                'Estonia', 'Estonian', 'Tallinn', 'Tartu',
                'Latvia', 'Latvian', 'Riga', 'Daugavpils',
                'Lithuania', 'Lithuanian', 'Vilnius', 'Kaunas',
                'Europe', 'European', 'EU', 'European Union',
                'Asia', 'Asian', 'Africa', 'African',
                'Middle East', 'Middle Eastern', 'Arab', 'Arabic',
                'Latin America', 'South America', 'North America',
                'Oceania', 'Pacific', 'Atlantic', 'Mediterranean'
            }
            
            for article in articles:
                text = f"{article.get('title', '')} {article.get('summary', '')}"
                
                for term in geographic_terms:
                    if term.lower() in text.lower():
                        regions.add(term)
            
            return list(regions)[:10]  # Return top 10 regions
            
        except Exception as e:
            self.logger.error(f"Failed to extract geographic regions: {e}")
            return []
    
    def _calculate_time_span(self, articles: List[Dict[str, Any]]) -> int:
        """Calculate time span of articles in days"""
        try:
            dates = []
            for article in articles:
                if article.get('published_date'):
                    dates.append(article['published_date'])
            
            if len(dates) < 2:
                return 1
            
            min_date = min(dates)
            max_date = max(dates)
            
            return (max_date - min_date).days + 1
            
        except Exception as e:
            self.logger.error(f"Failed to calculate time span: {e}")
            return 1
    
    def _determine_trend_direction(self, articles: List[Dict[str, Any]]) -> str:
        """Determine trend direction based on article dates"""
        try:
            if len(articles) < 3:
                return 'stable'
            
            # Sort articles by date
            sorted_articles = sorted(
                articles,
                key=lambda x: x.get('published_date', datetime.min)
            )
            
            # Calculate article count per day
            daily_counts = defaultdict(int)
            for article in sorted_articles:
                if article.get('published_date'):
                    date_key = article['published_date'].date()
                    daily_counts[date_key] += 1
            
            if len(daily_counts) < 2:
                return 'stable'
            
            # Calculate trend
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[date] for date in dates]
            
            # Simple linear trend calculation
            n = len(counts)
            x = np.arange(n)
            y = np.array(counts)
            
            # Calculate slope
            slope = np.polyfit(x, y, 1)[0]
            
            if slope > 0.5:
                return 'rising'
            elif slope < -0.5:
                return 'declining'
            else:
                return 'stable'
                
        except Exception as e:
            self.logger.error(f"Failed to determine trend direction: {e}")
            return 'stable'
    
    def _calculate_confidence_score(self, article_count: int, time_span: int, 
                                  source_diversity: int, quality_score: float, 
                                  keywords: List[str]) -> float:
        """Calculate confidence score for story suggestion"""
        try:
            # Base score from article count
            count_score = min(article_count / 10.0, 1.0)  # Max 1.0 for 10+ articles
            
            # Time span score (longer is better, but not too long)
            time_score = min(time_span / 7.0, 1.0)  # Max 1.0 for 7+ days
            
            # Source diversity score
            diversity_score = min(source_diversity / 5.0, 1.0)  # Max 1.0 for 5+ sources
            
            # Quality score
            quality_score_norm = quality_score  # Already 0-1
            
            # Keywords score
            keywords_score = min(len(keywords) / 10.0, 1.0)  # Max 1.0 for 10+ keywords
            
            # Weighted average
            confidence = (
                count_score * 0.3 +
                time_score * 0.2 +
                diversity_score * 0.2 +
                quality_score_norm * 0.2 +
                keywords_score * 0.1
            )
            
            return min(confidence, 1.0)
            
        except Exception as e:
            self.logger.error(f"Failed to calculate confidence score: {e}")
            return 0.0
    
    def _generate_story_title(self, keywords: List[str], entities: List[str]) -> str:
        """Generate a story title from keywords and entities"""
        try:
            if not keywords and not entities:
                return "Untitled Story"
            
            # Use top keywords and entities
            title_parts = []
            
            if entities:
                title_parts.append(entities[0])
            
            if keywords:
                title_parts.append(keywords[0])
            
            if len(title_parts) >= 2:
                return f"{title_parts[0]} and {title_parts[1]}"
            elif title_parts:
                return title_parts[0]
            else:
                return "Untitled Story"
                
        except Exception as e:
            self.logger.error(f"Failed to generate story title: {e}")
            return "Untitled Story"
    
    def _generate_story_description(self, articles: List[Dict[str, Any]], 
                                  keywords: List[str], entities: List[str]) -> str:
        """Generate a story description from articles, keywords, and entities"""
        try:
            # Get sample titles
            titles = [article.get('title', '') for article in articles[:3]]
            
            # Create description
            description_parts = []
            
            if entities:
                description_parts.append(f"Focuses on {', '.join(entities[:3])}")
            
            if keywords:
                description_parts.append(f"Key topics include {', '.join(keywords[:5])}")
            
            if titles:
                description_parts.append(f"Sample headlines: {titles[0]}")
            
            return ". ".join(description_parts) + "."
            
        except Exception as e:
            self.logger.error(f"Failed to generate story description: {e}")
            return "Story description unavailable"
    
    def _determine_suggested_priority(self, confidence_score: float, article_count: int,
                                    quality_score: float, trend_direction: str) -> int:
        """Determine suggested priority level (1-10)"""
        try:
            base_priority = 5  # Default priority
            
            # Adjust based on confidence
            if confidence_score > 0.8:
                base_priority += 2
            elif confidence_score > 0.6:
                base_priority += 1
            elif confidence_score < 0.4:
                base_priority -= 1
            
            # Adjust based on article count
            if article_count > 10:
                base_priority += 1
            elif article_count < 3:
                base_priority -= 1
            
            # Adjust based on quality
            if quality_score > 0.8:
                base_priority += 1
            elif quality_score < 0.5:
                base_priority -= 1
            
            # Adjust based on trend
            if trend_direction == 'rising':
                base_priority += 1
            elif trend_direction == 'declining':
                base_priority -= 1
            
            # Ensure priority is within bounds
            return max(1, min(10, base_priority))
            
        except Exception as e:
            self.logger.error(f"Failed to determine suggested priority: {e}")
            return 5
    
    def _get_trending_topics(self, articles: List[Dict[str, Any]]) -> List[str]:
        """Get trending topics from articles"""
        try:
            # Extract all keywords
            all_keywords = []
            for article in articles:
                keywords = self._extract_common_keywords([article])
                all_keywords.extend(keywords)
            
            # Count keyword frequency
            keyword_counts = Counter(all_keywords)
            
            # Return top trending topics
            return [keyword for keyword, count in keyword_counts.most_common(10)]
            
        except Exception as e:
            self.logger.error(f"Failed to get trending topics: {e}")
            return []
    
    def _calculate_quality_metrics(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate quality metrics for the digest"""
        try:
            if not articles:
                return {}
            
            quality_scores = [article.get('quality_score', 0) for article in articles]
            sentiment_scores = [article.get('sentiment_score', 0) for article in articles]
            
            return {
                'avg_quality_score': np.mean(quality_scores),
                'avg_sentiment_score': np.mean(sentiment_scores),
                'total_articles': len(articles),
                'high_quality_articles': len([s for s in quality_scores if s > 0.7]),
                'positive_sentiment_articles': len([s for s in sentiment_scores if s > 0.1]),
                'negative_sentiment_articles': len([s for s in sentiment_scores if s < -0.1])
            }
            
        except Exception as e:
            self.logger.error(f"Failed to calculate quality metrics: {e}")
            return {}
    
    def _get_last_monday(self) -> datetime:
        """Get the date of last Monday"""
        today = datetime.now().date()
        days_since_monday = today.weekday()
        last_monday = today - timedelta(days=days_since_monday)
        return datetime.combine(last_monday, datetime.min.time())
    
    def _get_articles_for_period(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get articles for a specific time period"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, title, content, summary, source, category, published_date,
                       quality_score, sentiment_score, url
                FROM articles
                WHERE published_date >= %s AND published_date < %s
                ORDER BY published_date DESC
            """, (start_date, end_date))
            
            articles = []
            for row in cur.fetchall():
                article = {
                    'id': row[0],
                    'title': row[1],
                    'content': row[2],
                    'summary': row[3],
                    'source': row[4],
                    'category': row[5],
                    'published_date': row[6],
                    'quality_score': row[7],
                    'sentiment_score': row[8],
                    'url': row[9]
                }
                articles.append(article)
            
            cur.close()
            conn.close()
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Failed to get articles for period: {e}")
            return []
    
    def _create_empty_digest(self, week_start: datetime, week_end: datetime) -> WeeklyDigest:
        """Create an empty digest when no articles are found"""
        return WeeklyDigest(
            digest_id=f"digest_{week_start.strftime('%Y%m%d')}",
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            total_articles_analyzed=0,
            new_stories_suggested=0,
            existing_stories_updated=0,
            top_trending_topics=[],
            story_suggestions=[],
            quality_metrics={},
            created_at=datetime.now().isoformat()
        )
    
    def _store_weekly_digest(self, digest: WeeklyDigest):
        """Store weekly digest in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO weekly_digests 
                (digest_id, week_start, week_end, total_articles_analyzed,
                 new_stories_suggested, existing_stories_updated, top_trending_topics,
                 story_suggestions, quality_metrics, created_at, is_generated)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (digest_id) DO UPDATE SET
                week_start = EXCLUDED.week_start,
                week_end = EXCLUDED.week_end,
                total_articles_analyzed = EXCLUDED.total_articles_analyzed,
                new_stories_suggested = EXCLUDED.new_stories_suggested,
                existing_stories_updated = EXCLUDED.existing_stories_updated,
                top_trending_topics = EXCLUDED.top_trending_topics,
                story_suggestions = EXCLUDED.story_suggestions,
                quality_metrics = EXCLUDED.quality_metrics,
                is_generated = EXCLUDED.is_generated
            """, (
                digest.digest_id, digest.week_start, digest.week_end,
                digest.total_articles_analyzed, digest.new_stories_suggested,
                digest.existing_stories_updated, json.dumps(digest.top_trending_topics),
                json.dumps([asdict(s) for s in digest.story_suggestions]),
                json.dumps(digest.quality_metrics), digest.created_at, True
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to store weekly digest: {e}")
            raise
    
    def get_weekly_digest(self, digest_id: str) -> Optional[WeeklyDigest]:
        """Get a weekly digest by ID"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT digest_id, week_start, week_end, total_articles_analyzed,
                       new_stories_suggested, existing_stories_updated, top_trending_topics,
                       story_suggestions, quality_metrics, created_at
                FROM weekly_digests
                WHERE digest_id = %s
            """, (digest_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            # Parse story suggestions
            story_suggestions_data = json.loads(row[7]) if row[7] else []
            story_suggestions = [
                StorySuggestion(**suggestion) for suggestion in story_suggestions_data
            ]
            
            digest = WeeklyDigest(
                digest_id=row[0],
                week_start=row[1],
                week_end=row[2],
                total_articles_analyzed=row[3],
                new_stories_suggested=row[4],
                existing_stories_updated=row[5],
                top_trending_topics=json.loads(row[6]) if row[6] else [],
                story_suggestions=story_suggestions,
                quality_metrics=json.loads(row[8]) if row[8] else {},
                created_at=row[9]
            )
            
            cur.close()
            conn.close()
            
            return digest
            
        except Exception as e:
            self.logger.error(f"Failed to get weekly digest: {e}")
            return None
    
    def get_recent_digests(self, limit: int = 5) -> List[WeeklyDigest]:
        """Get recent weekly digests"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT digest_id, week_start, week_end, total_articles_analyzed,
                       new_stories_suggested, existing_stories_updated, top_trending_topics,
                       story_suggestions, quality_metrics, created_at
                FROM weekly_digests
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
            
            digests = []
            for row in cur.fetchall():
                # Parse story suggestions
                story_suggestions_data = json.loads(row[7]) if row[7] else []
                story_suggestions = [
                    StorySuggestion(**suggestion) for suggestion in story_suggestions_data
                ]
                
                digest = WeeklyDigest(
                    digest_id=row[0],
                    week_start=row[1],
                    week_end=row[2],
                    total_articles_analyzed=row[3],
                    new_stories_suggested=row[4],
                    existing_stories_updated=row[5],
                    top_trending_topics=json.loads(row[6]) if row[6] else [],
                    story_suggestions=story_suggestions,
                    quality_metrics=json.loads(row[8]) if row[8] else {},
                    created_at=row[9]
                )
                digests.append(digest)
            
            cur.close()
            conn.close()
            
            return digests
            
        except Exception as e:
            self.logger.error(f"Failed to get recent digests: {e}")
            return []
