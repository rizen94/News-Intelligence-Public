"""
Simple API for frontend testing
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

app = FastAPI(
    title="News Intelligence System v3.0",
    description="Simple API for frontend testing",
    version="3.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System",
            "version": "3.0",
            "status": "operational"
        },
        "message": "News Intelligence System v3.0 is running"
    }

@app.get("/api/health/")
async def health():
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "message": "System operational",
            "version": "3.3.0"
        }
    }

@app.get("/api/articles/")
async def get_articles():
    return {
        "success": True,
        "data": {
            "articles": [
                {
                    "id": 1,
                    "title": "Sample Article 1",
                    "content": "This is a sample article for testing the frontend.",
                    "source": "Test Source",
                    "published_date": "2025-09-09T10:00:00Z",
                    "category": "Technology"
                },
                {
                    "id": 2,
                    "title": "Sample Article 2", 
                    "content": "Another sample article for testing purposes.",
                    "source": "Test Source 2",
                    "published_date": "2025-09-09T11:00:00Z",
                    "category": "News"
                }
            ],
            "total_count": 2,
            "page": 1,
            "limit": 20,
            "total_pages": 1
        }
    }

@app.get("/api/articles/stats/overview")
async def get_article_stats():
    return {
        "success": True,
        "data": {
            "total_articles": 2,
            "articles_by_source": {"Test Source": 1, "Test Source 2": 1},
            "articles_by_category": {"Technology": 1, "News": 1},
            "articles_by_status": {"published": 2},
            "recent_articles": 2,
            "avg_quality_score": 0.85
        }
    }

@app.get("/api/rss/feeds/")
async def get_rss_feeds():
    return {
        "success": True,
        "data": {
            "feeds": [
                {
                    "id": 1,
                    "name": "Test RSS Feed",
                    "url": "https://example.com/rss",
                    "status": "active",
                    "last_updated": "2025-09-09T10:00:00Z",
                    "article_count": 5
                }
            ],
            "total_count": 1
        }
    }

@app.get("/api/rss/feeds/stats/overview")
async def get_rss_stats():
    return {
        "success": True,
        "data": {
            "total_feeds": 1,
            "active_feeds": 1,
            "inactive_feeds": 0,
            "total_articles": 5
        }
    }

@app.get("/api/storylines/")
async def get_storylines():
    return {
        "success": True,
        "data": {
            "storylines": [
                {
                    "id": 1,
                    "title": "Sample Storyline",
                    "description": "A sample storyline for testing",
                    "status": "active",
                    "article_count": 3,
                    "updated_at": "2025-09-09T10:00:00Z"
                }
            ]
        }
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)


