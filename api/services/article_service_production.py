"""
News Intelligence System v3.1.0 - Production Article Service
Robust article management service with full database integration
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from schemas.robust_schemas import (
    Article, ArticleCreate, ArticleUpdate, ArticleSearch, 
    ArticleList, ArticleStats
)
import logging

logger = logging.getLogger(__name__)

class ArticleService:
    def __init__(self, db: Session):
        self.db = db

    async def get_articles(
        self, 
        page: int = 1, 
        limit: int = 20, 
        source: Optional[str] = None,
        category: Optional[str] = None,
        status: Optional[str] = None
    ) -> ArticleList:
        """Get paginated list of articles with filters"""
        try:
            query = self.db.query(Article)
            
            # Apply filters
            if source:
                query = query.filter(Article.source == source)
            if category:
                query = query.filter(Article.category == category)
            if status:
                query = query.filter(Article.status == status)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (page - 1) * limit
            articles = query.offset(offset).limit(limit).all()
            
            # Calculate pages
            pages = (total + limit - 1) // limit
            
            return ArticleList(
                items=articles,
                total=total,
                page=page,
                limit=limit,
                pages=pages
            )
        except Exception as e:
            logger.error(f"Error getting articles: {e}")
            raise

    async def get_article(self, article_id: str) -> Optional[Article]:
        """Get specific article by ID"""
        try:
            return self.db.query(Article).filter(Article.id == article_id).first()
        except Exception as e:
            logger.error(f"Error getting article {article_id}: {e}")
            raise

    async def create_article(self, article_data: ArticleCreate) -> Article:
        """Create new article"""
        try:
            article = Article(**article_data.dict())
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)
            return article
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating article: {e}")
            raise

    async def update_article(self, article_id: str, article_data: ArticleUpdate) -> Optional[Article]:
        """Update existing article"""
        try:
            article = self.db.query(Article).filter(Article.id == article_id).first()
            if not article:
                return None
            
            update_data = article_data.dict(exclude_unset=True)
            for field, value in update_data.items():
                setattr(article, field, value)
            
            self.db.commit()
            self.db.refresh(article)
            return article
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating article {article_id}: {e}")
            raise

    async def delete_article(self, article_id: str) -> bool:
        """Delete article"""
        try:
            article = self.db.query(Article).filter(Article.id == article_id).first()
            if not article:
                return False
            
            self.db.delete(article)
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deleting article {article_id}: {e}")
            raise

    async def search_articles(self, search_data: ArticleSearch) -> ArticleList:
        """Search articles with advanced filters"""
        try:
            query = self.db.query(Article)
            
            # Apply search filters
            if search_data.query:
                query = query.filter(
                    or_(
                        Article.title.ilike(f"%{search_data.query}%"),
                        Article.content.ilike(f"%{search_data.query}%")
                    )
                )
            
            if search_data.source:
                query = query.filter(Article.source == search_data.source)
            
            if search_data.category:
                query = query.filter(Article.category == search_data.category)
            
            if search_data.date_from:
                query = query.filter(Article.published_at >= search_data.date_from)
            
            if search_data.date_to:
                query = query.filter(Article.published_at <= search_data.date_to)
            
            if search_data.tags:
                for tag in search_data.tags:
                    query = query.filter(Article.tags.contains([tag]))
            
            if search_data.min_quality_score is not None:
                query = query.filter(Article.quality_score >= search_data.min_quality_score)
            
            # Get total count
            total = query.count()
            
            # Apply pagination
            offset = (search_data.page - 1) * search_data.limit
            articles = query.offset(offset).limit(search_data.limit).all()
            
            # Calculate pages
            pages = (total + search_data.limit - 1) // search_data.limit
            
            return ArticleList(
                items=articles,
                total=total,
                page=search_data.page,
                limit=search_data.limit,
                pages=pages
            )
        except Exception as e:
            logger.error(f"Error searching articles: {e}")
            raise

    async def get_sources(self) -> List[str]:
        """Get list of article sources"""
        try:
            sources = self.db.query(Article.source).filter(
                Article.source.isnot(None)
            ).distinct().all()
            return [source[0] for source in sources if source[0]]
        except Exception as e:
            logger.error(f"Error getting sources: {e}")
            raise

    async def get_categories(self) -> List[str]:
        """Get list of article categories"""
        try:
            categories = self.db.query(Article.category).filter(
                Article.category.isnot(None)
            ).distinct().all()
            return [category[0] for category in categories if category[0]]
        except Exception as e:
            logger.error(f"Error getting categories: {e}")
            raise

    async def analyze_article(self, article_id: str) -> Dict[str, Any]:
        """Trigger AI analysis for article"""
        try:
            article = await self.get_article(article_id)
            if not article:
                raise ValueError("Article not found")
            
            # Placeholder for AI analysis logic
            analysis_result = {
                "article_id": article_id,
                "sentiment_score": 0.5,
                "entities": [],
                "summary": "AI analysis placeholder",
                "processing_time_ms": 1000
            }
            
            return analysis_result
        except Exception as e:
            logger.error(f"Error analyzing article {article_id}: {e}")
            raise

    async def get_related_articles(self, article_id: str, limit: int = 10) -> List[Article]:
        """Get related articles"""
        try:
            article = await self.get_article(article_id)
            if not article:
                return []
            
            # Simple related articles logic based on category and tags
            query = self.db.query(Article).filter(Article.id != article_id)
            
            if article.category:
                query = query.filter(Article.category == article.category)
            
            if article.tags:
                for tag in article.tags:
                    query = query.filter(Article.tags.contains([tag]))
            
            return query.limit(limit).all()
        except Exception as e:
            logger.error(f"Error getting related articles for {article_id}: {e}")
            raise

    async def get_stats(self) -> ArticleStats:
        """Get article statistics"""
        try:
            total_articles = self.db.query(Article).count()
            
            # Articles by source
            sources_query = self.db.query(
                Article.source, func.count(Article.id)
            ).filter(
                Article.source.isnot(None)
            ).group_by(Article.source)
            articles_by_source = {row[0]: row[1] for row in sources_query.all()}
            
            # Articles by category
            categories_query = self.db.query(
                Article.category, func.count(Article.id)
            ).filter(
                Article.category.isnot(None)
            ).group_by(Article.category)
            articles_by_category = {row[0]: row[1] for row in categories_query.all()}
            
            # Average quality score
            avg_quality = self.db.query(func.avg(Article.quality_score)).scalar()
            
            # Processing success rate
            total_processed = self.db.query(Article).filter(
                Article.processing_status == "completed"
            ).count()
            success_rate = total_processed / total_articles if total_articles > 0 else 0
            
            return ArticleStats(
                total_articles=total_articles,
                articles_by_source=articles_by_source,
                articles_by_category=articles_by_category,
                avg_quality_score=float(avg_quality) if avg_quality else None,
                processing_success_rate=success_rate
            )
        except Exception as e:
            logger.error(f"Error getting article stats: {e}")
            raise
