#!/usr/bin/env python3
"""
News Intelligence System v2.9.0 - FastAPI Application
Modern, high-performance API with automatic OpenAPI documentation
"""

import os
import sys
import time
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import API modules
from routes import (
    articles,
    stories,
    intelligence,
    ml,
    monitoring,
    health,
    dashboard,
    rss,
    deduplication,
    entities,
    clusters,
    sources,
    search,
    rag,
    ml_management,
    automation,
    story_management
)

# Import middleware
from middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    SecurityMiddleware
)

# Global state for application lifecycle
app_state: Dict[str, Any] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events"""
    # Startup
    logger.info("Starting News Intelligence System v2.9.0")
    
    # Initialize application state
    app_state["startup_time"] = time.time()
    app_state["version"] = "2.9.0"
    
    # Initialize database connections
    try:
        from config.database import init_database
        await init_database()
        app_state["database_connected"] = True
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        app_state["database_connected"] = False
    
    # Initialize ML services
    try:
        from modules.ml.ml_pipeline import MLPipeline
        from config.database import get_db_config
        db_config = get_db_config()
        app_state["ml_pipeline"] = MLPipeline(db_config)
        app_state["ml_available"] = True
        logger.info("ML pipeline initialized")
    except Exception as e:
        logger.error(f"Failed to initialize ML pipeline: {e}")
        app_state["ml_available"] = False
    
    # Initialize monitoring
    try:
        from modules.monitoring.resource_logger import ResourceLogger
        app_state["monitoring"] = ResourceLogger()
        app_state["monitoring_available"] = True
        logger.info("Monitoring system initialized")
    except Exception as e:
        logger.error(f"Failed to initialize monitoring: {e}")
        app_state["monitoring_available"] = False
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System v3.0")
    
    # Cleanup resources
    if "ml_pipeline" in app_state:
        try:
            app_state["ml_pipeline"].cleanup()
        except Exception as e:
            logger.error(f"Error during ML pipeline cleanup: {e}")
    
    if "monitoring" in app_state:
        try:
            app_state["monitoring"].cleanup()
        except Exception as e:
            logger.error(f"Error during monitoring cleanup: {e}")

# Create FastAPI application
app = FastAPI(
    title="News Intelligence System API",
    description="Comprehensive news aggregation and analysis platform powered by AI",
    version="2.9.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(SecurityMiddleware)

# Include API routes
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(articles.router, prefix="/api/articles", tags=["Articles"])
app.include_router(stories.router, prefix="/api/stories", tags=["Stories"])
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["Intelligence"])
app.include_router(ml.router, prefix="/api/ml", tags=["Machine Learning"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoring"])
app.include_router(rss.router, prefix="/api/rss", tags=["RSS Management"])
app.include_router(deduplication.router, prefix="/api/deduplication", tags=["Deduplication"])
app.include_router(entities.router, prefix="/api/entities", tags=["Entities"])
app.include_router(clusters.router, prefix="/api/clusters", tags=["Clusters"])
app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(rag.router, prefix="/api/rag", tags=["RAG System"])
app.include_router(ml_management.router, prefix="/api/ml-management", tags=["ML Management"])
app.include_router(automation.router, prefix="/api/automation", tags=["Automation"])
app.include_router(story_management.router, prefix="/api/story-management", tags=["Story Management"])

# Mount static files (after API routes to prevent override)
if os.path.exists("web/build"):
    # Mount static assets at /static path
    app.mount("/static", StaticFiles(directory="web/build/static"), name="static")
    
    # Add specific routes for frontend (avoiding API path conflicts)
    @app.get("/dashboard")
    async def serve_dashboard():
        """Serve frontend for dashboard route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/intelligence")
    async def serve_intelligence():
        """Serve frontend for intelligence route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/articles")
    async def serve_articles():
        """Serve frontend for articles route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/stories")
    async def serve_stories():
        """Serve frontend for stories route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/rss")
    async def serve_rss():
        """Serve frontend for RSS route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/deduplication")
    async def serve_deduplication():
        """Serve frontend for deduplication route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/ml")
    async def serve_ml():
        """Serve frontend for ML route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")
    
    @app.get("/monitoring")
    async def serve_monitoring():
        """Serve frontend for monitoring route"""
        if os.path.exists("web/build/index.html"):
            return FileResponse("web/build/index.html")
        else:
            raise HTTPException(status_code=404, detail="Frontend not built")

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="News Intelligence System API",
        version="2.9.0",
        description="""
        ## News Intelligence System API v2.9.0
        
        A comprehensive news aggregation and analysis platform powered by AI.
        
        ### Features
        - **Automated News Collection**: Multi-source RSS feed collection
        - **AI-Powered Analysis**: Content summarization and classification
        - **Story Evolution Tracking**: Monitor story development over time
        - **Intelligence Delivery**: Real-time dashboards and analytics
        
        ### Authentication
        Currently, the API uses simple authentication. In production, implement proper JWT or OAuth2.
        
        ### Rate Limiting
        API endpoints are rate-limited to prevent abuse. Check response headers for rate limit information.
        """,
        routes=app.routes,
    )
    
    # Add custom tags
    openapi_schema["tags"] = [
        {
            "name": "Health",
            "description": "System health and status endpoints"
        },
        {
            "name": "Dashboard",
            "description": "Dashboard data and statistics"
        },
        {
            "name": "Articles",
            "description": "Article management and analysis"
        },
        {
            "name": "Stories",
            "description": "Story tracking and evolution"
        },
        {
            "name": "Intelligence",
            "description": "Intelligence data and insights"
        },
        {
            "name": "Machine Learning",
            "description": "ML pipeline and AI services"
        },
        {
            "name": "Monitoring",
            "description": "System monitoring and metrics"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": getattr(request.state, "request_id", None)
        }
    )

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with system information"""
    return {
        "name": "News Intelligence System",
        "version": "3.0.0",
        "status": "operational",
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json"
    }

# API info endpoint
@app.get("/api")
async def api_info():
    """API information endpoint"""
    return {
        "name": "News Intelligence System API",
        "version": "3.0.0",
        "description": "Comprehensive news aggregation and analysis platform",
        "endpoints": {
            "health": "/api/health",
            "dashboard": "/api/dashboard",
            "articles": "/api/articles",
            "stories": "/api/stories",
            "intelligence": "/api/intelligence",
            "ml": "/api/ml",
            "monitoring": "/api/monitoring"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    workers = int(os.getenv("WORKERS", 1))
    reload = os.getenv("RELOAD", "false").lower() == "true"
    
    logger.info(f"Starting News Intelligence System API on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level="info"
    )
