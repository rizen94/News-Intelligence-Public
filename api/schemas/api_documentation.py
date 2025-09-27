"""
News Intelligence System v3.3.0 - Comprehensive API Documentation Schemas
Provides detailed schemas for all API endpoints with examples and validation
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, validator
from enum import Enum

# Enums for API documentation
class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ArticleStatus(str, Enum):
    RAW = "raw"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"

class StorylineStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"

class DuplicateType(str, Enum):
    EXACT = "exact"
    NEAR = "near"
    CROSS_SOURCE = "cross-source"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Base response models
class BaseResponse(BaseModel):
    """Base response model for all API endpoints"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Human-readable message about the operation")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    meta: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class APIResponse(BaseResponse):
    """Standard API response with data field"""
    data: Optional[Union[Dict[str, Any], List[Any]]] = Field(None, description="Response data")

# Article models
class ArticleBase(BaseModel):
    """Base article model"""
    title: str = Field(..., description="Article title", max_length=500)
    content: str = Field(..., description="Article content")
    url: Optional[str] = Field(None, description="Article URL", max_length=1000)
    published_at: Optional[datetime] = Field(None, description="Publication timestamp")
    source: Optional[str] = Field(None, description="News source", max_length=100)
    author: Optional[str] = Field(None, description="Article author", max_length=255)
    tags: Optional[List[str]] = Field(default=[], description="Article tags")
    language: str = Field(default="en", description="Article language", max_length=10)

class ArticleCreate(ArticleBase):
    """Model for creating new articles"""
    pass

class ArticleUpdate(BaseModel):
    """Model for updating articles"""
    title: Optional[str] = Field(None, description="Article title", max_length=500)
    content: Optional[str] = Field(None, description="Article content")
    tags: Optional[List[str]] = Field(None, description="Article tags")
    status: Optional[ArticleStatus] = Field(None, description="Processing status")

class ArticleResponse(ArticleBase):
    """Complete article response model"""
    id: int = Field(..., description="Unique article identifier")
    status: ArticleStatus = Field(..., description="Processing status")
    quality_score: Optional[float] = Field(None, description="Content quality score (0-1)")
    sentiment_score: Optional[float] = Field(None, description="Sentiment score (-1 to 1)")
    readability_score: Optional[float] = Field(None, description="Readability score (0-1)")
    summary: Optional[str] = Field(None, description="AI-generated summary")
    entities: Optional[Dict[str, Any]] = Field(None, description="Extracted entities")
    ml_data: Optional[Dict[str, Any]] = Field(None, description="ML processing data")
    word_count: int = Field(default=0, description="Word count")
    reading_time: int = Field(default=0, description="Estimated reading time in minutes")
    content_hash: Optional[str] = Field(None, description="Content hash for deduplication")
    deduplication_status: Optional[str] = Field(None, description="Deduplication status")
    similarity_score: Optional[float] = Field(None, description="Similarity score with other articles")
    cluster_id: Optional[int] = Field(None, description="Article cluster ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# RSS Feed models
class RSSFeedBase(BaseModel):
    """Base RSS feed model"""
    name: str = Field(..., description="Feed name", max_length=200)
    url: str = Field(..., description="Feed URL", max_length=500)
    description: Optional[str] = Field(None, description="Feed description")
    category: Optional[str] = Field(None, description="Feed category", max_length=100)
    subcategory: Optional[str] = Field(None, description="Feed subcategory", max_length=100)
    country: Optional[str] = Field(None, description="Feed country", max_length=50)
    tier: int = Field(default=1, description="Feed priority tier (1-5)")
    priority: int = Field(default=1, description="Feed priority (1-10)")
    max_articles: int = Field(default=50, description="Maximum articles per fetch")
    update_frequency: int = Field(default=30, description="Update frequency in minutes")

class RSSFeedCreate(RSSFeedBase):
    """Model for creating new RSS feeds"""
    pass

class RSSFeedUpdate(BaseModel):
    """Model for updating RSS feeds"""
    name: Optional[str] = Field(None, description="Feed name", max_length=200)
    description: Optional[str] = Field(None, description="Feed description")
    category: Optional[str] = Field(None, description="Feed category", max_length=100)
    subcategory: Optional[str] = Field(None, description="Feed subcategory", max_length=100)
    country: Optional[str] = Field(None, description="Feed country", max_length=50)
    tier: Optional[int] = Field(None, description="Feed priority tier (1-5)")
    priority: Optional[int] = Field(None, description="Feed priority (1-10)")
    max_articles: Optional[int] = Field(None, description="Maximum articles per fetch")
    update_frequency: Optional[int] = Field(None, description="Update frequency in minutes")
    is_active: Optional[bool] = Field(None, description="Whether feed is active")

class RSSFeedResponse(RSSFeedBase):
    """Complete RSS feed response model"""
    id: int = Field(..., description="Unique feed identifier")
    is_active: bool = Field(default=True, description="Whether feed is active")
    last_fetched: Optional[datetime] = Field(None, description="Last fetch timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# Storyline models
class StorylineBase(BaseModel):
    """Base storyline model"""
    title: str = Field(..., description="Storyline title", max_length=500)
    description: Optional[str] = Field(None, description="Storyline description")
    status: StorylineStatus = Field(default=StorylineStatus.ACTIVE, description="Storyline status")
    category: Optional[str] = Field(None, description="Storyline category", max_length=100)
    tags: Optional[List[str]] = Field(default=[], description="Storyline tags")
    priority: int = Field(default=1, description="Storyline priority (1-10)")

class StorylineCreate(StorylineBase):
    """Model for creating new storylines"""
    pass

class StorylineUpdate(BaseModel):
    """Model for updating storylines"""
    title: Optional[str] = Field(None, description="Storyline title", max_length=500)
    description: Optional[str] = Field(None, description="Storyline description")
    status: Optional[StorylineStatus] = Field(None, description="Storyline status")
    category: Optional[str] = Field(None, description="Storyline category", max_length=100)
    tags: Optional[List[str]] = Field(None, description="Storyline tags")
    priority: Optional[int] = Field(None, description="Storyline priority (1-10)")

class StorylineResponse(StorylineBase):
    """Complete storyline response model"""
    id: str = Field(..., description="Unique storyline identifier")
    master_summary: Optional[str] = Field(None, description="Master summary")
    timeline_summary: Optional[str] = Field(None, description="Timeline summary")
    key_entities: Optional[Dict[str, Any]] = Field(None, description="Key entities")
    sentiment_trend: Optional[Dict[str, Any]] = Field(None, description="Sentiment trend")
    source_diversity: Optional[Dict[str, Any]] = Field(None, description="Source diversity")
    last_article_added: Optional[datetime] = Field(None, description="Last article added timestamp")
    article_count: int = Field(default=0, description="Number of articles in storyline")
    ml_processed: bool = Field(default=False, description="Whether storyline has been ML processed")
    ml_processing_status: ProcessingStatus = Field(default=ProcessingStatus.PENDING, description="ML processing status")
    rag_content: Optional[Dict[str, Any]] = Field(None, description="RAG content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

# Storyline Article models
class StorylineArticleBase(BaseModel):
    """Base storyline article model"""
    storyline_id: str = Field(..., description="Storyline identifier")
    article_id: str = Field(..., description="Article identifier")
    relevance_score: Optional[float] = Field(None, description="Relevance score (0-1)")
    importance_score: Optional[float] = Field(None, description="Importance score (0-1)")
    temporal_order: Optional[int] = Field(None, description="Temporal order in storyline")
    notes: Optional[str] = Field(None, description="Additional notes")

class StorylineArticleCreate(StorylineArticleBase):
    """Model for adding articles to storylines"""
    pass

class StorylineArticleResponse(StorylineArticleBase):
    """Complete storyline article response model"""
    id: str = Field(..., description="Unique storyline article identifier")
    added_at: datetime = Field(..., description="Addition timestamp")
    added_by: Optional[str] = Field(None, description="User who added the article")
    ml_analysis: Optional[Dict[str, Any]] = Field(None, description="ML analysis data")

# Deduplication models
class DuplicatePairResponse(BaseModel):
    """Duplicate pair response model"""
    id: int = Field(..., description="Unique duplicate pair identifier")
    article1_id: int = Field(..., description="First article ID")
    article2_id: int = Field(..., description="Second article ID")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    duplicate_type: DuplicateType = Field(..., description="Type of duplicate")
    algorithm: str = Field(..., description="Algorithm used for detection")
    status: str = Field(..., description="Duplicate status")
    detected_at: datetime = Field(..., description="Detection timestamp")

class ClusterResponse(BaseModel):
    """Article cluster response model"""
    id: int = Field(..., description="Unique cluster identifier")
    article_ids: List[int] = Field(..., description="Article IDs in cluster")
    cluster_size: int = Field(..., description="Number of articles in cluster")
    similarity_threshold: float = Field(..., description="Similarity threshold used")
    storyline_suggestion: Optional[str] = Field(None, description="Suggested storyline title")
    created_at: datetime = Field(..., description="Cluster creation timestamp")

class DeduplicationStatsResponse(BaseModel):
    """Deduplication statistics response model"""
    total_articles: int = Field(..., description="Total articles processed")
    articles_with_content_hash: int = Field(..., description="Articles with content hash")
    total_clusters: int = Field(..., description="Total clusters created")
    total_duplicate_pairs: int = Field(..., description="Total duplicate pairs found")
    system_status: str = Field(..., description="Deduplication system status")

# Log management models
class LogEntryResponse(BaseModel):
    """Log entry response model"""
    timestamp: datetime = Field(..., description="Log entry timestamp")
    level: LogLevel = Field(..., description="Log level")
    logger: str = Field(..., description="Logger name")
    message: str = Field(..., description="Log message")
    module: Optional[str] = Field(None, description="Module name")
    function: Optional[str] = Field(None, description="Function name")
    line: Optional[int] = Field(None, description="Line number")
    exception: Optional[Dict[str, Any]] = Field(None, description="Exception information")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Additional data")

class LogStatsResponse(BaseModel):
    """Log statistics response model"""
    period_days: int = Field(..., description="Analysis period in days")
    total_entries: int = Field(..., description="Total log entries")
    error_count: int = Field(..., description="Error count")
    warning_count: int = Field(..., description="Warning count")
    info_count: int = Field(..., description="Info count")
    debug_count: int = Field(..., description="Debug count")
    time_range: Dict[str, str] = Field(..., description="Time range of analysis")
    top_loggers: List[Dict[str, Union[str, int]]] = Field(..., description="Top loggers by count")
    top_errors: List[Dict[str, Union[str, int]]] = Field(..., description="Top errors by count")

class SystemHealthResponse(BaseModel):
    """System health response model"""
    error_rate_last_hour: float = Field(..., description="Error rate in last hour")
    total_errors_last_24h: int = Field(..., description="Total errors in last 24 hours")
    hourly_error_trend: List[int] = Field(..., description="Hourly error trend (24 hours)")
    system_health_score: float = Field(..., description="System health score (0-100)")
    timestamp: datetime = Field(..., description="Health check timestamp")

# Monitoring models
class SystemMetricsResponse(BaseModel):
    """System metrics response model"""
    cpu_percent: float = Field(..., description="CPU usage percentage")
    memory_percent: float = Field(..., description="Memory usage percentage")
    disk_percent: float = Field(..., description="Disk usage percentage")
    load_average: List[float] = Field(..., description="System load average")
    uptime: str = Field(..., description="System uptime")
    last_health_check: datetime = Field(..., description="Last health check timestamp")

class DatabaseMetricsResponse(BaseModel):
    """Database metrics response model"""
    total_articles: int = Field(..., description="Total articles count")
    recent_articles: int = Field(..., description="Recent articles count (24h)")
    total_rss_feeds: int = Field(..., description="Total RSS feeds count")
    total_storylines: int = Field(..., description="Total storylines count")
    database_size: str = Field(..., description="Database size")
    connection_status: str = Field(..., description="Database connection status")

# ML Processing models
class MLPipelineRequest(BaseModel):
    """ML pipeline request model"""
    pipeline_id: str = Field(..., description="Pipeline identifier")
    force: bool = Field(default=False, description="Force pipeline execution")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Pipeline parameters")

class MLPipelineResponse(BaseModel):
    """ML pipeline response model"""
    pipeline_id: str = Field(..., description="Pipeline identifier")
    status: str = Field(..., description="Pipeline status")
    progress: float = Field(..., description="Progress percentage (0-100)")
    started_at: datetime = Field(..., description="Pipeline start timestamp")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")
    processed_items: int = Field(..., description="Number of processed items")
    total_items: int = Field(..., description="Total items to process")
    errors: List[str] = Field(default=[], description="Pipeline errors")

# Error response models
class ErrorResponse(BaseModel):
    """Error response model"""
    success: bool = Field(default=False, description="Operation success status")
    message: str = Field(..., description="Error message")
    error_type: str = Field(..., description="Error type")
    details: str = Field(..., description="Error details")
    recoverable: bool = Field(..., description="Whether error is recoverable")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")

# Pagination models
class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1, description="Page number")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")

class PaginatedResponse(BaseModel):
    """Paginated response model"""
    items: List[Any] = Field(..., description="Response items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")

# Filter models
class ArticleFilters(BaseModel):
    """Article filtering parameters"""
    status: Optional[ArticleStatus] = Field(None, description="Filter by status")
    source: Optional[str] = Field(None, description="Filter by source")
    category: Optional[str] = Field(None, description="Filter by category")
    date_from: Optional[datetime] = Field(None, description="Filter from date")
    date_to: Optional[datetime] = Field(None, description="Filter to date")
    quality_min: Optional[float] = Field(None, ge=0, le=1, description="Minimum quality score")
    quality_max: Optional[float] = Field(None, ge=0, le=1, description="Maximum quality score")

class StorylineFilters(BaseModel):
    """Storyline filtering parameters"""
    status: Optional[StorylineStatus] = Field(None, description="Filter by status")
    category: Optional[str] = Field(None, description="Filter by category")
    min_articles: Optional[int] = Field(None, ge=0, description="Minimum article count")
    max_articles: Optional[int] = Field(None, ge=0, description="Maximum article count")
    ml_processed: Optional[bool] = Field(None, description="Filter by ML processing status")
