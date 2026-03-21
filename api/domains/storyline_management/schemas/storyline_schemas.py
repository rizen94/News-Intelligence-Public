#!/usr/bin/env python3
"""
Storyline Management Schemas
Pydantic models for request/response validation
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Request Models
# ============================================================================


class StorylineCreateRequest(BaseModel):
    """Request model for creating a new storyline"""

    title: str = Field(..., min_length=1, max_length=500, description="Storyline title")
    description: str | None = Field(None, max_length=5000, description="Storyline description")
    article_ids: list[int] | None = Field(
        None, max_length=100, description="Initial article IDs to include"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Title cannot be empty")
        return v.strip()

    @field_validator("article_ids")
    @classmethod
    def validate_article_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is not None:
            if len(v) == 0:
                return None
            if len(set(v)) != len(v):
                raise ValueError("Article IDs must be unique")
        return v


class StorylineUpdateRequest(BaseModel):
    """Request model for updating a storyline"""

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = Field(None, max_length=5000)
    status: str | None = Field(None, pattern="^(active|archived|draft)$")

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str | None) -> str | None:
        if v is not None and (not v or not v.strip()):
            raise ValueError("Title cannot be empty")
        return v.strip() if v else None


class AddArticleRequest(BaseModel):
    """Request model for adding an article to a storyline"""

    relevance_score: float | None = Field(
        0.5, ge=0.0, le=1.0, description="Relevance score (0.0-1.0)"
    )


class StorylineEvolutionRequest(BaseModel):
    """Request model for evolving a storyline"""

    new_article_ids: list[int] | None = Field(
        None, max_length=50, description="New article IDs to add"
    )
    force_evolution: bool = Field(False, description="Force evolution even if recent")

    @field_validator("new_article_ids")
    @classmethod
    def validate_new_article_ids(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and len(v) > 0:
            if len(set(v)) != len(v):
                raise ValueError("Article IDs must be unique")
        return v


# ============================================================================
# Response Models
# ============================================================================


class ArticleSummary(BaseModel):
    """Summary of an article in a storyline"""

    id: int
    title: str
    url: str | None
    source_domain: str | None
    published_at: datetime | None
    summary: str | None

    class Config:
        from_attributes = True


class StorylineResponse(BaseModel):
    """Response model for a single storyline"""

    id: int
    title: str
    description: str | None
    status: str
    article_count: int
    quality_score: float | None
    analysis_summary: str | None
    created_at: datetime
    updated_at: datetime
    last_evolution_at: datetime | None
    evolution_count: int | None

    class Config:
        from_attributes = True


class StorylineEntitySummary(BaseModel):
    """Entity attached to a storyline (from article_entities + entity_canonical)"""

    canonical_entity_id: int
    name: str
    type: str
    description: str | None = None
    mention_count: int = 0
    has_profile: bool = False
    has_dossier: bool = False
    profile_id: int | None = None


class StorylineDetailResponse(StorylineResponse):
    """Detailed storyline response with articles and entities"""

    articles: list[ArticleSummary] = Field(default_factory=list)
    background_information: dict[str, Any] | None = None
    context_last_updated: datetime | None = None
    ml_processing_status: str | None = None  # pending, processing, completed, failed
    editorial_document: dict[str, Any] | None = None
    document_version: int | None = None
    document_status: str | None = None
    last_refinement: datetime | None = None
    key_entities: dict[str, Any] | None = None  # legacy column from storylines.key_entities
    entities: list[StorylineEntitySummary] = Field(default_factory=list)
    # Migration 181: durable narratives + refinement queue (optional until columns exist)
    canonical_narrative: str | None = None
    narrative_finisher_model: str | None = None
    narrative_finisher_at: datetime | None = None
    narrative_finisher_meta: dict[str, Any] | None = None
    timeline_narrative_chronological: str | None = None
    timeline_narrative_briefing: str | None = None
    timeline_narrative_chronological_at: datetime | None = None
    timeline_narrative_briefing_at: datetime | None = None
    refinement_jobs_pending: list[str] = Field(
        default_factory=list,
        description="job_type values queued in intelligence.content_refinement_queue",
    )


class StorylineRefinementEnqueueRequest(BaseModel):
    """POST body to queue storyline refinement (processed by automation workers)."""

    job_type: str = Field(
        ...,
        description="comprehensive_rag | narrative_finisher | headline_refiner | timeline_narrative_chronological | timeline_narrative_briefing",
    )
    priority: str = Field("medium", pattern="^(high|medium|low)$")


class StorylineListItem(BaseModel):
    """List item for storyline listing"""

    id: int
    title: str
    description: str | None
    article_count: int
    quality_score: float | None
    status: str
    created_at: datetime
    updated_at: datetime
    top_entities: list[dict[str, Any]] = Field(
        default_factory=list
    )  # [{name, type, description_short}]


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

    data: list[StorylineListItem]
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
    context_stats: dict[str, int]


class QualityAssessmentResult(BaseModel):
    """Result of quality assessment"""

    storyline_id: int
    overall_score: float
    quality_score: float
    factual_accuracy_score: float
    narrative_quality_score: float
    source_diversity: int
    article_count: int
    recommendations: list[str]


class EmergingStoryline(BaseModel):
    """Emerging storyline detection result"""

    title: str
    description: str
    article_count: int
    confidence_score: float
    keywords: list[str]
    article_ids: list[int]


class EmergingStorylinesResponse(BaseModel):
    """Response for emerging storylines"""

    emerging_storylines: list[EmergingStoryline]
    articles_analyzed: int
    clusters_found: int


# ============================================================================
# Common Response Wrapper
# ============================================================================


class APIResponse(BaseModel):
    """Standard API response wrapper"""

    success: bool
    data: Any | None = None
    message: str | None = None
    error: str | None = None
    timestamp: datetime | None = None
