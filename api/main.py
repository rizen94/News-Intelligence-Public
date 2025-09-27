"""
News Intelligence System v3.0 - Production FastAPI Application
Robust, production-ready API with comprehensive error handling
"""

import os
import sys
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Configure comprehensive logging system
from config.logging_config import setup_logging, get_component_logger
from middleware.error_handling import get_error_handler

# Setup logging system
logging_system = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_dir="/app/logs",
    enable_console=True,
    enable_file=True,
    enable_json=True,
    enable_ml_logging=True
)

logger = get_component_logger('app')
error_handler = get_error_handler()

# Import route modules
from routes.articles import router as articles_router
from routes.rss_feeds import router as rss_feeds_router
from routes.health import router as health_router
from routes.fallback_logging import router as fallback_router
from routes.timeline import router as timeline_router
from routes.story_management import router as story_management_router
from routes.monitoring import router as monitoring_router
from routes.intelligence import router as intelligence_router
from routes.dashboard import router as dashboard_router
from routes.storylines import router as storylines_router
from routes.enhanced_storylines import router as enhanced_storylines_router
from routes.article_processing import router as article_processing_router
from routes.deduplication_simple import router as deduplication_router
from routes.log_management import router as log_management_router
from routes.api_documentation import router as api_documentation_router
# # from routes.enhanced_analysis import router as enhanced_analysis_router
from routes.pipeline_monitoring import router as pipeline_monitoring_router

# Import unified database configuration
from config.database import get_db, get_db_config, check_database_health

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting News Intelligence System v3.0")
    
    # Start automation manager in background thread
    try:
        from services.automation_manager import AutomationManager
        from config.database import get_db_config
        import threading
        
        db_config = get_db_config()
        automation = AutomationManager(db_config)
        
        # Start automation in background thread
        def start_automation():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(automation.start())
        
        automation_thread = threading.Thread(target=start_automation, daemon=True)
        automation_thread.start()
        
        logger.info("Automation manager started in background thread")
        
        # Store automation manager for shutdown
        app.state.automation = automation
        app.state.automation_thread = automation_thread
    except Exception as e:
        logger.error(f"Failed to start automation manager: {e}")
        # Continue without automation if it fails
        app.state.automation = None
        app.state.automation_thread = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System v3.0")
    
    # Stop automation manager
    try:
        if hasattr(app.state, 'automation') and app.state.automation:
            # Signal automation to stop
            app.state.automation.is_running = False
            logger.info("Automation manager stop signal sent")
            
            # Wait for automation thread to finish (with timeout)
            if hasattr(app.state, 'automation_thread') and app.state.automation_thread:
                app.state.automation_thread.join(timeout=5)
                if app.state.automation_thread.is_alive():
                    logger.warning("Automation thread did not stop gracefully")
                else:
                    logger.info("Automation manager stopped")
    except Exception as e:
        logger.error(f"Error stopping automation manager: {e}")

# Create FastAPI application
app = FastAPI(
    title="News Intelligence System v3.3.0",
    description="""
    ## News Intelligence System - AI-Powered News Analysis Platform
    
    A comprehensive news aggregation and analysis platform featuring:
    
    * **Article Management** - Process and analyze news articles with AI
    * **RSS Feed Processing** - Automated collection from multiple news sources
    * **Storyline Creation** - Organize articles into coherent storylines
    * **Duplicate Detection** - Advanced clustering and deduplication
    * **ML Processing** - AI-powered content analysis and summarization
    * **Real-time Monitoring** - Comprehensive logging and system health
    * **API Documentation** - Complete endpoint documentation and examples
    
    ### Key Features
    - **Multi-source RSS aggregation** with intelligent filtering
    - **AI-powered content analysis** using Llama 3.1 70B
    - **Advanced duplicate detection** with semantic similarity
    - **Storyline management** with automatic suggestions
    - **Comprehensive logging** with structured data storage
    - **Real-time monitoring** and health assessment
    
    ### Authentication
    Currently in development mode - no authentication required.
    Production deployment will include JWT-based authentication.
    
    ### Rate Limiting
    Currently no rate limiting in development mode.
    Production deployment will include rate limiting.
    """,
    version="3.3.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "Articles",
            "description": "Article management and processing operations"
        },
        {
            "name": "RSS Feeds", 
            "description": "RSS feed management and configuration"
        },
        {
            "name": "Storylines",
            "description": "Storyline creation and management"
        },
        {
            "name": "Deduplication",
            "description": "Duplicate detection and clustering"
        },
        {
            "name": "Log Management",
            "description": "Log viewing, analysis, and management"
        },
        {
            "name": "API Documentation",
            "description": "Comprehensive API documentation and examples"
        },
        {
            "name": "Monitoring",
            "description": "System monitoring and health checks"
        },
        {
            "name": "Health",
            "description": "System health and status endpoints"
        }
    ],
    contact={
        "name": "News Intelligence System",
        "url": "https://github.com/news-intelligence",
        "email": "support@news-intelligence.com"
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure appropriately for production
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Use comprehensive error handling
    error_response = error_handler.handle_exception(
        exception=exc,
        context={
            'endpoint': str(request.url),
            'method': request.method,
            'user_agent': request.headers.get('user-agent'),
            'client_ip': request.client.host if request.client else None
        },
        request=request
    )
    
    return JSONResponse(
        status_code=error_response['status_code'],
        content={
            "success": False,
            "data": None,
            "message": error_response['message'],
            "error": error_response['details'],
            "error_type": error_response['error_type'],
            "recoverable": error_response.get('recoverable', False),
            "timestamp": datetime.now().isoformat()
        }
    )

# Include routers
app.include_router(articles_router, prefix="/api")
app.include_router(rss_feeds_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(fallback_router, prefix="/api")
app.include_router(timeline_router, prefix="/api")
app.include_router(story_management_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(storylines_router, prefix="/api")
app.include_router(enhanced_storylines_router, prefix="/api")
app.include_router(article_processing_router, prefix="/api")
app.include_router(deduplication_router, prefix="/api")
app.include_router(log_management_router, prefix="/api")
app.include_router(api_documentation_router, prefix="/api")
# # app.include_router(enhanced_analysis_router, prefix="/api")
app.include_router(pipeline_monitoring_router, prefix="/api")

# Root endpoint
@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System",
            "version": "3.1.0",
            "status": "operational",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "message": "News Intelligence System v3.0 is running",
        "timestamp": "2025-09-05T17:00:00Z"
    }

# Additional endpoints for frontend compatibility (without /api prefix)
@app.get("/api/storylines")
async def get_storylines_frontend():
    """Frontend-compatible storyline endpoint"""
    try:
        from services.storyline_service import StorylineService
        storyline_service = StorylineService()
        result = await storyline_service.get_storylines()
        
        if "error" in result:
            return {"success": False, "message": "Failed to retrieve storylines", "error": result["error"]}
        
        return {"success": True, "data": result, "message": f"Retrieved {len(result['storylines'])} storylines"}
    except Exception as e:
        logger.error(f"Error retrieving storylines: {str(e)}")
        return {"success": False, "message": "Internal server error", "error": str(e)}

@app.post("/api/storylines")
async def create_storyline_frontend(request: dict):
    """Frontend-compatible storyline creation endpoint"""
    try:
        from services.storyline_service import StorylineService
        storyline_service = StorylineService()
        result = await storyline_service.create_storyline(
            title=request.get('title', ''),
            description=request.get('description', '')
        )
        
        if "error" in result:
            return {"success": False, "message": "Failed to create storyline", "error": result["error"]}
        
        return {"success": True, "data": {"storyline": result}, "message": "Storyline created successfully"}
    except Exception as e:
        logger.error(f"Error creating storyline: {str(e)}")
        return {"success": False, "message": "Internal server error", "error": str(e)}

@app.post("/api/storylines/{storyline_id}/add-article")
async def add_article_to_storyline_frontend(storyline_id: int, request: dict):
    """Frontend-compatible add article to storyline endpoint"""
    try:
        from services.storyline_service import StorylineService
        storyline_service = StorylineService()
        
        article_id = request.get('article_id')
        if not article_id:
            return {"success": False, "message": "Article ID is required"}
        
        result = await storyline_service.add_article_to_storyline(
            storyline_id=str(storyline_id),
            article_id=str(article_id)
        )
        
        if "error" in result:
            return {"success": False, "message": "Failed to add article to storyline", "error": result["error"]}
        
        return {"success": True, "message": "Article added to storyline successfully"}
    except Exception as e:
        logger.error(f"Error adding article to storyline: {str(e)}")
        return {"success": False, "message": "Internal server error", "error": str(e)}

@app.post("/article-processing/fetch-full-content/{article_id}")
async def fetch_full_content_frontend(article_id: int):
    """Frontend-compatible article content fetching endpoint"""
    try:
        from config.database import get_db_connection
        from psycopg2.extras import RealDictCursor
        
        conn = get_db_connection()
        if not conn:
            return {
                "success": False,
                "data": {"error": "Database connection failed"},
                "message": "Failed to fetch article content"
            }
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, content, url, published_at, source, 
                           summary, word_count, reading_time, quality_score
                    FROM articles 
                    WHERE id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                
                if not article:
                    return {
                        "success": False,
                        "data": {"error": "Article not found"},
                        "message": "Article not found"
                    }
                
                # Format the content for better readability
                full_content = f"""
# {article['title']}

**Source:** {article['source']}  
**Published:** {article['published_at']}  
**URL:** {article['url']}

---

{article['content']}

---

**Summary:** {article['summary'] or 'No summary available'}

**Word Count:** {article['word_count'] or 'Unknown'}  
**Reading Time:** {article['reading_time'] or 'Unknown'} minutes  
**Quality Score:** {article['quality_score'] or 'Not rated'}
                """.strip()
                
                return {
                    "success": True,
                    "data": {
                        "article_id": article_id,
                        "full_content": full_content,
                        "title": article['title'],
                        "source": article['source'],
                        "url": article['url'],
                        "status": "fetched"
                    },
                    "message": "Full content fetched successfully"
                }
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error fetching article content: {e}")
        return {
            "success": False,
            "data": {"error": str(e)},
            "message": "Failed to fetch article content"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
