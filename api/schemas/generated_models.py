"""
Generated API Models from Unified Schema
Version: 3.1.0
Generated: 2025-09-09T15:15:21.750428
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class Article(BaseModel):
    """Article model"""

    id: int
    title: str
    content: Optional[str]
    url: Optional[str]
    published_at: Optional[datetime]
    source: Optional[str]
    category: Optional[str]
    status: str
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime
    sentiment_score: Optional[float]
    entities: Optional[Dict[str, Any]]
    readability_score: Optional[float]
    quality_score: Optional[float]
    summary: Optional[str]
    ml_data: Optional[Dict[str, Any]]
    language: Optional[str]
    word_count: Optional[int]
    reading_time: Optional[int]
    feed_id: Optional[int]
class RSSFeed(BaseModel):
    """RSSFeed model"""

    id: int
    name: str
    url: str
    is_active: bool
    last_fetched: Optional[datetime]
    fetch_interval: Optional[int]
    created_at: datetime
    updated_at: datetime
    error_count: Optional[int]
    last_error: Optional[str]

class ArticleCreate(BaseModel):
    """Article creation model"""
    title: str
    content: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    category: Optional[str] = None
    status: str = "pending"
    tags: Optional[List[str]] = None
    sentiment_score: Optional[float] = None
    entities: Optional[Dict[str, Any]] = None
    readability_score: Optional[float] = None
    quality_score: Optional[float] = 0.0
    summary: Optional[str] = None
    ml_data: Optional[Dict[str, Any]] = None
    language: Optional[str] = "en"
    word_count: Optional[int] = 0
    reading_time: Optional[int] = 0
    feed_id: Optional[int] = None

class ArticleUpdate(BaseModel):
    """Article update model"""
    title: Optional[str] = None
    content: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    source: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    sentiment_score: Optional[float] = None
    entities: Optional[Dict[str, Any]] = None
    readability_score: Optional[float] = None
    quality_score: Optional[float] = None
    summary: Optional[str] = None
    ml_data: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    word_count: Optional[int] = None
    reading_time: Optional[int] = None
    feed_id: Optional[int] = None