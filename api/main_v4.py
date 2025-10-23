"""
News Intelligence System v4.0 - Domain-Driven FastAPI Application
Uses Llama 3.1 8B (primary) and Mistral 7B (secondary) models
"""

import os
import sys
import logging
import threading
import time
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
sys.path.append(os.path.join(os.path.dirname(__file__), 'shared'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'domains'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import domain routers
from domains.news_aggregation.routes.news_aggregation import router as news_aggregation_router
from domains.content_analysis.routes.content_analysis import router as content_analysis_router
from domains.storyline_management.routes.storyline_management import router as storyline_management_router
from domains.intelligence_hub.routes.intelligence_hub import router as intelligence_hub_router
from domains.user_management.routes.user_management import router as user_management_router
from domains.system_monitoring.routes.system_monitoring import router as system_monitoring_router

# Import compatibility layer
from compatibility.v3_compatibility import compatibility_router

# Import shared services
from shared.services.llm_service import llm_service

# Import database configuration
from shared.database.connection import get_db_connection, check_database_health

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting News Intelligence System v4.0")
    
    # Initialize LLM service
    try:
        llm_status = await llm_service.get_model_status()
        if llm_status["success"]:
            logger.info(f"✅ LLM Service initialized - Primary: {llm_status.get('primary_model')}, Secondary: {llm_status.get('secondary_model')}")
        else:
            logger.warning(f"⚠️ LLM Service initialization failed: {llm_status.get('error')}")
        
        app.state.llm_service = llm_service
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM service: {e}")
        app.state.llm_service = None
    
    # Start automation manager in background thread
    try:
        from services.automation_manager import AutomationManager
        from services.ml_processing_service import MLProcessingService
        import threading
        
        # Use localhost database configuration
        db_config = {
            "host": "localhost",
            "database": "news_intelligence", 
            "user": "newsapp",
            "password": "newsapp_password",
            "port": "5432"
        }
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
        
        # Start ML processing service
        try:
            ml_processing_service = MLProcessingService()
            ml_processing_service.start_processing()
            logger.info("✅ ML Processing Service started automatically")
            app.state.ml_processing = ml_processing_service
        except Exception as e:
            logger.error(f"❌ Failed to start ML Processing Service: {e}")
    except Exception as e:
        logger.error(f"Failed to start automation manager: {e}")
        # Continue without automation if it fails
        app.state.automation = None
        app.state.automation_thread = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System v4.0")
    
    # Close LLM service
    try:
        if hasattr(app.state, 'llm_service') and app.state.llm_service:
            await app.state.llm_service.close()
            logger.info("LLM service closed")
    except Exception as e:
        logger.error(f"Error closing LLM service: {e}")
    
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
    title="News Intelligence System v4.0",
    description="""
    ## News Intelligence System v4.0 - Domain-Driven AI Platform
    
    A comprehensive news aggregation and analysis platform featuring:
    
    * **Domain-Driven Architecture** - Organized into 6 business domains
    * **AI-Powered Analysis** - Using Llama 3.1 8B (primary) and Mistral 7B (secondary)
    * **News Aggregation** - RSS feed processing and article ingestion
    * **Content Analysis** - Sentiment, entities, summarization, bias detection
    * **Storyline Management** - RAG-enhanced narrative creation and timeline generation
    * **Intelligence Hub** - Predictive analytics and strategic insights
    * **User Management** - Personalized experiences and behavior analysis
    * **System Monitoring** - Comprehensive health and performance tracking
    
    ### Key Features
    - **Local AI Models Only** - Self-contained system using Ollama-hosted models
    - **Hybrid Processing** - Real-time operations (<5s) + batch processing (5-20s)
    - **Quality-First Approach** - Journalist-quality output with professional standards
    - **Domain-Driven Design** - Business-focused organization with integrated AI capabilities
    - **Scalable Architecture** - Microservice-ready structure for future growth
    
    ### Model Performance
    - **Primary Model**: Llama 3.1 8B (2.93s for 200 words, 73.0 MMLU score)
    - **Secondary Model**: Mistral 7B (4.17s for 200 words, competitive quality)
    - **Resource Usage**: 9.3GB total storage (vs 109GB+ with previous models)
    
    ### Authentication
    Currently in development mode - no authentication required.
    Production deployment will include JWT-based authentication.
    
    ### Rate Limiting
    Currently no rate limiting in development mode.
    Production deployment will include rate limiting.
    """,
    version="4.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {
            "name": "News Aggregation",
            "description": "RSS feed processing, article ingestion, and content quality assessment"
        },
        {
            "name": "Content Analysis", 
            "description": "Sentiment analysis, entity extraction, summarization, and bias detection"
        },
        {
            "name": "Storyline Management",
            "description": "Storyline creation, timeline generation, and RAG-enhanced analysis"
        },
        {
            "name": "Intelligence Hub",
            "description": "Predictive analytics, trend analysis, and strategic insights"
        },
        {
            "name": "User Management",
            "description": "User profiles, preferences, and personalized experiences"
        },
        {
            "name": "System Monitoring",
            "description": "Health checks, performance monitoring, and alerting"
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
    """Global exception handler for comprehensive error handling"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "message": "Internal server error",
            "error": str(exc),
            "error_type": "InternalServerError",
            "recoverable": False,
            "timestamp": datetime.now().isoformat()
        }
    )

# Include domain routers
app.include_router(news_aggregation_router)
app.include_router(content_analysis_router)
app.include_router(storyline_management_router)
app.include_router(intelligence_hub_router)
app.include_router(user_management_router)
app.include_router(system_monitoring_router)

# Include v3.0 compatibility layer
app.include_router(compatibility_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System v4.0",
            "version": "4.0.0",
            "architecture": "Domain-Driven Design",
            "ai_models": {
                "primary": "llama3.1:8b",
                "secondary": "mistral:7b"
            },
            "domains": [
                "news_aggregation",
                "content_analysis", 
                "storyline_management",
                "intelligence_hub",
                "user_management",
                "system_monitoring"
            ],
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "message": "News Intelligence System v4.0 is running",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
