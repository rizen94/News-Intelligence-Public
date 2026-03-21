"""
Generated API Models from Unified Schema
Version: 3.1.0
Generated: 2025-09-09T15:15:21.750428
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Article(BaseModel):
    """Article model"""

    id: int
    title: str
    content: str | None
    url: str | None
    published_at: datetime | None
    source: str | None
    category: str | None
    status: str
    tags: list[str] | None
    created_at: datetime
    updated_at: datetime
    sentiment_score: float | None
    entities: dict[str, Any] | None
    readability_score: float | None
    quality_score: float | None
    summary: str | None
    ml_data: dict[str, Any] | None
    language: str | None
    word_count: int | None
    reading_time: int | None
    feed_id: int | None


class RSSFeed(BaseModel):
    """RSSFeed model"""

    id: int
    name: str
    url: str
    is_active: bool
    last_fetched: datetime | None
    fetch_interval: int | None
    created_at: datetime
    updated_at: datetime
    error_count: int | None
    last_error: str | None


class ArticleCreate(BaseModel):
    """Article creation model"""

    title: str
    content: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    source: str | None = None
    category: str | None = None
    status: str = "pending"
    tags: list[str] | None = None
    sentiment_score: float | None = None
    entities: dict[str, Any] | None = None
    readability_score: float | None = None
    quality_score: float | None = 0.0
    summary: str | None = None
    ml_data: dict[str, Any] | None = None
    language: str | None = "en"
    word_count: int | None = 0
    reading_time: int | None = 0
    feed_id: int | None = None


class ArticleUpdate(BaseModel):
    """Article update model"""

    title: str | None = None
    content: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    source: str | None = None
    category: str | None = None
    status: str | None = None
    tags: list[str] | None = None
    sentiment_score: float | None = None
    entities: dict[str, Any] | None = None
    readability_score: float | None = None
    quality_score: float | None = None
    summary: str | None = None
    ml_data: dict[str, Any] | None = None
    language: str | None = None
    word_count: int | None = None
    reading_time: int | None = None
    feed_id: int | None = None
