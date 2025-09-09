#!/usr/bin/env python3
"""
Migration Phase 2: Service Consolidation Script
Consolidates all services into 5 core services with standardized structure
"""

import os
import shutil
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_directory_structure():
    """Create new directory structure for consolidated services"""
    directories = [
        "api/controllers",
        "api/repositories", 
        "api/models",
        "api/tasks",
        "api/middleware",
        "tests/unit",
        "tests/integration",
        "tests/e2e"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        # Create __init__.py files
        init_file = f"{directory}/__init__.py"
        if not os.path.exists(init_file):
            with open(init_file, "w") as f:
                f.write(f'"""News Intelligence System v3.1.0 - {directory}"""\n')
        logger.info(f"Created directory: {directory}")

def create_article_service():
    """Create consolidated ArticleService"""
    article_service_content = '''"""
News Intelligence System v3.1.0 - Article Service
Consolidated article business logic
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from repositories.article_repository import ArticleRepository
from models.article_model import Article, ArticleCreate, ArticleUpdate, ProcessingStatus

logger = logging.getLogger(__name__)

class ArticleService:
    """Consolidated article service with all article business logic"""
    
    def __init__(self, repository: ArticleRepository):
        self.repository = repository
    
    async def get_articles(
        self, 
        page: int = 1, 
        limit: int = 20,
        source: Optional[str] = None,
        category: Optional[str] = None,
        processing_status: Optional[ProcessingStatus] = None
    ) -> Dict[str, Any]:
        """Get paginated list of articles with filters"""
        try:
            filters = {}
            if source:
                filters['source'] = source
            if category:
                filters['category'] = category
            if processing_status:
                filters['processing_status'] = processing_status
            
            articles = await self.repository.find_by_filters(filters, page, limit)
            total_count = await self.repository.count_by_filters(filters)
            
            return {
                'articles': articles,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            }
        except Exception as e:
            logger.error(f"Error getting articles: {e}")
            raise
    
    async def get_article(self, article_id: int) -> Optional[Article]:
        """Get single article by ID"""
        try:
            return await self.repository.find_by_id(article_id)
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            raise
    
    async def create_article(self, data: ArticleCreate) -> Article:
        """Create new article"""
        try:
            return await self.repository.create(data)
        except Exception as e:
            logger.error(f"Error creating article: {e}")
            raise
    
    async def update_article(self, article_id: int, data: ArticleUpdate) -> Article:
        """Update existing article"""
        try:
            return await self.repository.update(article_id, data)
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            raise
    
    async def delete_article(self, article_id: int) -> bool:
        """Delete article"""
        try:
            return await self.repository.delete(article_id)
        except Exception as e:
            logger.error(f"Error deleting article {article_id}: {e}")
            raise
    
    async def get_article_stats(self) -> Dict[str, Any]:
        """Get article statistics"""
        try:
            return await self.repository.get_stats()
        except Exception as e:
            logger.error(f"Error getting article stats: {e}")
            raise
    
    async def search_articles(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Article]:
        """Search articles by query"""
        try:
            return await self.repository.search(query, filters)
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            raise
'''
    
    with open("api/services/article_service.py", "w") as f:
        f.write(article_service_content)
    logger.info("Created ArticleService")

def create_feed_service():
    """Create consolidated FeedService"""
    feed_service_content = '''"""
News Intelligence System v3.1.0 - Feed Service
Consolidated RSS feed business logic
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from repositories.feed_repository import FeedRepository
from models.feed_model import Feed, FeedCreate, FeedUpdate, FeedTier, FeedStatus

logger = logging.getLogger(__name__)

class FeedService:
    """Consolidated feed service with all RSS feed business logic"""
    
    def __init__(self, repository: FeedRepository):
        self.repository = repository
    
    async def get_feeds(
        self, 
        active_only: bool = False,
        tier: Optional[FeedTier] = None,
        category: Optional[str] = None
    ) -> List[Feed]:
        """Get list of RSS feeds with optional filters"""
        try:
            filters = {}
            if active_only:
                filters['is_active'] = True
            if tier:
                filters['tier'] = tier
            if category:
                filters['category'] = category
            
            return await self.repository.find_by_filters(filters)
        except Exception as e:
            logger.error(f"Error getting feeds: {e}")
            raise
    
    async def get_feed(self, feed_id: int) -> Optional[Feed]:
        """Get single feed by ID"""
        try:
            return await self.repository.find_by_id(feed_id)
        except Exception as e:
            logger.error(f"Error getting feed {feed_id}: {e}")
            raise
    
    async def create_feed(self, data: FeedCreate) -> Feed:
        """Create new RSS feed"""
        try:
            # Check if URL already exists
            existing = await self.repository.find_by_url(data.url)
            if existing:
                raise ValueError("RSS feed with this URL already exists")
            
            return await self.repository.create(data)
        except Exception as e:
            logger.error(f"Error creating feed: {e}")
            raise
    
    async def update_feed(self, feed_id: int, data: FeedUpdate) -> Feed:
        """Update existing feed"""
        try:
            return await self.repository.update(feed_id, data)
        except Exception as e:
            logger.error(f"Error updating feed {feed_id}: {e}")
            raise
    
    async def delete_feed(self, feed_id: int) -> bool:
        """Delete feed"""
        try:
            return await self.repository.delete(feed_id)
        except Exception as e:
            logger.error(f"Error deleting feed {feed_id}: {e}")
            raise
    
    async def get_feed_stats(self) -> Dict[str, Any]:
        """Get feed statistics"""
        try:
            return await self.repository.get_stats()
        except Exception as e:
            logger.error(f"Error getting feed stats: {e}")
            raise
    
    async def test_feed(self, feed_id: int) -> Dict[str, Any]:
        """Test RSS feed connectivity"""
        try:
            feed = await self.repository.find_by_id(feed_id)
            if not feed:
                raise ValueError("Feed not found")
            
            # Test feed URL
            import requests
            response = requests.get(feed.url, timeout=30)
            
            return {
                'feed_id': feed_id,
                'url': feed.url,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'success': response.status_code == 200
            }
        except Exception as e:
            logger.error(f"Error testing feed {feed_id}: {e}")
            raise
'''
    
    with open("api/services/feed_service.py", "w") as f:
        f.write(feed_service_content)
    logger.info("Created FeedService")

def create_storyline_service():
    """Create consolidated StorylineService"""
    storyline_service_content = '''"""
News Intelligence System v3.1.0 - Storyline Service
Consolidated storyline business logic
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from repositories.storyline_repository import StorylineRepository
from models.storyline_model import Storyline, StorylineCreate, StorylineUpdate

logger = logging.getLogger(__name__)

class StorylineService:
    """Consolidated storyline service with all storyline business logic"""
    
    def __init__(self, repository: StorylineRepository):
        self.repository = repository
    
    async def get_storylines(
        self, 
        page: int = 1, 
        limit: int = 20,
        status: Optional[str] = None,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get paginated list of storylines with filters"""
        try:
            filters = {}
            if status:
                filters['status'] = status
            if category:
                filters['category'] = category
            
            storylines = await self.repository.find_by_filters(filters, page, limit)
            total_count = await self.repository.count_by_filters(filters)
            
            return {
                'storylines': storylines,
                'total_count': total_count,
                'page': page,
                'limit': limit,
                'total_pages': (total_count + limit - 1) // limit
            }
        except Exception as e:
            logger.error(f"Error getting storylines: {e}")
            raise
    
    async def get_storyline(self, storyline_id: int) -> Optional[Storyline]:
        """Get single storyline by ID"""
        try:
            return await self.repository.find_by_id(storyline_id)
        except Exception as e:
            logger.error(f"Error getting storyline {storyline_id}: {e}")
            raise
    
    async def create_storyline(self, data: StorylineCreate) -> Storyline:
        """Create new storyline"""
        try:
            return await self.repository.create(data)
        except Exception as e:
            logger.error(f"Error creating storyline: {e}")
            raise
    
    async def update_storyline(self, storyline_id: int, data: StorylineUpdate) -> Storyline:
        """Update existing storyline"""
        try:
            return await self.repository.update(storyline_id, data)
        except Exception as e:
            logger.error(f"Error updating storyline {storyline_id}: {e}")
            raise
    
    async def delete_storyline(self, storyline_id: int) -> bool:
        """Delete storyline"""
        try:
            return await self.repository.delete(storyline_id)
        except Exception as e:
            logger.error(f"Error deleting storyline {storyline_id}: {e}")
            raise
    
    async def get_storyline_articles(self, storyline_id: int) -> List[Dict[str, Any]]:
        """Get articles associated with storyline"""
        try:
            return await self.repository.get_articles(storyline_id)
        except Exception as e:
            logger.error(f"Error getting storyline articles: {e}")
            raise
    
    async def add_article_to_storyline(self, storyline_id: int, article_id: int) -> bool:
        """Add article to storyline"""
        try:
            return await self.repository.add_article(storyline_id, article_id)
        except Exception as e:
            logger.error(f"Error adding article to storyline: {e}")
            raise
    
    async def remove_article_from_storyline(self, storyline_id: int, article_id: int) -> bool:
        """Remove article from storyline"""
        try:
            return await self.repository.remove_article(storyline_id, article_id)
        except Exception as e:
            logger.error(f"Error removing article from storyline: {e}")
            raise
'''
    
    with open("api/services/storyline_service.py", "w") as f:
        f.write(storyline_service_content)
    logger.info("Created StorylineService")

def create_ml_service():
    """Create consolidated MLService"""
    ml_service_content = '''"""
News Intelligence System v3.1.0 - ML Service
Consolidated machine learning business logic
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from repositories.ml_repository import MLRepository
from models.article_model import Article

logger = logging.getLogger(__name__)

class MLService:
    """Consolidated ML service with all machine learning business logic"""
    
    def __init__(self, repository: MLRepository):
        self.repository = repository
    
    async def process_article(self, article_id: int) -> Dict[str, Any]:
        """Process article with full ML pipeline"""
        try:
            # Get article
            article = await self.repository.get_article(article_id)
            if not article:
                raise ValueError("Article not found")
            
            # Run ML processing
            results = {}
            
            # Entity extraction
            entities = await self._extract_entities(article.content)
            results['entities'] = entities
            
            # Sentiment analysis
            sentiment = await self._analyze_sentiment(article.content)
            results['sentiment'] = sentiment
            
            # Quality scoring
            quality = await self._score_quality(article)
            results['quality'] = quality
            
            # Readability analysis
            readability = await self._analyze_readability(article.content)
            results['readability'] = readability
            
            # Update article with results
            await self.repository.update_article_ml_data(article_id, results)
            
            return results
        except Exception as e:
            logger.error(f"Error processing article {article_id}: {e}")
            raise
    
    async def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        try:
            # Simple entity extraction (replace with actual ML model)
            entities = {
                'people': [],
                'organizations': [],
                'locations': [],
                'topics': []
            }
            
            # This would be replaced with actual ML model
            # For now, return empty results
            return entities
        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            raise
    
    async def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        try:
            # Simple sentiment analysis (replace with actual ML model)
            sentiment = {
                'score': 0.0,
                'label': 'neutral',
                'confidence': 0.5
            }
            
            # This would be replaced with actual ML model
            return sentiment
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            raise
    
    async def score_quality(self, article: Article) -> Dict[str, Any]:
        """Score article quality"""
        try:
            # Simple quality scoring (replace with actual ML model)
            quality = {
                'score': 0.5,
                'factors': {
                    'length': len(article.content) if article.content else 0,
                    'title_quality': len(article.title) if article.title else 0,
                    'source_reliability': 0.5
                }
            }
            
            # This would be replaced with actual ML model
            return quality
        except Exception as e:
            logger.error(f"Error scoring quality: {e}")
            raise
    
    async def analyze_readability(self, text: str) -> Dict[str, Any]:
        """Analyze text readability"""
        try:
            # Simple readability analysis (replace with actual ML model)
            readability = {
                'score': 0.5,
                'grade_level': 8,
                'complexity': 'medium'
            }
            
            # This would be replaced with actual ML model
            return readability
        except Exception as e:
            logger.error(f"Error analyzing readability: {e}")
            raise
    
    async def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Internal entity extraction method"""
        return await self.extract_entities(text)
    
    async def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Internal sentiment analysis method"""
        return await self.analyze_sentiment(text)
    
    async def _score_quality(self, article: Article) -> Dict[str, Any]:
        """Internal quality scoring method"""
        return await self.score_quality(article)
    
    async def _analyze_readability(self, text: str) -> Dict[str, Any]:
        """Internal readability analysis method"""
        return await self.analyze_readability(text)
'''
    
    with open("api/services/ml_service.py", "w") as f:
        f.write(ml_service_content)
    logger.info("Created MLService")

def create_health_service():
    """Create consolidated HealthService"""
    health_service_content = '''"""
News Intelligence System v3.1.0 - Health Service
Consolidated system health monitoring
"""

import logging
from typing import Dict, Any
from datetime import datetime
from repositories.health_repository import HealthRepository

logger = logging.getLogger(__name__)

class HealthService:
    """Consolidated health service with all system health monitoring"""
    
    def __init__(self, repository: HealthRepository):
        self.repository = repository
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health status"""
        try:
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'services': {}
            }
            
            # Check database health
            health_status['services']['database'] = await self._check_database()
            
            # Check Redis health
            health_status['services']['redis'] = await self._check_redis()
            
            # Check ML services health
            health_status['services']['ml_services'] = await self._check_ml_services()
            
            # Check background tasks health
            health_status['services']['background_tasks'] = await self._check_background_tasks()
            
            # Determine overall status
            all_healthy = all(
                service['status'] == 'healthy' 
                for service in health_status['services'].values()
            )
            
            health_status['status'] = 'healthy' if all_healthy else 'degraded'
            
            return health_status
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            return {
                'status': 'unhealthy',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e)
            }
    
    async def get_database_health(self) -> Dict[str, Any]:
        """Get database health status"""
        try:
            return await self._check_database()
        except Exception as e:
            logger.error(f"Error checking database health: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    async def get_redis_health(self) -> Dict[str, Any]:
        """Get Redis health status"""
        try:
            return await self._check_redis()
        except Exception as e:
            logger.error(f"Error checking Redis health: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    async def get_ml_services_health(self) -> Dict[str, Any]:
        """Get ML services health status"""
        try:
            return await self._check_ml_services()
        except Exception as e:
            logger.error(f"Error checking ML services health: {e}")
            return {'status': 'unhealthy', 'error': str(e)}
    
    async def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = datetime.utcnow()
            result = await self.repository.test_database_connection()
            end_time = datetime.utcnow()
            
            response_time = (end_time - start_time).total_seconds()
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'connection_count': result.get('connection_count', 0),
                'last_check': end_time.isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity and performance"""
        try:
            start_time = datetime.utcnow()
            result = await self.repository.test_redis_connection()
            end_time = datetime.utcnow()
            
            response_time = (end_time - start_time).total_seconds()
            
            return {
                'status': 'healthy',
                'response_time': response_time,
                'memory_usage': result.get('memory_usage', 0),
                'last_check': end_time.isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_ml_services(self) -> Dict[str, Any]:
        """Check ML services health"""
        try:
            # Check if ML models are loaded and responsive
            result = await self.repository.test_ml_services()
            
            return {
                'status': 'healthy',
                'models_loaded': result.get('models_loaded', 0),
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
    
    async def _check_background_tasks(self) -> Dict[str, Any]:
        """Check background tasks health"""
        try:
            result = await self.repository.test_background_tasks()
            
            return {
                'status': 'healthy',
                'active_tasks': result.get('active_tasks', 0),
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.utcnow().isoformat()
            }
'''
    
    with open("api/services/health_service.py", "w") as f:
        f.write(health_service_content)
    logger.info("Created HealthService")

def create_repository_layer():
    """Create repository layer files"""
    
    # Article Repository
    article_repo_content = '''"""
News Intelligence System v3.1.0 - Article Repository
Data access layer for articles
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.article_model import Article, ArticleCreate, ArticleUpdate

logger = logging.getLogger(__name__)

class ArticleRepository:
    """Repository for article data access"""
    
    def __init__(self, db):
        self.db = db
    
    async def find_by_filters(self, filters: Dict[str, Any], page: int = 1, limit: int = 20) -> List[Article]:
        """Find articles by filters with pagination"""
        try:
            query = "SELECT * FROM articles WHERE 1=1"
            params = {}
            offset = (page - 1) * limit
            
            if 'source' in filters:
                query += " AND source = :source"
                params['source'] = filters['source']
            
            if 'processing_status' in filters:
                query += " AND processing_status = :processing_status"
                params['processing_status'] = filters['processing_status']
            
            if 'category' in filters:
                query += " AND category = :category"
                params['category'] = filters['category']
            
            query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset
            
            result = await self.db.fetch_all(query, params)
            return [Article(**row) for row in result]
        except Exception as e:
            logger.error(f"Error finding articles by filters: {e}")
            raise
    
    async def find_by_id(self, article_id: int) -> Optional[Article]:
        """Find article by ID"""
        try:
            query = "SELECT * FROM articles WHERE id = :id"
            result = await self.db.fetch_one(query, {'id': article_id})
            return Article(**result) if result else None
        except Exception as e:
            logger.error(f"Error finding article by ID: {e}")
            raise
    
    async def create(self, data: ArticleCreate) -> Article:
        """Create new article"""
        try:
            query = """
                INSERT INTO articles (title, content, url, source, processing_status, created_at, updated_at)
                VALUES (:title, :content, :url, :source, :processing_status, :created_at, :updated_at)
                RETURNING *
            """
            params = data.dict()
            params['created_at'] = datetime.utcnow()
            params['updated_at'] = datetime.utcnow()
            
            result = await self.db.fetch_one(query, params)
            return Article(**result)
        except Exception as e:
            logger.error(f"Error creating article: {e}")
            raise
    
    async def update(self, article_id: int, data: ArticleUpdate) -> Article:
        """Update article"""
        try:
            query = """
                UPDATE articles 
                SET title = :title, content = :content, url = :url, source = :source, 
                    processing_status = :processing_status, updated_at = :updated_at
                WHERE id = :id
                RETURNING *
            """
            params = data.dict()
            params['id'] = article_id
            params['updated_at'] = datetime.utcnow()
            
            result = await self.db.fetch_one(query, params)
            return Article(**result)
        except Exception as e:
            logger.error(f"Error updating article: {e}")
            raise
    
    async def delete(self, article_id: int) -> bool:
        """Delete article"""
        try:
            query = "DELETE FROM articles WHERE id = :id"
            result = await self.db.execute(query, {'id': article_id})
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting article: {e}")
            raise
    
    async def count_by_filters(self, filters: Dict[str, Any]) -> int:
        """Count articles by filters"""
        try:
            query = "SELECT COUNT(*) FROM articles WHERE 1=1"
            params = {}
            
            if 'source' in filters:
                query += " AND source = :source"
                params['source'] = filters['source']
            
            if 'processing_status' in filters:
                query += " AND processing_status = :processing_status"
                params['processing_status'] = filters['processing_status']
            
            result = await self.db.fetch_one(query, params)
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error counting articles: {e}")
            raise
    
    async def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[Article]:
        """Search articles by text query"""
        try:
            search_query = """
                SELECT * FROM articles 
                WHERE to_tsvector('english', title || ' ' || content) @@ plainto_tsquery('english', :query)
                ORDER BY ts_rank(to_tsvector('english', title || ' ' || content), plainto_tsquery('english', :query)) DESC
            """
            params = {'query': query}
            
            result = await self.db.fetch_all(search_query, params)
            return [Article(**row) for row in result]
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            raise
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get article statistics"""
        try:
            stats_query = """
                SELECT 
                    COUNT(*) as total_articles,
                    COUNT(CASE WHEN processing_status = 'processed' THEN 1 END) as processed_articles,
                    COUNT(CASE WHEN processing_status = 'processing' THEN 1 END) as processing_articles,
                    COUNT(CASE WHEN processing_status = 'error' THEN 1 END) as error_articles,
                    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as articles_last_24h
                FROM articles
            """
            result = await self.db.fetch_one(stats_query)
            
            return {
                'total_articles': result[0],
                'processed_articles': result[1],
                'processing_articles': result[2],
                'error_articles': result[3],
                'articles_last_24h': result[4]
            }
        except Exception as e:
            logger.error(f"Error getting article stats: {e}")
            raise
'''
    
    with open("api/repositories/article_repository.py", "w") as f:
        f.write(article_repo_content)
    logger.info("Created ArticleRepository")

def create_model_layer():
    """Create standardized model files"""
    
    # Base Model
    base_model_content = '''"""
News Intelligence System v3.1.0 - Base Model
Base model class with common functionality
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class BaseModel(BaseModel):
    """Base model with common fields and configuration"""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
'''
    
    with open("api/models/base_model.py", "w") as f:
        f.write(base_model_content)
    logger.info("Created BaseModel")

def update_main_app():
    """Update main application to use new services"""
    main_app_content = '''"""
News Intelligence System v3.1.0 - Main Application
Simplified FastAPI application with consolidated services
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from controllers.article_controller import ArticleController
from controllers.feed_controller import FeedController
from controllers.storyline_controller import StorylineController
from controllers.health_controller import HealthController
from controllers.admin_controller import AdminController

from services.article_service import ArticleService
from services.feed_service import FeedService
from services.storyline_service import StorylineService
from services.ml_service import MLService
from services.health_service import HealthService

from repositories.article_repository import ArticleRepository
from repositories.feed_repository import FeedRepository
from repositories.storyline_repository import StorylineRepository
from repositories.ml_repository import MLRepository
from repositories.health_repository import HealthRepository

from database.connection import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global service instances
article_service = None
feed_service = None
storyline_service = None
ml_service = None
health_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global article_service, feed_service, storyline_service, ml_service, health_service
    
    # Startup
    logger.info("Starting News Intelligence System v3.1.0")
    
    try:
        # Initialize repositories
        db = next(get_db())
        article_repo = ArticleRepository(db)
        feed_repo = FeedRepository(db)
        storyline_repo = StorylineRepository(db)
        ml_repo = MLRepository(db)
        health_repo = HealthRepository(db)
        
        # Initialize services
        article_service = ArticleService(article_repo)
        feed_service = FeedService(feed_repo)
        storyline_service = StorylineService(storyline_repo)
        ml_service = MLService(ml_repo)
        health_service = HealthService(health_repo)
        
        # Store services in app state
        app.state.article_service = article_service
        app.state.feed_service = feed_service
        app.state.storyline_service = storyline_service
        app.state.ml_service = ml_service
        app.state.health_service = health_service
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System v3.1.0")

# Create FastAPI app
app = FastAPI(
    title="News Intelligence System v3.1.0",
    description="Simplified news intelligence system with consolidated services",
    version="3.1.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize controllers
article_controller = ArticleController(article_service)
feed_controller = FeedController(feed_service)
storyline_controller = StorylineController(storyline_service)
health_controller = HealthController(health_service)
admin_controller = AdminController(article_service, feed_service, storyline_service, ml_service)

# Include routers
app.include_router(article_controller.router, prefix="/api/v1")
app.include_router(feed_controller.router, prefix="/api/v1")
app.include_router(storyline_controller.router, prefix="/api/v1")
app.include_router(health_controller.router, prefix="/api/v1")
app.include_router(admin_controller.router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "News Intelligence System v3.1.0",
        "status": "running",
        "version": "3.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
    
    with open("api/main.py", "w") as f:
        f.write(main_app_content)
    logger.info("Updated main application")

def main():
    """Main migration function"""
    logger.info("Starting Phase 2: Service Consolidation")
    
    try:
        # Create directory structure
        create_directory_structure()
        
        # Create core services
        create_article_service()
        create_feed_service()
        create_storyline_service()
        create_ml_service()
        create_health_service()
        
        # Create repository layer
        create_repository_layer()
        
        # Create model layer
        create_model_layer()
        
        # Update main application
        update_main_app()
        
        logger.info("Phase 2: Service Consolidation completed successfully!")
        
    except Exception as e:
        logger.error(f"Phase 2 migration failed: {e}")
        raise

if __name__ == "__main__":
    main()

