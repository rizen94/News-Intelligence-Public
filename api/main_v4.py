"""
News Intelligence System v4.0 - Domain-Driven FastAPI Application
Uses Llama 3.1 8B (primary) and Mistral 7B (secondary) models
"""

import os
import sys
import logging
import threading
import time
import asyncio
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
from domains.news_aggregation.routes.rss_duplicate_management import router as rss_duplicate_router
from domains.content_analysis.routes.content_analysis import router as content_analysis_router
from domains.content_analysis.routes.article_deduplication import router as article_deduplication_router
from domains.content_analysis.routes.topic_management import router as topic_management_router
from domains.content_analysis.routes.topic_queue_management import router as topic_queue_management_router
from domains.content_analysis.routes.llm_activity_monitoring import router as llm_activity_monitoring_router
# Import consolidated storyline router (includes all feature modules)
from domains.storyline_management.routes import router as storyline_management_router
from domains.storyline_management.routes.storyline_automation import router as storyline_automation_router
from domains.storyline_management.routes.storyline_discovery import router as storyline_discovery_router
from domains.storyline_management.routes.storyline_consolidation import router as storyline_consolidation_router
from domains.intelligence_hub.routes.intelligence_hub import router as intelligence_hub_router
from domains.intelligence_hub.routes.intelligence_analysis import router as intelligence_analysis_router
from domains.intelligence_hub.routes.rag_queries import router as rag_queries_router
from domains.intelligence_hub.routes.content_synthesis import router as content_synthesis_router
from domains.finance.routes.finance import router as finance_router
from domains.user_management.routes.user_management import router as user_management_router
from domains.system_monitoring.routes.system_monitoring import router as system_monitoring_router
from domains.system_monitoring.routes.route_supervisor import router as route_supervisor_router

# Import pipeline monitoring
# from routes.pipeline_monitoring import router as pipeline_monitoring_router

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
    
    # Initialize database connection pool early (persistent connection)
    try:
        from shared.database.connection import _init_pool, get_db_config
        
        # HARD REQUIREMENT: Enforce SSH tunnel usage
        if not os.getenv("DB_HOST"):
            os.environ["DB_HOST"] = "localhost"
            os.environ["DB_PORT"] = "5433"
            logger.info("✅ Defaulting to SSH tunnel: DB_HOST=localhost DB_PORT=5433")
        
        # Verify SSH tunnel is required and running
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = int(os.getenv("DB_PORT", "5433"))
        
        if db_host not in ['localhost', '127.0.0.1', '::1'] or db_port != 5433:
            logger.error("❌ INVALID CONFIGURATION: System MUST use SSH tunnel")
            logger.error(f"   Current: DB_HOST={db_host} DB_PORT={db_port}")
            logger.error("   Required: DB_HOST=localhost DB_PORT=5433")
            raise ValueError("System MUST use SSH tunnel (localhost:5433). Direct connections are blocked.")
        
        # Check if SSH tunnel is running
        import subprocess
        tunnel_running = subprocess.run(
            ["pgrep", "-f", "ssh -L 5433:localhost:5432.*192.168.93.100"],
            capture_output=True
        ).returncode == 0
        
        if not tunnel_running:
            logger.error("❌ SSH TUNNEL NOT RUNNING: Required tunnel is not active")
            logger.error("   Run: ./scripts/setup_nas_ssh_tunnel.sh")
            logger.error("   The tunnel must be running before starting the API server")
            raise ValueError("SSH tunnel (localhost:5433) must be running. Run setup_nas_ssh_tunnel.sh")
        
        logger.info("✅ SSH tunnel verified: localhost:5433 -> 192.168.93.100:5432")
        
        # Initialize connection pool (persistent connections)
        try:
            pool = _init_pool()
            logger.info("✅ Database connection pool initialized (persistent connections)")
            
            # Test connection
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                conn.close()
                logger.info("✅ Database connection test successful")
            else:
                logger.error("❌ Database connection test failed")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connection pool: {e}")
            logger.error("   API will not be able to access database without DB_HOST environment variable")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
    
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
        
        # Use NAS database via SSH tunnel
        db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "database": os.getenv("DB_NAME", "news_intelligence"), 
            "user": os.getenv("DB_USER", "newsapp"),
            "password": os.getenv("DB_PASSWORD", "newsapp_password"),
            "port": os.getenv("DB_PORT", "5433")  # SSH tunnel port
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
        
        # Start topic extraction queue workers for all domains
        try:
            from domains.content_analysis.services.topic_extraction_queue_worker import TopicExtractionQueueWorker
            from shared.database.connection import get_db_connection
            
            def start_queue_workers_background():
                """Start queue workers in background thread"""
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                async def start_workers():
                    """Start queue workers for all active domains"""
                    domains = ['politics', 'finance', 'science-tech']
                    workers = []
                    for domain in domains:
                        try:
                            schema = domain.replace('-', '_')
                            worker = TopicExtractionQueueWorker(get_db_connection, schema=schema)
                            workers.append(worker)
                            # Start worker in background task
                            asyncio.create_task(worker.start())
                            logger.info(f"✅ Started topic extraction queue worker for {domain}")
                        except Exception as e:
                            logger.error(f"❌ Failed to start queue worker for {domain}: {e}")
                    
                    # Keep workers running
                    while True:
                        await asyncio.sleep(60)  # Check every minute
                
                loop.run_until_complete(start_workers())
            
            # Start queue workers in background thread
            queue_worker_thread = threading.Thread(target=start_queue_workers_background, daemon=True)
            queue_worker_thread.start()
            app.state.queue_worker_thread = queue_worker_thread
            logger.info("✅ Topic extraction queue workers started automatically in background")
        except Exception as e:
            logger.error(f"❌ Failed to start topic extraction queue workers: {e}")
    except Exception as e:
        logger.error(f"Failed to start automation manager: {e}")
        # Continue without automation if it fails
        app.state.automation = None
        app.state.automation_thread = None
    
    # Start Route Supervisor
    try:
        from shared.services.route_supervisor import get_route_supervisor
        import asyncio
        
        supervisor = get_route_supervisor()
        
        # Start monitoring in background
        def start_supervisor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(supervisor.start_monitoring())
        
        supervisor_thread = threading.Thread(target=start_supervisor, daemon=True)
        supervisor_thread.start()
        
        logger.info("✅ Route Supervisor started - monitoring routes and database connections")
        app.state.route_supervisor = supervisor
        app.state.route_supervisor_thread = supervisor_thread
    except Exception as e:
        logger.error(f"❌ Failed to start Route Supervisor: {e}")
        app.state.route_supervisor = None
        app.state.route_supervisor_thread = None
    
    # Start Storyline Consolidation Service
    try:
        from services.storyline_consolidation_service import (
            get_consolidation_service,
            CONSOLIDATION_INTERVAL_MINUTES
        )
        
        consolidation_service = get_consolidation_service(db_config)
        
        # Background thread for periodic consolidation
        consolidation_stop_event = threading.Event()
        
        def run_periodic_consolidation():
            """Run consolidation periodically"""
            interval_seconds = CONSOLIDATION_INTERVAL_MINUTES * 60
            while not consolidation_stop_event.is_set():
                try:
                    logger.info("🔄 Running scheduled storyline consolidation...")
                    result = consolidation_service.run_all_domains()
                    logger.info(f"✅ Consolidation complete: {result.get('stats', {})}")
                except Exception as e:
                    logger.error(f"❌ Consolidation error: {e}")
                
                # Wait for next interval (or stop signal)
                consolidation_stop_event.wait(interval_seconds)
        
        consolidation_thread = threading.Thread(
            target=run_periodic_consolidation, 
            daemon=True,
            name="StorylineConsolidation"
        )
        consolidation_thread.start()
        
        logger.info(f"✅ Storyline Consolidation Service started - runs every {CONSOLIDATION_INTERVAL_MINUTES} minutes")
        app.state.consolidation_service = consolidation_service
        app.state.consolidation_thread = consolidation_thread
        app.state.consolidation_stop_event = consolidation_stop_event
    except Exception as e:
        logger.error(f"❌ Failed to start Storyline Consolidation Service: {e}")
        app.state.consolidation_service = None
    
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
    
    # Stop Route Supervisor
    try:
        if hasattr(app.state, 'route_supervisor') and app.state.route_supervisor:
            app.state.route_supervisor.stop_monitoring()
            logger.info("Route Supervisor stopped")
    except Exception as e:
        logger.error(f"Error stopping Route Supervisor: {e}")
    
    # Stop Consolidation Service
    try:
        if hasattr(app.state, 'consolidation_stop_event') and app.state.consolidation_stop_event:
            app.state.consolidation_stop_event.set()
            if hasattr(app.state, 'consolidation_thread') and app.state.consolidation_thread:
                app.state.consolidation_thread.join(timeout=5)
            logger.info("Storyline Consolidation Service stopped")
    except Exception as e:
        logger.error(f"Error stopping Consolidation Service: {e}")

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
app.include_router(rss_duplicate_router)
app.include_router(content_analysis_router)
app.include_router(topic_management_router)
app.include_router(article_deduplication_router)
app.include_router(topic_queue_management_router)
app.include_router(llm_activity_monitoring_router)
# Discovery router FIRST (has specific routes like /compare, /evolution)
app.include_router(storyline_discovery_router)
app.include_router(storyline_consolidation_router)
app.include_router(storyline_automation_router)
# Management router LAST (has catch-all /{storyline_id} route)
app.include_router(storyline_management_router)
app.include_router(intelligence_hub_router)
app.include_router(intelligence_analysis_router)
app.include_router(rag_queries_router)
app.include_router(content_synthesis_router)
app.include_router(finance_router)
app.include_router(user_management_router)
app.include_router(system_monitoring_router)
app.include_router(route_supervisor_router)
# app.include_router(pipeline_monitoring_router)

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
