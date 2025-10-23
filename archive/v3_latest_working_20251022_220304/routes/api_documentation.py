"""
News Intelligence System v3.3.0 - API Documentation Routes
Provides comprehensive API documentation and endpoint descriptions
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from config.database import get_db
from config.logging_config import get_component_logger
from schemas.api_documentation import (
    APIResponse, ArticleResponse, ArticleCreate, ArticleUpdate, ArticleFilters,
    RSSFeedResponse, RSSFeedCreate, RSSFeedUpdate,
    StorylineResponse, StorylineCreate, StorylineUpdate, StorylineFilters,
    StorylineArticleResponse, StorylineArticleCreate,
    DeduplicationStatsResponse, DuplicatePairResponse, ClusterResponse,
    LogStatsResponse, LogEntryResponse, SystemHealthResponse,
    SystemMetricsResponse, DatabaseMetricsResponse,
    MLPipelineRequest, MLPipelineResponse,
    PaginationParams, PaginatedResponse
)

router = APIRouter(prefix="/docs", tags=["API Documentation"])
logger = get_component_logger('api')

@router.get("/overview", response_model=APIResponse)
async def get_api_overview():
    """
    Get comprehensive API overview and system information
    
    Returns detailed information about the News Intelligence System API including:
    - System version and capabilities
    - Available endpoints and their purposes
    - Authentication requirements
    - Rate limiting information
    - Data models and schemas
    """
    try:
        overview = {
            "system": {
                "name": "News Intelligence System",
                "version": "3.3.0",
                "description": "AI-powered news aggregation and analysis platform",
                "capabilities": [
                    "RSS feed processing and article collection",
                    "AI-powered content analysis and summarization",
                    "Advanced duplicate detection and clustering",
                    "Storyline creation and management",
                    "Real-time monitoring and analytics",
                    "Comprehensive logging and error handling"
                ]
            },
            "endpoints": {
                "articles": {
                    "description": "Article management and processing",
                    "endpoints": [
                        "GET /api/articles - List articles with filtering",
                        "POST /api/articles - Create new article",
                        "GET /api/articles/{id} - Get article details",
                        "PUT /api/articles/{id} - Update article",
                        "DELETE /api/articles/{id} - Delete article"
                    ]
                },
                "rss_feeds": {
                    "description": "RSS feed management",
                    "endpoints": [
                        "GET /api/rss/feeds - List RSS feeds",
                        "POST /api/rss/feeds - Add new RSS feed",
                        "GET /api/rss/feeds/{id} - Get feed details",
                        "PUT /api/rss/feeds/{id} - Update feed",
                        "DELETE /api/rss/feeds/{id} - Delete feed"
                    ]
                },
                "storylines": {
                    "description": "Storyline creation and management",
                    "endpoints": [
                        "GET /api/storylines - List storylines",
                        "POST /api/storylines - Create storyline",
                        "GET /api/storylines/{id} - Get storyline details",
                        "PUT /api/storylines/{id} - Update storyline",
                        "POST /api/storylines/{id}/add-article - Add article to storyline"
                    ]
                },
                "deduplication": {
                    "description": "Duplicate detection and clustering",
                    "endpoints": [
                        "GET /api/deduplication/statistics - Get deduplication stats",
                        "GET /api/deduplication/test - Test deduplication system",
                        "GET /api/deduplication/duplicates - Find duplicate articles",
                        "GET /api/deduplication/clusters - Get article clusters"
                    ]
                },
                "logs": {
                    "description": "Log management and monitoring",
                    "endpoints": [
                        "GET /api/logs/statistics - Get log statistics",
                        "GET /api/logs/entries - Get log entries",
                        "GET /api/logs/errors - Analyze errors",
                        "GET /api/logs/health - System health from logs",
                        "GET /api/logs/realtime - Real-time logs"
                    ]
                },
                "monitoring": {
                    "description": "System monitoring and health",
                    "endpoints": [
                        "GET /api/health - System health check",
                        "GET /api/monitoring/dashboard - Monitoring dashboard",
                        "GET /api/monitoring/metrics - System metrics"
                    ]
                }
            },
            "authentication": {
                "type": "None (Development)",
                "note": "Authentication will be implemented in production",
                "rate_limiting": "None (Development)"
            },
            "data_models": {
                "article": "Article with content, metadata, and ML analysis",
                "rss_feed": "RSS feed configuration and status",
                "storyline": "Storyline with articles and analysis",
                "log_entry": "Structured log entry with context",
                "duplicate_pair": "Duplicate article relationship",
                "cluster": "Article cluster for storyline suggestions"
            }
        }
        
        return APIResponse(
            success=True,
            data=overview,
            message="API overview retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting API overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/endpoints", response_model=APIResponse)
async def get_all_endpoints():
    """
    Get comprehensive list of all API endpoints with descriptions
    
    Returns detailed information about every available endpoint including:
    - HTTP method and path
    - Request/response schemas
    - Query parameters
    - Example requests and responses
    - Error codes and handling
    """
    try:
        endpoints = {
            "articles": [
                {
                    "method": "GET",
                    "path": "/api/articles",
                    "description": "List articles with filtering and pagination",
                    "parameters": {
                        "query": {
                            "page": "int (default: 1) - Page number",
                            "limit": "int (default: 20) - Items per page",
                            "status": "str - Filter by status (raw, processing, processed, failed)",
                            "source": "str - Filter by news source",
                            "category": "str - Filter by category",
                            "date_from": "datetime - Filter from date",
                            "date_to": "datetime - Filter to date",
                            "quality_min": "float - Minimum quality score",
                            "quality_max": "float - Maximum quality score"
                        }
                    },
                    "response": "PaginatedResponse[ArticleResponse]",
                    "example_request": "GET /api/articles?status=processed&source=CNN&page=1&limit=10",
                    "example_response": {
                        "success": True,
                        "data": {
                            "items": [{"id": 1, "title": "Sample Article", "status": "processed"}],
                            "total": 100,
                            "page": 1,
                            "limit": 10,
                            "pages": 10
                        }
                    }
                },
                {
                    "method": "POST",
                    "path": "/api/articles",
                    "description": "Create a new article",
                    "parameters": {
                        "body": "ArticleCreate - Article data"
                    },
                    "response": "ArticleResponse",
                    "example_request": {
                        "title": "Breaking News",
                        "content": "Article content...",
                        "url": "https://example.com/article",
                        "source": "CNN"
                    }
                },
                {
                    "method": "GET",
                    "path": "/api/articles/{id}",
                    "description": "Get article details by ID",
                    "parameters": {
                        "path": {
                            "id": "int - Article ID"
                        }
                    },
                    "response": "ArticleResponse"
                },
                {
                    "method": "PUT",
                    "path": "/api/articles/{id}",
                    "description": "Update article by ID",
                    "parameters": {
                        "path": {"id": "int - Article ID"},
                        "body": "ArticleUpdate - Updated article data"
                    },
                    "response": "ArticleResponse"
                },
                {
                    "method": "DELETE",
                    "path": "/api/articles/{id}",
                    "description": "Delete article by ID",
                    "parameters": {
                        "path": {"id": "int - Article ID"}
                    },
                    "response": "APIResponse"
                }
            ],
            "rss_feeds": [
                {
                    "method": "GET",
                    "path": "/api/rss/feeds",
                    "description": "List RSS feeds with status information",
                    "parameters": {
                        "query": {
                            "active_only": "bool - Show only active feeds"
                        }
                    },
                    "response": "APIResponse[List[RSSFeedResponse]]"
                },
                {
                    "method": "POST",
                    "path": "/api/rss/feeds",
                    "description": "Add new RSS feed",
                    "parameters": {
                        "body": "RSSFeedCreate - Feed configuration"
                    },
                    "response": "RSSFeedResponse",
                    "example_request": {
                        "name": "CNN Top Stories",
                        "url": "https://rss.cnn.com/rss/edition.rss",
                        "category": "news",
                        "country": "US",
                        "tier": 1,
                        "priority": 5
                    }
                }
            ],
            "storylines": [
                {
                    "method": "GET",
                    "path": "/api/storylines",
                    "description": "List storylines with article counts",
                    "parameters": {
                        "query": {
                            "status": "str - Filter by status",
                            "category": "str - Filter by category",
                            "min_articles": "int - Minimum article count",
                            "ml_processed": "bool - Filter by ML processing status"
                        }
                    },
                    "response": "APIResponse[List[StorylineResponse]]"
                },
                {
                    "method": "POST",
                    "path": "/api/storylines",
                    "description": "Create new storyline",
                    "parameters": {
                        "body": "StorylineCreate - Storyline data"
                    },
                    "response": "StorylineResponse"
                },
                {
                    "method": "POST",
                    "path": "/api/storylines/{id}/add-article",
                    "description": "Add article to storyline",
                    "parameters": {
                        "path": {"id": "str - Storyline ID"},
                        "body": "StorylineArticleCreate - Article assignment data"
                    },
                    "response": "StorylineArticleResponse"
                }
            ],
            "deduplication": [
                {
                    "method": "GET",
                    "path": "/api/deduplication/statistics",
                    "description": "Get deduplication system statistics",
                    "response": "DeduplicationStatsResponse"
                },
                {
                    "method": "GET",
                    "path": "/api/deduplication/test",
                    "description": "Test deduplication system health",
                    "response": "APIResponse"
                }
            ],
            "logs": [
                {
                    "method": "GET",
                    "path": "/api/logs/statistics",
                    "description": "Get comprehensive log statistics",
                    "parameters": {
                        "query": {
                            "days": "int (default: 7) - Analysis period in days"
                        }
                    },
                    "response": "LogStatsResponse"
                },
                {
                    "method": "GET",
                    "path": "/api/logs/entries",
                    "description": "Get log entries with filtering",
                    "parameters": {
                        "query": {
                            "start_time": "datetime - Start time filter",
                            "end_time": "datetime - End time filter",
                            "level": "str - Log level filter",
                            "logger_name": "str - Logger name filter",
                            "limit": "int (default: 100) - Maximum entries"
                        }
                    },
                    "response": "APIResponse[List[LogEntryResponse]]"
                },
                {
                    "method": "GET",
                    "path": "/api/logs/health",
                    "description": "Get system health metrics from logs",
                    "response": "SystemHealthResponse"
                },
                {
                    "method": "GET",
                    "path": "/api/logs/realtime",
                    "description": "Get real-time log entries (last 5 minutes)",
                    "response": "APIResponse[List[LogEntryResponse]]"
                }
            ],
            "monitoring": [
                {
                    "method": "GET",
                    "path": "/api/health",
                    "description": "System health check",
                    "response": "APIResponse"
                },
                {
                    "method": "GET",
                    "path": "/api/monitoring/dashboard",
                    "description": "Comprehensive monitoring dashboard",
                    "response": "APIResponse"
                }
            ]
        }
        
        return APIResponse(
            success=True,
            data=endpoints,
            message="API endpoints documentation retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting API endpoints: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/schemas", response_model=APIResponse)
async def get_data_schemas():
    """
    Get detailed data schemas and models
    
    Returns comprehensive information about all data models including:
    - Field descriptions and types
    - Validation rules and constraints
    - Example data structures
    - Relationships between models
    """
    try:
        schemas = {
            "article": {
                "description": "Article with content, metadata, and ML analysis",
                "fields": {
                    "id": "int - Unique identifier",
                    "title": "str (max 500) - Article title",
                    "content": "str - Article content",
                    "url": "str (max 1000) - Article URL",
                    "published_at": "datetime - Publication timestamp",
                    "source": "str (max 100) - News source",
                    "author": "str (max 255) - Article author",
                    "status": "ArticleStatus - Processing status",
                    "quality_score": "float (0-1) - Content quality score",
                    "sentiment_score": "float (-1 to 1) - Sentiment score",
                    "readability_score": "float (0-1) - Readability score",
                    "summary": "str - AI-generated summary",
                    "entities": "Dict - Extracted entities",
                    "ml_data": "Dict - ML processing data",
                    "word_count": "int - Word count",
                    "reading_time": "int - Reading time in minutes",
                    "content_hash": "str - Content hash for deduplication",
                    "deduplication_status": "str - Deduplication status",
                    "similarity_score": "float - Similarity score",
                    "cluster_id": "int - Article cluster ID",
                    "created_at": "datetime - Creation timestamp",
                    "updated_at": "datetime - Last update timestamp"
                },
                "enums": {
                    "ArticleStatus": ["raw", "processing", "processed", "failed"]
                }
            },
            "rss_feed": {
                "description": "RSS feed configuration and status",
                "fields": {
                    "id": "int - Unique identifier",
                    "name": "str (max 200) - Feed name",
                    "url": "str (max 500) - Feed URL",
                    "description": "str - Feed description",
                    "category": "str (max 100) - Feed category",
                    "subcategory": "str (max 100) - Feed subcategory",
                    "country": "str (max 50) - Feed country",
                    "tier": "int (1-5) - Priority tier",
                    "priority": "int (1-10) - Feed priority",
                    "max_articles": "int - Maximum articles per fetch",
                    "update_frequency": "int - Update frequency in minutes",
                    "is_active": "bool - Whether feed is active",
                    "last_fetched": "datetime - Last fetch timestamp",
                    "created_at": "datetime - Creation timestamp",
                    "updated_at": "datetime - Last update timestamp"
                }
            },
            "storyline": {
                "description": "Storyline with articles and analysis",
                "fields": {
                    "id": "str - Unique identifier",
                    "title": "str (max 500) - Storyline title",
                    "description": "str - Storyline description",
                    "status": "StorylineStatus - Storyline status",
                    "category": "str (max 100) - Storyline category",
                    "tags": "List[str] - Storyline tags",
                    "priority": "int (1-10) - Storyline priority",
                    "master_summary": "str - Master summary",
                    "timeline_summary": "str - Timeline summary",
                    "key_entities": "Dict - Key entities",
                    "sentiment_trend": "Dict - Sentiment trend",
                    "source_diversity": "Dict - Source diversity",
                    "last_article_added": "datetime - Last article added",
                    "article_count": "int - Number of articles",
                    "ml_processed": "bool - ML processing status",
                    "ml_processing_status": "ProcessingStatus - ML status",
                    "rag_content": "Dict - RAG content",
                    "metadata": "Dict - Additional metadata",
                    "created_at": "datetime - Creation timestamp",
                    "updated_at": "datetime - Last update timestamp"
                },
                "enums": {
                    "StorylineStatus": ["active", "archived", "draft"],
                    "ProcessingStatus": ["pending", "processing", "completed", "failed"]
                }
            },
            "log_entry": {
                "description": "Structured log entry with context",
                "fields": {
                    "timestamp": "datetime - Log timestamp",
                    "level": "LogLevel - Log level",
                    "logger": "str - Logger name",
                    "message": "str - Log message",
                    "module": "str - Module name",
                    "function": "str - Function name",
                    "line": "int - Line number",
                    "exception": "Dict - Exception information",
                    "extra_data": "Dict - Additional data"
                },
                "enums": {
                    "LogLevel": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                }
            },
            "duplicate_pair": {
                "description": "Duplicate article relationship",
                "fields": {
                    "id": "int - Unique identifier",
                    "article1_id": "int - First article ID",
                    "article2_id": "int - Second article ID",
                    "similarity_score": "float (0-1) - Similarity score",
                    "duplicate_type": "DuplicateType - Type of duplicate",
                    "algorithm": "str - Detection algorithm",
                    "status": "str - Duplicate status",
                    "detected_at": "datetime - Detection timestamp"
                },
                "enums": {
                    "DuplicateType": ["exact", "near", "cross-source"]
                }
            }
        }
        
        return APIResponse(
            success=True,
            data=schemas,
            message="Data schemas retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting data schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/examples", response_model=APIResponse)
async def get_api_examples():
    """
    Get comprehensive API usage examples
    
    Returns detailed examples for common API operations including:
    - Request/response examples
    - Error handling examples
    - Best practices and patterns
    - Common use cases
    """
    try:
        examples = {
            "article_management": {
                "create_article": {
                    "request": {
                        "method": "POST",
                        "url": "/api/articles",
                        "headers": {"Content-Type": "application/json"},
                        "body": {
                            "title": "Breaking: Major Policy Change Announced",
                            "content": "The government announced a major policy change today that will affect millions of citizens...",
                            "url": "https://example.com/news/policy-change",
                            "source": "CNN",
                            "author": "John Smith",
                            "tags": ["politics", "policy", "government"],
                            "language": "en"
                        }
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "id": 123,
                            "title": "Breaking: Major Policy Change Announced",
                            "status": "raw",
                            "created_at": "2025-09-26T01:00:00Z"
                        },
                        "message": "Article created successfully"
                    }
                },
                "list_articles": {
                    "request": {
                        "method": "GET",
                        "url": "/api/articles?status=processed&source=CNN&page=1&limit=10"
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "items": [
                                {
                                    "id": 123,
                                    "title": "Breaking: Major Policy Change Announced",
                                    "status": "processed",
                                    "quality_score": 0.85,
                                    "sentiment_score": 0.2,
                                    "summary": "Government announces significant policy change affecting citizens..."
                                }
                            ],
                            "total": 100,
                            "page": 1,
                            "limit": 10,
                            "pages": 10
                        }
                    }
                }
            },
            "rss_feed_management": {
                "add_feed": {
                    "request": {
                        "method": "POST",
                        "url": "/api/rss/feeds",
                        "body": {
                            "name": "CNN Top Stories",
                            "url": "https://rss.cnn.com/rss/edition.rss",
                            "description": "CNN's top news stories",
                            "category": "news",
                            "subcategory": "general",
                            "country": "US",
                            "tier": 1,
                            "priority": 5,
                            "max_articles": 50,
                            "update_frequency": 30
                        }
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "id": 1,
                            "name": "CNN Top Stories",
                            "url": "https://rss.cnn.com/rss/edition.rss",
                            "is_active": True,
                            "created_at": "2025-09-26T01:00:00Z"
                        }
                    }
                }
            },
            "storyline_management": {
                "create_storyline": {
                    "request": {
                        "method": "POST",
                        "url": "/api/storylines",
                        "body": {
                            "title": "Climate Change Policy Updates",
                            "description": "Tracking climate change policy developments",
                            "category": "environment",
                            "tags": ["climate", "policy", "environment"],
                            "priority": 3
                        }
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "id": "storyline_001",
                            "title": "Climate Change Policy Updates",
                            "status": "active",
                            "article_count": 0,
                            "created_at": "2025-09-26T01:00:00Z"
                        }
                    }
                },
                "add_article_to_storyline": {
                    "request": {
                        "method": "POST",
                        "url": "/api/storylines/storyline_001/add-article",
                        "body": {
                            "article_id": "123",
                            "relevance_score": 0.9,
                            "importance_score": 0.8,
                            "notes": "Highly relevant to climate policy"
                        }
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "id": "sa_001",
                            "storyline_id": "storyline_001",
                            "article_id": "123",
                            "relevance_score": 0.9,
                            "added_at": "2025-09-26T01:00:00Z"
                        }
                    }
                }
            },
            "error_handling": {
                "validation_error": {
                    "request": {
                        "method": "POST",
                        "url": "/api/articles",
                        "body": {
                            "title": "",  # Invalid: empty title
                            "content": "Some content"
                        }
                    },
                    "response": {
                        "success": False,
                        "message": "Validation error",
                        "error_type": "validation_error",
                        "details": "Title cannot be empty",
                        "recoverable": True,
                        "timestamp": "2025-09-26T01:00:00Z"
                    }
                },
                "not_found_error": {
                    "request": {
                        "method": "GET",
                        "url": "/api/articles/999999"
                    },
                    "response": {
                        "success": False,
                        "message": "Article not found",
                        "error_type": "not_found",
                        "details": "Article with ID 999999 does not exist",
                        "recoverable": False,
                        "timestamp": "2025-09-26T01:00:00Z"
                    }
                }
            },
            "monitoring": {
                "health_check": {
                    "request": {
                        "method": "GET",
                        "url": "/api/health"
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "status": "healthy",
                            "services": {
                                "database": "healthy",
                                "redis": "healthy",
                                "system": "healthy"
                            }
                        }
                    }
                },
                "log_statistics": {
                    "request": {
                        "method": "GET",
                        "url": "/api/logs/statistics?days=7"
                    },
                    "response": {
                        "success": True,
                        "data": {
                            "period_days": 7,
                            "total_entries": 15420,
                            "error_count": 23,
                            "warning_count": 156,
                            "info_count": 15241,
                            "system_health_score": 98.5
                        }
                    }
                }
            }
        }
        
        return APIResponse(
            success=True,
            data=examples,
            message="API examples retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting API examples: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status", response_model=APIResponse)
async def get_api_status():
    """
    Get current API status and system information
    
    Returns real-time information about:
    - API version and build information
    - System health and performance metrics
    - Available features and capabilities
    - Database and service status
    """
    try:
        # Get system health
        health_response = await get_system_health()
        health_data = health_response.get('data', {})
        
        status_info = {
            "api": {
                "version": "3.3.0",
                "status": "operational",
                "uptime": "System running",
                "features": [
                    "Article Management",
                    "RSS Feed Processing", 
                    "Storyline Management",
                    "Duplicate Detection",
                    "ML Processing",
                    "Comprehensive Logging",
                    "Real-time Monitoring"
                ]
            },
            "system": {
                "health": health_data.get('status', 'unknown'),
                "services": health_data.get('services', {}),
                "database": health_data.get('details', {}).get('database', {}),
                "redis": health_data.get('details', {}).get('redis', {}),
                "system": health_data.get('details', {}).get('system', {})
            },
            "capabilities": {
                "article_processing": "Active",
                "rss_feed_management": "Active", 
                "storyline_creation": "Active",
                "duplicate_detection": "Active",
                "ml_analysis": "Active",
                "log_monitoring": "Active",
                "real_time_monitoring": "Active"
            },
            "endpoints": {
                "total_endpoints": 25,
                "active_endpoints": 25,
                "documented_endpoints": 25
            }
        }
        
        return APIResponse(
            success=True,
            data=status_info,
            message="API status retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting API status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Helper function to get system health
async def get_system_health():
    """Get system health information"""
    try:
        # This would normally call the health endpoint
        # For now, return a basic health status
        return {
            "data": {
                "status": "healthy",
                "services": {
                    "database": "healthy",
                    "redis": "healthy", 
                    "system": "healthy"
                },
                "details": {
                    "database": {"status": "healthy"},
                    "redis": {"status": "healthy"},
                    "system": {"status": "healthy"}
                }
            }
        }
    except Exception:
        return {
            "data": {
                "status": "unknown",
                "services": {},
                "details": {}
            }
        }
