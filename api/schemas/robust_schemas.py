"""
News Intelligence System v3.1.0 - Robust API Schemas
Production-ready schemas aligned with database requirements
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum

# Base Response Schema
class APIResponse(BaseModel):
    success: bool = Field(..., description="Request success status")
    data: Optional[Any] = Field(None, description="Response data")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error message if any")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

# Article Schemas (aligned with articles table)
class ArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000, description="Article title")
    content: Optional[str] = Field(None, description="Article content")
    url: Optional[str] = Field(None, description="Article URL")
    source: Optional[str] = Field(None, description="Article source")
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    category: Optional[str] = Field(None, description="Article category")
    tags: Optional[List[str]] = Field(default=[], description="Article tags")
    language: str = Field(default="en", max_length=10, description="Article language")

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=1000)
    content: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    language: Optional[str] = Field(None, max_length=10)

class Article(ArticleBase):
    id: str = Field(..., description="Article ID")
    status: str = Field(default="active", description="Article status")
    sentiment_score: Optional[float] = Field(None, ge=-1, le=1, description="Sentiment score")
    entities: Optional[Dict[str, Any]] = Field(None, description="Extracted entities")
    readability_score: Optional[float] = Field(None, ge=0, le=100, description="Readability score")
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="Quality score")
    processing_status: str = Field(default="pending", description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processing_completed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    ml_data: Optional[Dict[str, Any]] = Field(None, description="ML processing data")
    word_count: int = Field(default=0, ge=0, description="Word count")
    reading_time: int = Field(default=0, ge=0, description="Reading time in minutes")

class ArticleSearch(BaseModel):
    query: Optional[str] = Field(None, description="Search query")
    source: Optional[str] = Field(None, description="Filter by source")
    category: Optional[str] = Field(None, description="Filter by category")
    date_from: Optional[datetime] = Field(None, description="Start date filter")
    date_to: Optional[datetime] = Field(None, description="End date filter")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    min_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Minimum quality score")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")

class ArticleList(BaseModel):
    items: List[Article] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total pages")

# Story Timeline Schemas (aligned with story_timelines table)
class StoryTimelineBase(BaseModel):
    story_id: str = Field(..., min_length=1, max_length=255, description="Story identifier")
    title: str = Field(..., min_length=1, max_length=500, description="Story title")
    summary: Optional[str] = Field(None, description="Story summary")
    status: str = Field(default="developing", description="Story status")
    sentiment: str = Field(default="neutral", description="Story sentiment")
    impact_level: str = Field(default="medium", description="Impact level")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    sources_count: int = Field(default=0, ge=0, description="Number of sources")

class StoryTimelineCreate(StoryTimelineBase):
    pass

class StoryTimelineUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    summary: Optional[str] = None
    status: Optional[str] = None
    sentiment: Optional[str] = None
    impact_level: Optional[str] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    sources_count: Optional[int] = Field(None, ge=0)

class StoryTimeline(StoryTimelineBase):
    id: int = Field(..., description="Timeline ID")
    last_updated: datetime = Field(..., description="Last update timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# Story Consolidation Schemas (aligned with story_consolidations table)
class StoryConsolidationBase(BaseModel):
    story_timeline_id: Optional[int] = Field(None, description="Associated timeline ID")
    headline: str = Field(..., min_length=1, max_length=500, description="Consolidated headline")
    consolidated_summary: str = Field(..., min_length=1, description="Consolidated summary")
    key_points: Optional[List[str]] = Field(default=[], description="Key points")
    professional_report: Optional[str] = Field(None, description="Professional report")
    executive_summary: Optional[str] = Field(None, description="Executive summary")
    recommendations: Optional[List[str]] = Field(default=[], description="Recommendations")
    ai_analysis: Optional[Dict[str, Any]] = Field(default={}, description="AI analysis data")
    sources: Optional[List[Dict[str, Any]]] = Field(default=[], description="Source information")

class StoryConsolidationCreate(StoryConsolidationBase):
    pass

class StoryConsolidationUpdate(BaseModel):
    headline: Optional[str] = Field(None, min_length=1, max_length=500)
    consolidated_summary: Optional[str] = Field(None, min_length=1)
    key_points: Optional[List[str]] = None
    professional_report: Optional[str] = None
    executive_summary: Optional[str] = None
    recommendations: Optional[List[str]] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    sources: Optional[List[Dict[str, Any]]] = None

class StoryConsolidation(StoryConsolidationBase):
    id: int = Field(..., description="Consolidation ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# RSS Feed Schemas (aligned with rss_feeds table)
class RSSFeedBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Feed name")
    url: str = Field(..., description="Feed URL")
    description: Optional[str] = Field(None, description="Feed description")
    category: Optional[str] = Field(None, description="Feed category")
    is_active: bool = Field(default=True, description="Feed active status")

class RSSFeedCreate(RSSFeedBase):
    pass

class RSSFeedUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None

class RSSFeed(RSSFeedBase):
    id: int = Field(..., description="Feed ID")
    last_checked: Optional[datetime] = Field(None, description="Last check timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_success: Optional[datetime] = Field(None, description="Last successful fetch")
    last_error: Optional[str] = Field(None, description="Last error message")
    error_count: int = Field(default=0, ge=0, description="Error count")
    failure_count: int = Field(default=0, ge=0, description="Failure count")
    article_count: int = Field(default=0, ge=0, description="Article count")
    last_article_date: Optional[datetime] = Field(None, description="Last article date")
    error_message: Optional[str] = Field(None, description="Current error message")

# AI Analysis Schemas (aligned with ai_analysis table)
class AIAnalysisBase(BaseModel):
    story_timeline_id: Optional[int] = Field(None, description="Associated timeline ID")
    analysis_type: str = Field(..., min_length=1, max_length=50, description="Analysis type")
    analysis_data: Dict[str, Any] = Field(..., description="Analysis data")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Analysis confidence")
    model_used: Optional[str] = Field(None, max_length=100, description="Model used")
    processing_time_ms: Optional[int] = Field(None, ge=0, description="Processing time in milliseconds")

class AIAnalysisCreate(AIAnalysisBase):
    pass

class AIAnalysis(AIAnalysisBase):
    id: int = Field(..., description="Analysis ID")
    created_at: datetime = Field(..., description="Creation timestamp")

# Health Check Schemas
class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"

class HealthCheck(BaseModel):
    status: HealthStatus = Field(..., description="Health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    services: Dict[str, HealthStatus] = Field(..., description="Service statuses")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")

# Statistics Schemas
class ArticleStats(BaseModel):
    total_articles: int = Field(..., ge=0, description="Total articles")
    articles_by_source: Dict[str, int] = Field(..., description="Articles by source")
    articles_by_category: Dict[str, int] = Field(..., description="Articles by category")
    avg_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Average quality score")
    processing_success_rate: Optional[float] = Field(None, ge=0, le=1, description="Processing success rate")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")

# Search Schemas
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Search filters")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")

class SearchResult(BaseModel):
    items: List[Article] = Field(..., description="Search results")
    total: int = Field(..., ge=0, description="Total results")
    query: str = Field(..., description="Search query")
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")
    page: int = Field(..., ge=1, description="Current page")
    limit: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=1, description="Total pages")
