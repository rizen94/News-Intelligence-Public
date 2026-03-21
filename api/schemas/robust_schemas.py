"""
News Intelligence System v3.0 - Robust API Schemas
Production-ready schemas aligned with database requirements
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# Base Response Schema - Standardized for all API endpoints
class APIResponse(BaseModel):
    success: bool = Field(..., description="Request success status")
    data: Any | None = Field(None, description="Response data")
    message: str = Field(..., description="Response message")
    error: str | None = Field(None, description="Error message if any")
    meta: dict[str, Any] | None = Field(None, description="Additional metadata")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# Pagination metadata for list endpoints
class PaginationMeta(BaseModel):
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


# Filter metadata
class FilterMeta(BaseModel):
    applied_filters: dict[str, Any] = Field(default_factory=dict, description="Applied filters")
    available_filters: dict[str, list[str]] = Field(
        default_factory=dict, description="Available filter options"
    )


# Standardized error response
class ErrorResponse(BaseModel):
    success: bool = Field(False, description="Always false for errors")
    data: Any | None = Field(None, description="Null for errors")
    error: str = Field(..., description="Error message")
    error_code: str | None = Field(None, description="Error code for programmatic handling")
    details: dict[str, Any] | None = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}


# Utility functions for creating standardized responses
def create_success_response(
    data: Any, message: str = None, meta: dict[str, Any] = None
) -> APIResponse:
    """Create a standardized success response"""
    return APIResponse(success=True, data=data, message=message or "Request successful", meta=meta)


def create_error_response(
    error: str, error_code: str = None, details: dict[str, Any] = None
) -> ErrorResponse:
    """Create a standardized error response"""
    return ErrorResponse(error=error, error_code=error_code, details=details)


def create_paginated_response(
    data: list[Any],
    page: int,
    per_page: int,
    total: int,
    message: str = None,
    filters: FilterMeta = None,
) -> APIResponse:
    """Create a standardized paginated response"""
    total_pages = (total + per_page - 1) // per_page  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    pagination = PaginationMeta(
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev,
    )

    meta = {"pagination": pagination.dict()}
    if filters:
        meta["filters"] = filters.dict()

    return APIResponse(
        success=True, data=data, message=message or f"Retrieved {len(data)} items", meta=meta
    )


# Article Schemas (aligned with articles table)
class ArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=1000, description="Article title")
    content: str | None = Field(None, description="Article content")
    url: str | None = Field(None, description="Article URL")
    source: str | None = Field(None, description="Article source")
    published_at: datetime | None = Field(None, description="Publication timestamp")
    category: str | None = Field(None, description="Article category")
    tags: list[str] | None = Field(default=[], description="Article tags")
    language: str = Field(default="en", max_length=10, description="Article language")


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=1000)
    content: str | None = None
    url: str | None = None
    source: str | None = None
    published_at: datetime | None = None
    category: str | None = None
    tags: list[str] | None = None
    language: str | None = Field(None, max_length=10)


class Article(ArticleBase):
    id: str = Field(..., description="Article ID")
    status: str = Field(default="active", description="Article status")
    sentiment_score: float | None = Field(None, ge=-1, le=1, description="Sentiment score")
    entities: dict[str, Any] | None = Field(None, description="Extracted entities")
    readability_score: float | None = Field(None, ge=0, le=100, description="Readability score")
    quality_score: float | None = Field(None, ge=0, le=1, description="Quality score")
    processing_status: str = Field(default="pending", description="Processing status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processing_completed_at: datetime | None = Field(
        None, description="Processing completion timestamp"
    )
    summary: str | None = Field(None, description="AI-generated summary")
    ml_data: dict[str, Any] | None = Field(None, description="ML processing data")
    word_count: int = Field(default=0, ge=0, description="Word count")
    reading_time: int = Field(default=0, ge=0, description="Reading time in minutes")


class ArticleSearch(BaseModel):
    query: str | None = Field(None, description="Search query")
    source: str | None = Field(None, description="Filter by source")
    category: str | None = Field(None, description="Filter by category")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    tags: list[str] | None = Field(None, description="Filter by tags")
    min_quality_score: float | None = Field(None, ge=0, le=1, description="Minimum quality score")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")


class ArticleList(BaseModel):
    items: list[Article] = Field(..., description="List of articles")
    total: int = Field(..., description="Total number of articles")
    page: int = Field(..., description="Current page")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total pages")


# Story Timeline Schemas (aligned with story_threads table)
class StoryTimelineBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Story title")
    summary: str | None = Field(None, description="Story summary")
    status: str = Field(default="active", description="Story status")
    priority_level_id: int | None = Field(None, description="Priority level ID")


class StoryTimelineCreate(StoryTimelineBase):
    pass


class StoryTimelineUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    summary: str | None = None
    status: str | None = None
    priority_level_id: int | None = None


class StoryTimeline(StoryTimelineBase):
    id: int = Field(..., description="Story thread ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# Storyline-Article Relationship Schema
class StorylineArticleBase(BaseModel):
    storyline_id: int = Field(..., description="Storyline ID")
    article_id: int = Field(..., description="Article ID")
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Relevance score")
    importance_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Importance score")


class StorylineArticleCreate(StorylineArticleBase):
    pass


class StorylineArticle(StorylineArticleBase):
    id: int = Field(..., description="Relationship ID")
    created_at: datetime = Field(..., description="Creation timestamp")


# Story Consolidation Schemas (aligned with story_consolidations table)
class StoryConsolidationBase(BaseModel):
    story_timeline_id: int | None = Field(None, description="Associated timeline ID")
    headline: str = Field(..., min_length=1, max_length=500, description="Consolidated headline")
    consolidated_summary: str = Field(..., min_length=1, description="Consolidated summary")
    key_points: list[str] | None = Field(default=[], description="Key points")
    professional_report: str | None = Field(None, description="Professional report")
    executive_summary: str | None = Field(None, description="Executive summary")
    recommendations: list[str] | None = Field(default=[], description="Recommendations")
    ai_analysis: dict[str, Any] | None = Field(default={}, description="AI analysis data")
    sources: list[dict[str, Any]] | None = Field(default=[], description="Source information")


class StoryConsolidationCreate(StoryConsolidationBase):
    pass


class StoryConsolidationUpdate(BaseModel):
    headline: str | None = Field(None, min_length=1, max_length=500)
    consolidated_summary: str | None = Field(None, min_length=1)
    key_points: list[str] | None = None
    professional_report: str | None = None
    executive_summary: str | None = None
    recommendations: list[str] | None = None
    ai_analysis: dict[str, Any] | None = None
    sources: list[dict[str, Any]] | None = None


class StoryConsolidation(StoryConsolidationBase):
    id: int = Field(..., description="Consolidation ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# RSS Feed Schemas (aligned with rss_feeds table)
class RSSFeedBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Feed name")
    url: str = Field(..., description="Feed URL")
    description: str | None = Field(None, description="Feed description")
    tier: int = Field(
        ..., ge=1, le=3, description="Feed tier: 1=wire services, 2=institutions, 3=specialized"
    )
    priority: int = Field(
        default=5, ge=1, le=10, description="Processing priority: 1=highest, 10=lowest"
    )
    language: str = Field(default="en", max_length=10, description="Feed language")
    country: str | None = Field(None, max_length=100, description="Feed country")
    category: str = Field(..., max_length=50, description="Feed category")
    subcategory: str | None = Field(None, max_length=50, description="Feed subcategory")
    is_active: bool = Field(default=True, description="Feed active status")
    status: str = Field(default="active", max_length=20, description="Feed status")
    update_frequency: int = Field(
        default=30, ge=5, le=1440, description="Update frequency in minutes"
    )
    max_articles_per_update: int = Field(
        default=50, ge=1, le=1000, description="Maximum articles per update"
    )


class RSSFeedCreate(RSSFeedBase):
    pass


class RSSFeedUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    url: str | None = None
    description: str | None = None
    tier: int | None = Field(None, ge=1, le=3)
    priority: int | None = Field(None, ge=1, le=10)
    language: str | None = Field(None, max_length=10)
    country: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    subcategory: str | None = Field(None, max_length=50)
    is_active: bool | None = None
    status: str | None = Field(None, max_length=20)
    update_frequency: int | None = Field(None, ge=5, le=1440)
    max_articles_per_update: int | None = Field(None, ge=1, le=1000)


class RSSFeed(RSSFeedBase):
    id: int = Field(..., description="Feed ID")
    success_rate: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Success rate percentage"
    )
    avg_response_time: int = Field(default=0, ge=0, description="Average response time in seconds")
    reliability_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Reliability score")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


# AI Analysis Schemas (aligned with ai_analysis table)
class AIAnalysisBase(BaseModel):
    model_config = {"protected_namespaces": ()}

    story_timeline_id: int | None = Field(None, description="Associated timeline ID")
    analysis_type: str = Field(..., min_length=1, max_length=50, description="Analysis type")
    analysis_data: dict[str, Any] = Field(..., description="Analysis data")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Analysis confidence")
    model_used: str | None = Field(None, max_length=100, description="Model used")
    processing_time_ms: int | None = Field(
        None, ge=0, description="Processing time in milliseconds"
    )


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
    services: dict[str, HealthStatus] = Field(..., description="Service statuses")
    details: dict[str, Any] | None = Field(None, description="Additional details")


# Statistics Schemas
class ArticleStats(BaseModel):
    total_articles: int = Field(..., ge=0, description="Total articles")
    articles_by_source: dict[str, int] = Field(..., description="Articles by source")
    articles_by_category: dict[str, int] = Field(..., description="Articles by category")
    avg_quality_score: float | None = Field(None, ge=0, le=1, description="Average quality score")
    processing_success_rate: float | None = Field(
        None, ge=0, le=1, description="Processing success rate"
    )
    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )


# Search Schemas
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    filters: dict[str, Any] | None = Field(None, description="Search filters")
    page: int = Field(1, ge=1, description="Page number")
    limit: int = Field(20, ge=1, le=100, description="Items per page")


class SearchResult(BaseModel):
    items: list[Article] = Field(..., description="Search results")
    total: int = Field(..., ge=0, description="Total results")
    query: str = Field(..., description="Search query")
    filters: dict[str, Any] | None = Field(None, description="Applied filters")
    page: int = Field(..., ge=1, description="Current page")
    limit: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=1, description="Total pages")


class StorylineResponse(BaseModel):
    """Response model for storyline operations"""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error: str | None = None


class CreateStorylineRequest(BaseModel):
    """Request model for creating storylines"""

    title: str
    description: str | None = None


class AddArticleRequest(BaseModel):
    """Request model for adding articles to storylines"""

    article_id: str
    relevance_score: float | None = 0.5
    importance_score: float | None = 0.5
