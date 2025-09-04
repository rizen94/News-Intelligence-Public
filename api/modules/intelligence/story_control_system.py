#!/usr/bin/env python3
"""
Story Control System for News Intelligence System v3.0
Provides high-level control over story tracking, priority targeting, and quality filtering
"""

import logging
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import json
import re

logger = logging.getLogger(__name__)

@dataclass
class StoryExpectation:
    """Defines what to track for a specific story"""
    story_id: str
    name: str
    description: str
    priority_level: int  # 1-10, 10 being highest
    keywords: List[str]
    entities: List[str]  # People, places, organizations
    geographic_regions: List[str]
    time_period: Optional[Tuple[datetime, datetime]]  # Start and end dates
    quality_threshold: float  # 0.0-1.0, minimum quality score
    max_articles_per_day: int
    auto_enhance: bool  # Whether to auto-trigger RAG enhancement
    created_at: str
    updated_at: str
    is_active: bool

@dataclass
class StoryTarget:
    """Specific targets within a story to track"""
    target_id: str
    story_id: str
    target_type: str  # 'person', 'organization', 'event', 'concept'
    target_name: str
    target_description: str
    importance_weight: float  # 0.0-1.0
    tracking_keywords: List[str]
    tracking_entities: List[str]
    created_at: str
    is_active: bool

@dataclass
class StoryQualityFilter:
    """Quality control filters for story content"""
    filter_id: str
    story_id: str
    filter_type: str  # 'source_whitelist', 'source_blacklist', 'content_quality', 'sentiment_range'
    filter_config: Dict[str, Any]
    created_at: str
    is_active: bool

class StoryControlSystem:
    """
    High-level control system for story tracking and priority targeting
    """
    
    def __init__(self, db_config: Dict[str, str]):
        """
        Initialize story control system
        
        Args:
            db_config: Database connection configuration
        """
        self.db_config = db_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize database tables
        self._init_database_tables()
    
    def _init_database_tables(self):
        """Initialize database tables for story control"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            # Story expectations table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_expectations (
                    story_id VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    description TEXT,
                    priority_level INTEGER CHECK (priority_level >= 1 AND priority_level <= 10),
                    keywords JSONB,
                    entities JSONB,
                    geographic_regions JSONB,
                    time_period_start TIMESTAMP,
                    time_period_end TIMESTAMP,
                    quality_threshold DECIMAL(3,2) CHECK (quality_threshold >= 0.0 AND quality_threshold <= 1.0),
                    max_articles_per_day INTEGER DEFAULT 100,
                    auto_enhance BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT true
                )
            """)
            
            # Story targets table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_targets (
                    target_id VARCHAR(50) PRIMARY KEY,
                    story_id VARCHAR(50) REFERENCES story_expectations(story_id),
                    target_type VARCHAR(50) NOT NULL,
                    target_name VARCHAR(200) NOT NULL,
                    target_description TEXT,
                    importance_weight DECIMAL(3,2) CHECK (importance_weight >= 0.0 AND importance_weight <= 1.0),
                    tracking_keywords JSONB,
                    tracking_entities JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT true
                )
            """)
            
            # Story quality filters table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_quality_filters (
                    filter_id VARCHAR(50) PRIMARY KEY,
                    story_id VARCHAR(50) REFERENCES story_expectations(story_id),
                    filter_type VARCHAR(50) NOT NULL,
                    filter_config JSONB,
                    created_at TIMESTAMP DEFAULT NOW(),
                    is_active BOOLEAN DEFAULT true
                )
            """)
            
            # Story tracking results table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS story_tracking_results (
                    result_id SERIAL PRIMARY KEY,
                    story_id VARCHAR(50) REFERENCES story_expectations(story_id),
                    article_id INTEGER,
                    match_score DECIMAL(5,4),
                    match_reasons JSONB,
                    tracked_at TIMESTAMP DEFAULT NOW(),
                    is_enhanced BOOLEAN DEFAULT false
                )
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            
            self.logger.info("Story control database tables initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize story control database: {e}")
            raise
    
    def create_story_expectation(self, story_data: Dict[str, Any]) -> StoryExpectation:
        """
        Create a new story expectation with high-level control
        
        Args:
            story_data: Dictionary containing story configuration
            
        Returns:
            StoryExpectation object
        """
        try:
            story_id = story_data.get('story_id', f"story_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            expectation = StoryExpectation(
                story_id=story_id,
                name=story_data['name'],
                description=story_data.get('description', ''),
                priority_level=story_data.get('priority_level', 5),
                keywords=story_data.get('keywords', []),
                entities=story_data.get('entities', []),
                geographic_regions=story_data.get('geographic_regions', []),
                time_period=story_data.get('time_period'),
                quality_threshold=story_data.get('quality_threshold', 0.7),
                max_articles_per_day=story_data.get('max_articles_per_day', 100),
                auto_enhance=story_data.get('auto_enhance', True),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                is_active=True
            )
            
            # Store in database
            self._store_story_expectation(expectation)
            
            self.logger.info(f"Created story expectation: {expectation.name} (ID: {story_id})")
            return expectation
            
        except Exception as e:
            self.logger.error(f"Failed to create story expectation: {e}")
            raise
    
    def create_ukraine_russia_conflict_story(self) -> StoryExpectation:
        """
        Create a pre-configured story expectation for Ukraine-Russia conflict
        This is the example you mentioned - a high-priority, well-defined story
        """
        story_data = {
            'story_id': 'ukraine_russia_conflict_2024',
            'name': 'Ukraine-Russia Conflict 2024',
            'description': 'Comprehensive tracking of the ongoing conflict between Ukraine and Russia, including military developments, diplomatic efforts, humanitarian impact, and international responses.',
            'priority_level': 10,  # Highest priority
            'keywords': [
                'ukraine', 'russia', 'conflict', 'war', 'invasion', 'military', 'defense',
                'zelensky', 'putin', 'nato', 'european union', 'sanctions', 'humanitarian',
                'refugees', 'casualties', 'territory', 'ceasefire', 'peace talks',
                'weapons', 'aid', 'support', 'diplomacy', 'international law'
            ],
            'entities': [
                'Volodymyr Zelensky', 'Vladimir Putin', 'Ukraine', 'Russia', 'NATO',
                'European Union', 'United States', 'Germany', 'France', 'United Kingdom',
                'Donbas', 'Crimea', 'Kyiv', 'Moscow', 'Kremlin', 'Pentagon',
                'UN Security Council', 'International Criminal Court'
            ],
            'geographic_regions': [
                'Ukraine', 'Russia', 'Eastern Europe', 'NATO countries', 'EU countries'
            ],
            'time_period': (datetime(2022, 2, 24), None),  # From invasion start to present
            'quality_threshold': 0.8,  # High quality threshold
            'max_articles_per_day': 200,  # Allow more articles for this important story
            'auto_enhance': True  # Auto-trigger RAG enhancement
        }
        
        return self.create_story_expectation(story_data)
    
    def add_story_targets(self, story_id: str, targets: List[Dict[str, Any]]) -> List[StoryTarget]:
        """
        Add specific targets to track within a story
        
        Args:
            story_id: ID of the story
            targets: List of target configurations
            
        Returns:
            List of StoryTarget objects
        """
        try:
            story_targets = []
            
            for target_data in targets:
                target_id = target_data.get('target_id', f"target_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                
                target = StoryTarget(
                    target_id=target_id,
                    story_id=story_id,
                    target_type=target_data['target_type'],
                    target_name=target_data['target_name'],
                    target_description=target_data.get('target_description', ''),
                    importance_weight=target_data.get('importance_weight', 0.5),
                    tracking_keywords=target_data.get('tracking_keywords', []),
                    tracking_entities=target_data.get('tracking_entities', []),
                    created_at=datetime.now().isoformat(),
                    is_active=True
                )
                
                # Store in database
                self._store_story_target(target)
                story_targets.append(target)
            
            self.logger.info(f"Added {len(story_targets)} targets to story {story_id}")
            return story_targets
            
        except Exception as e:
            self.logger.error(f"Failed to add story targets: {e}")
            raise
    
    def add_ukraine_russia_targets(self, story_id: str) -> List[StoryTarget]:
        """
        Add specific targets for Ukraine-Russia conflict tracking
        """
        targets = [
            {
                'target_type': 'person',
                'target_name': 'Volodymyr Zelensky',
                'target_description': 'President of Ukraine, key figure in conflict',
                'importance_weight': 1.0,
                'tracking_keywords': ['zelensky', 'ukraine president', 'volodymyr'],
                'tracking_entities': ['Volodymyr Zelensky', 'President of Ukraine']
            },
            {
                'target_type': 'person',
                'target_name': 'Vladimir Putin',
                'target_description': 'President of Russia, key figure in conflict',
                'importance_weight': 1.0,
                'tracking_keywords': ['putin', 'russia president', 'vladimir'],
                'tracking_entities': ['Vladimir Putin', 'President of Russia']
            },
            {
                'target_type': 'organization',
                'target_name': 'NATO',
                'target_description': 'North Atlantic Treaty Organization, key military alliance',
                'importance_weight': 0.9,
                'tracking_keywords': ['nato', 'north atlantic treaty organization'],
                'tracking_entities': ['NATO', 'North Atlantic Treaty Organization']
            },
            {
                'target_type': 'event',
                'target_name': 'Military Operations',
                'target_description': 'Military operations, battles, and strategic movements',
                'importance_weight': 0.95,
                'tracking_keywords': ['military', 'battle', 'operation', 'offensive', 'defensive', 'attack', 'defense'],
                'tracking_entities': ['Ukrainian Armed Forces', 'Russian Armed Forces']
            },
            {
                'target_type': 'concept',
                'target_name': 'Diplomatic Efforts',
                'target_description': 'Peace talks, negotiations, and diplomatic initiatives',
                'importance_weight': 0.8,
                'tracking_keywords': ['diplomacy', 'peace talks', 'negotiations', 'ceasefire', 'treaty'],
                'tracking_entities': ['United Nations', 'European Union', 'International mediators']
            }
        ]
        
        return self.add_story_targets(story_id, targets)
    
    def add_quality_filters(self, story_id: str, filters: List[Dict[str, Any]]) -> List[StoryQualityFilter]:
        """
        Add quality control filters for story content
        
        Args:
            story_id: ID of the story
            filters: List of filter configurations
            
        Returns:
            List of StoryQualityFilter objects
        """
        try:
            story_filters = []
            
            for filter_data in filters:
                filter_id = filter_data.get('filter_id', f"filter_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                
                filter_obj = StoryQualityFilter(
                    filter_id=filter_id,
                    story_id=story_id,
                    filter_type=filter_data['filter_type'],
                    filter_config=filter_data['filter_config'],
                    created_at=datetime.now().isoformat(),
                    is_active=True
                )
                
                # Store in database
                self._store_story_quality_filter(filter_obj)
                story_filters.append(filter_obj)
            
            self.logger.info(f"Added {len(story_filters)} quality filters to story {story_id}")
            return story_filters
            
        except Exception as e:
            self.logger.error(f"Failed to add quality filters: {e}")
            raise
    
    def add_ukraine_russia_quality_filters(self, story_id: str) -> List[StoryQualityFilter]:
        """
        Add quality control filters for Ukraine-Russia conflict
        """
        filters = [
            {
                'filter_type': 'source_whitelist',
                'filter_config': {
                    'allowed_sources': [
                        'Reuters', 'Associated Press', 'BBC', 'CNN', 'New York Times',
                        'Washington Post', 'Guardian', 'Financial Times', 'Wall Street Journal',
                        'Politico', 'Foreign Policy', 'Defense News', 'Military Times',
                        'Ukraine Pravda', 'Kyiv Post', 'Interfax-Ukraine'
                    ]
                }
            },
            {
                'filter_type': 'source_blacklist',
                'filter_config': {
                    'blocked_sources': [
                        'RT News', 'Sputnik News', 'TASS', 'RIA Novosti',
                        'Conspiracy sites', 'Unverified social media'
                    ]
                }
            },
            {
                'filter_type': 'content_quality',
                'filter_config': {
                    'min_word_count': 200,
                    'max_word_count': 5000,
                    'require_quotes': True,
                    'require_sources': True,
                    'min_quality_score': 0.7
                }
            },
            {
                'filter_type': 'sentiment_range',
                'filter_config': {
                    'min_sentiment': -1.0,
                    'max_sentiment': 1.0,
                    'neutral_allowed': True
                }
            }
        ]
        
        return self.add_quality_filters(story_id, filters)
    
    def evaluate_article_for_story(self, article_id: int, story_id: str) -> Dict[str, Any]:
        """
        Evaluate if an article matches a story expectation
        
        Args:
            article_id: ID of the article to evaluate
            story_id: ID of the story to match against
            
        Returns:
            Dictionary containing match results
        """
        try:
            # Get story expectation
            expectation = self._get_story_expectation(story_id)
            if not expectation:
                return {'match': False, 'error': 'Story expectation not found'}
            
            # Get article data
            article = self._get_article(article_id)
            if not article:
                return {'match': False, 'error': 'Article not found'}
            
            # Evaluate match
            match_score = 0.0
            match_reasons = []
            
            # Check keywords
            keyword_matches = self._check_keyword_matches(article, expectation.keywords)
            if keyword_matches > 0:
                match_score += keyword_matches * 0.3
                match_reasons.append(f"Keyword matches: {keyword_matches}")
            
            # Check entities
            entity_matches = self._check_entity_matches(article, expectation.entities)
            if entity_matches > 0:
                match_score += entity_matches * 0.4
                match_reasons.append(f"Entity matches: {entity_matches}")
            
            # Check geographic regions
            geo_matches = self._check_geographic_matches(article, expectation.geographic_regions)
            if geo_matches > 0:
                match_score += geo_matches * 0.2
                match_reasons.append(f"Geographic matches: {geo_matches}")
            
            # Check quality threshold
            if article.get('quality_score', 0) < expectation.quality_threshold:
                return {'match': False, 'reason': 'Quality below threshold'}
            
            # Check time period
            if expectation.time_period:
                article_date = article.get('published_date')
                if article_date and not self._is_within_time_period(article_date, expectation.time_period):
                    return {'match': False, 'reason': 'Outside time period'}
            
            # Determine if article matches
            matches = match_score >= 0.5  # Minimum threshold for matching
            
            if matches:
                # Store tracking result
                self._store_tracking_result(story_id, article_id, match_score, match_reasons)
                
                # Auto-trigger enhancement if enabled
                if expectation.auto_enhance:
                    self._trigger_story_enhancement(story_id, article_id)
            
            return {
                'match': matches,
                'match_score': match_score,
                'match_reasons': match_reasons,
                'story_id': story_id,
                'article_id': article_id
            }
            
        except Exception as e:
            self.logger.error(f"Failed to evaluate article for story: {e}")
            return {'match': False, 'error': str(e)}
    
    def get_active_stories(self) -> List[StoryExpectation]:
        """Get all active story expectations"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT story_id, name, description, priority_level, keywords, entities,
                       geographic_regions, time_period_start, time_period_end,
                       quality_threshold, max_articles_per_day, auto_enhance,
                       created_at, updated_at, is_active
                FROM story_expectations
                WHERE is_active = true
                ORDER BY priority_level DESC, created_at DESC
            """)
            
            stories = []
            for row in cur.fetchall():
                story = StoryExpectation(
                    story_id=row[0],
                    name=row[1],
                    description=row[2],
                    priority_level=row[3],
                    keywords=row[4] or [],
                    entities=row[5] or [],
                    geographic_regions=row[6] or [],
                    time_period=(row[7], row[8]) if row[7] else None,
                    quality_threshold=float(row[9]),
                    max_articles_per_day=row[10],
                    auto_enhance=row[11],
                    created_at=row[12].isoformat(),
                    updated_at=row[13].isoformat(),
                    is_active=row[14]
                )
                stories.append(story)
            
            cur.close()
            conn.close()
            
            return stories
            
        except Exception as e:
            self.logger.error(f"Failed to get active stories: {e}")
            return []
    
    def _store_story_expectation(self, expectation: StoryExpectation):
        """Store story expectation in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO story_expectations 
                (story_id, name, description, priority_level, keywords, entities,
                 geographic_regions, time_period_start, time_period_end,
                 quality_threshold, max_articles_per_day, auto_enhance,
                 created_at, updated_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (story_id) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                priority_level = EXCLUDED.priority_level,
                keywords = EXCLUDED.keywords,
                entities = EXCLUDED.entities,
                geographic_regions = EXCLUDED.geographic_regions,
                time_period_start = EXCLUDED.time_period_start,
                time_period_end = EXCLUDED.time_period_end,
                quality_threshold = EXCLUDED.quality_threshold,
                max_articles_per_day = EXCLUDED.max_articles_per_day,
                auto_enhance = EXCLUDED.auto_enhance,
                updated_at = EXCLUDED.updated_at,
                is_active = EXCLUDED.is_active
            """, (
                expectation.story_id, expectation.name, expectation.description,
                expectation.priority_level, json.dumps(expectation.keywords),
                json.dumps(expectation.entities), json.dumps(expectation.geographic_regions),
                expectation.time_period[0] if expectation.time_period else None,
                expectation.time_period[1] if expectation.time_period else None,
                expectation.quality_threshold, expectation.max_articles_per_day,
                expectation.auto_enhance, expectation.created_at, expectation.updated_at,
                expectation.is_active
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to store story expectation: {e}")
            raise
    
    def _store_story_target(self, target: StoryTarget):
        """Store story target in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO story_targets 
                (target_id, story_id, target_type, target_name, target_description,
                 importance_weight, tracking_keywords, tracking_entities,
                 created_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (target_id) DO UPDATE SET
                story_id = EXCLUDED.story_id,
                target_type = EXCLUDED.target_type,
                target_name = EXCLUDED.target_name,
                target_description = EXCLUDED.target_description,
                importance_weight = EXCLUDED.importance_weight,
                tracking_keywords = EXCLUDED.tracking_keywords,
                tracking_entities = EXCLUDED.tracking_entities,
                is_active = EXCLUDED.is_active
            """, (
                target.target_id, target.story_id, target.target_type,
                target.target_name, target.target_description, target.importance_weight,
                json.dumps(target.tracking_keywords), json.dumps(target.tracking_entities),
                target.created_at, target.is_active
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to store story target: {e}")
            raise
    
    def _store_story_quality_filter(self, filter_obj: StoryQualityFilter):
        """Store story quality filter in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO story_quality_filters 
                (filter_id, story_id, filter_type, filter_config, created_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (filter_id) DO UPDATE SET
                story_id = EXCLUDED.story_id,
                filter_type = EXCLUDED.filter_type,
                filter_config = EXCLUDED.filter_config,
                is_active = EXCLUDED.is_active
            """, (
                filter_obj.filter_id, filter_obj.story_id, filter_obj.filter_type,
                json.dumps(filter_obj.filter_config), filter_obj.created_at,
                filter_obj.is_active
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to store story quality filter: {e}")
            raise
    
    def _store_tracking_result(self, story_id: str, article_id: int, match_score: float, match_reasons: List[str]):
        """Store story tracking result in database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO story_tracking_results 
                (story_id, article_id, match_score, match_reasons, tracked_at, is_enhanced)
                VALUES (%s, %s, %s, %s, NOW(), false)
            """, (story_id, article_id, match_score, json.dumps(match_reasons)))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            self.logger.error(f"Failed to store tracking result: {e}")
            raise
    
    def _get_story_expectation(self, story_id: str) -> Optional[StoryExpectation]:
        """Get story expectation from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT story_id, name, description, priority_level, keywords, entities,
                       geographic_regions, time_period_start, time_period_end,
                       quality_threshold, max_articles_per_day, auto_enhance,
                       created_at, updated_at, is_active
                FROM story_expectations
                WHERE story_id = %s AND is_active = true
            """, (story_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            story = StoryExpectation(
                story_id=row[0],
                name=row[1],
                description=row[2],
                priority_level=row[3],
                keywords=row[4] or [],
                entities=row[5] or [],
                geographic_regions=row[6] or [],
                time_period=(row[7], row[8]) if row[7] else None,
                quality_threshold=float(row[9]),
                max_articles_per_day=row[10],
                auto_enhance=row[11],
                created_at=row[12].isoformat(),
                updated_at=row[13].isoformat(),
                is_active=row[14]
            )
            
            cur.close()
            conn.close()
            
            return story
            
        except Exception as e:
            self.logger.error(f"Failed to get story expectation: {e}")
            return None
    
    def _get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get article from database"""
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, title, content, summary, source, category, published_date,
                       quality_score, sentiment_score, url
                FROM articles
                WHERE id = %s
            """, (article_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
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
            
            cur.close()
            conn.close()
            
            return article
            
        except Exception as e:
            self.logger.error(f"Failed to get article: {e}")
            return None
    
    def _check_keyword_matches(self, article: Dict[str, Any], keywords: List[str]) -> int:
        """Check how many keywords match in the article"""
        if not keywords:
            return 0
        
        text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}".lower()
        matches = 0
        
        for keyword in keywords:
            if keyword.lower() in text:
                matches += 1
        
        return matches
    
    def _check_entity_matches(self, article: Dict[str, Any], entities: List[str]) -> int:
        """Check how many entities match in the article"""
        if not entities:
            return 0
        
        text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}".lower()
        matches = 0
        
        for entity in entities:
            if entity.lower() in text:
                matches += 1
        
        return matches
    
    def _check_geographic_matches(self, article: Dict[str, Any], regions: List[str]) -> int:
        """Check how many geographic regions match in the article"""
        if not regions:
            return 0
        
        text = f"{article.get('title', '')} {article.get('content', '')} {article.get('summary', '')}".lower()
        matches = 0
        
        for region in regions:
            if region.lower() in text:
                matches += 1
        
        return matches
    
    def _is_within_time_period(self, article_date: datetime, time_period: Tuple[datetime, Optional[datetime]]) -> bool:
        """Check if article date is within the specified time period"""
        start_date, end_date = time_period
        
        if article_date < start_date:
            return False
        
        if end_date and article_date > end_date:
            return False
        
        return True
    
    def _trigger_story_enhancement(self, story_id: str, article_id: int):
        """Trigger RAG enhancement for a story"""
        try:
            # This will be implemented in the next step
            self.logger.info(f"Triggering story enhancement for story {story_id}, article {article_id}")
            # TODO: Implement RAG enhancement triggering
        except Exception as e:
            self.logger.error(f"Failed to trigger story enhancement: {e}")
