#!/usr/bin/env python3
"""
Storyline Management Schemas
Pydantic models for request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional
from datetime import datetime


# ============================================================================
# Request Models
# ============================================================================

class StorylineCreateRequest(BaseModel):
    """Request model for creating a new storyline"""
    title: str = Field(..., min_length=1, max_length=500, description="Storyline title")
    description: Optional[str] = Field(None, max_length=5000, description="Storyline description")
    article_ids: Optional[List[int]] = Field(None, max_items=100, description="Initial article IDs to include")
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('article_ids')
    def validate_article_ids(cls, v):
        if v is not None:
            if len(v) == 0:
                return None
            if len(set(v)) != len(v):
                raise ValueError('Article IDs must be unique')
        return v


class StorylineUpdateRequest(BaseModel):
    """Request model for updating a storyline"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[str] = Field(None, pattern="^(active|archived|draft)$")
    
    @validator('title')
    def validate_title(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title cannot be empty')
        return v.strip() if v else None


class AddArticleRequest(BaseModel):
    """Request model for adding an article to a storyline"""
    relevance_score: Optional[float] = Field(0.5, ge=0.0, le=1.0, description="Relevance score (0.0-1.0)")


class StorylineEvolutionRequest(BaseModel):
    """Request model for evolving a storyline"""
    new_article_ids: Optional[List[int]] = Field(None, max_items=50, description="New article IDs to add")
    force_evolution: bool = Field(False, description="Force evolution even if recent")
    
    @validator('new_article_ids')
    def validate_article_ids(cls, v):
        if v is not None and len(v) > 0:
            if len(set(v)) != len(v):
                raise ValueError('Article IDs must be unique')
        return v


# ============================================================================
# Response Models
# ============================================================================

class ArticleSummary(BaseModel):
    """Summary of an article in a storyline"""
    id: int
    title: str
    url: Optional[str]
    source_domain: Optional[str]
    published_at: Optional[datetime]
    summary: Optional[str]
    
    class Config:
        from_attributes = True


class StorylineResponse(BaseModel):
    """Response model for a single storyline"""
    id: int
    title: str
    description: Optional[str]
    status: str
    article_count: int
    quality_score: Optional[float]
    analysis_summary: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_evolution_at: Optional[datetime]
    evolution_count: Optional[int]
    
    class Config:
        from_attributes = True


class StorylineEntitySummary(BaseModel):
    """Entity attached to a storyline (from article_entities + entity_canonical)"""
    canonical_entity_id: int
    name: str
    type: str
    description: Optional[str] = None
    mention_count: int = 0
    has_profile: bool = False
    has_dossier: bool = False
    profile_id: Optional[int] = None


class StorylineDetailResponse(StorylineResponse):
    """Detailed storyline response with articles and entities"""
    articles: List[ArticleSummary] = Field(default_factory=list)
    background_information: Optional[Dict[str, Any]] = None
    context_last_updated: Optional[datetime] = None
    ml_processing_status: Optional[str] = None  # pending, processing, completed, failed
    editorial_document: Optional[Dict[str, Any]] = None
    document_version: Optional[int] = None
    document_status: Optional[str] = None
    last_refinement: Optional[datetime] = None
    key_entities: Optional[Dict[str, Any]] = None  # legacy column from storylines.key_entities
    entities: List[StorylineEntitySummary] = Field(default_factory=list)
    # Migration 181: durable narratives + refinement queue (optional until columns exist)
    canonical_narrative: Optional[str] = None
    narrative_finisher_model: Optional[str] = None
    narrative_finisher_at: Optional[datetime] = None
    narrative_finisher_meta: Optional[Dict[str, Any]] = None
    timeline_narrative_chronological: Optional[str] = None
    timeline_narrative_briefing: Optional[str] = None
    timeline_narrative_chronological_at: Optional[datetime] = None
    timeline_narrative_briefing_at: Optional[datetime] = None
    refinement_jobs_pending: List[str] = Field(
        default_factory=list,
        description="job_type values queued in intelligence.content_refinement_queue",
    )


class StorylineRefinementEnqueueRequest(BaseModel):
    """POST body to queue storyline refinement (processed by automation workers)."""

    job_type: str = Field(
        ...,
        description="comprehensive_rag | narrative_finisher | timeline_narrative_chronological | timeline_narrative_briefing",
    )
    priority: str = Field("medium", pattern="^(high|medium|low)$")


class StorylineListItem(BaseModel):
    """List item for storyline listing"""
    id: int
    title: str
    description: Optional[str]
    article_count: int
    quality_score: Optional[float]
    status: str
    created_at: datetime
    updated_at: datetime
    top_entities: List[Dict[str, Any]] = Field(default_factory=list)  # [{name, type, description_short}]


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there is a next page")
    has_prev: bool = Field(..., description="Whether there is a previous page")


class StorylineListResponse(BaseModel):
    """Paginated list of storylines"""
    data: List[StorylineListItem]
    pagination: PaginationInfo
    domain: str


class EvolutionResult(BaseModel):
    """Result of storyline evolution"""
    storyline_id: int
    total_articles: int
    new_articles: int
    evolution_count: int
    summary_updated: bool
    context_updated: bool
    summary_length: int
    context_stats: Dict[str, int]


class QualityAssessmentResult(BaseModel):
    """Result of quality assessment"""
    storyline_id: int
    overall_score: float
    quality_score: float
    factual_accuracy_score: float
    narrative_quality_score: float
    source_diversity: int
    article_count: int
    recommendations: List[str]


class EmergingStoryline(BaseModel):
    """Emerging storyline detection result"""
    title: str
    description: str
    article_count: int
    confidence_score: float
    keywords: List[str]
    article_ids: List[int]


class EmergingStorylinesResponse(BaseModel):
    """Response for emerging storylines"""
    emerging_storylines: List[EmergingStoryline]
    articles_analyzed: int
    clusters_found: int


# ============================================================================
# Common Response Wrapper
# ============================================================================

class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    data: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

