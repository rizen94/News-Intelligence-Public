"""
News Intelligence System v5.0 - Domain-Driven FastAPI Application
Uses Llama 3.1 8B (primary) and Mistral 7B (secondary) models
"""

# Load .env before any config — override=False so shell/env take precedence
from dotenv import load_dotenv
load_dotenv(override=False)

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

# Configure logging from centralized config (uses settings.LOG_LEVEL, LOG_DIR)
try:
    from config.logging_config import setup_logging
    setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    logger.warning("Centralized logging unavailable, using basicConfig: %s", e)

# Import domain routers (consolidated — one per domain)
from domains.news_aggregation.routes import router as news_aggregation_router
from domains.content_analysis.routes import router as content_analysis_router
from domains.storyline_management.routes import router as storyline_management_router
from domains.intelligence_hub.routes import router as intelligence_hub_router
from domains.intelligence_hub.routes.context_centric import router as context_centric_router
from domains.finance.routes.finance import router as finance_router
from domains.user_management.routes.user_management import router as user_management_router
from domains.system_monitoring.routes import router as system_monitoring_router

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
    logger.info("Starting News Intelligence System v5.0")

    # Initialize database connection pool early (persistent connection)
    try:
        from shared.database.connection import _init_pool, get_db_config, get_db_connection

        # get_db_config enforces NAS tunnel rules and logs host/port
        db_config = get_db_config()
        logger.info(
            "Database configuration resolved: %s:%s/%s",
            db_config["host"],
            db_config["port"],
            db_config["database"],
        )

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
            logger.error("   API will not be able to access database without DB_HOST/DB_PORT configuration")
    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
    
    # Initialize LLM service
    async def init_llm(app: FastAPI) -> None:
        try:
            llm_status = await llm_service.get_model_status()
            if llm_status["success"]:
                logger.info(
                    "✅ LLM Service initialized - Primary: %s, Secondary: %s",
                    llm_status.get("primary_model"),
                    llm_status.get("secondary_model"),
                )
            else:
                logger.warning("⚠️ LLM Service initialization failed: %s", llm_status.get("error"))

            app.state.llm_service = llm_service
        except Exception as exc:
            logger.error("❌ Failed to initialize LLM service: %s", exc)
            app.state.llm_service = None

    await init_llm(app)

    # Log finance embedding config (no heavy imports)
    try:
        from domains.finance.data.vector_store import get_embedding_collection_info
        model, coll = get_embedding_collection_info()
        logger.info(f"✅ Finance evidence: embedding={model}, collection={coll}")
    except Exception as e:
        logger.debug("Finance embedding config not logged: %s", e)

    # Initialize Finance Orchestrator
    try:
        from domains.finance.orchestrator import FinanceOrchestrator
        from domains.finance import data_sources
        from domains.finance.data import market_data_store, vector_store, evidence_ledger
        from domains.finance import embedding, stats
        from domains.finance import llm as finance_llm

        app.state.finance_orchestrator = FinanceOrchestrator(
            source_loader=data_sources,
            market_data_store=market_data_store,
            vector_store=vector_store,
            evidence_ledger=evidence_ledger,
            embedding_module=embedding,
            stats_module=stats,
            llm_wrapper=finance_llm,
            cpu_concurrency=4,
        )
        logger.info("✅ Finance Orchestrator initialized")
        if app.state.finance_orchestrator:
            app.state.finance_orchestrator.start_scheduler()
            app.state.finance_orchestrator.start_queue_worker()
            logger.info("✅ Finance scheduler and queue worker started")
    except Exception as e:
        logger.error("❌ Failed to initialize Finance Orchestrator: %s", e)
        app.state.finance_orchestrator = None

    # Orchestrator coordinator (collection + processing governor, importance, loop: assess/plan/execute/learn)
    try:
        from services.orchestrator_coordinator import OrchestratorCoordinator
        from collectors.rss_collector import collect_rss_feeds
        from shared.database.connection import get_db_connection as get_db
        coordinator = OrchestratorCoordinator(
            get_finance_orchestrator=lambda: getattr(app.state, "finance_orchestrator", None),
            get_automation=lambda: getattr(app.state, "automation", None),
            get_db_connection=get_db,
            collect_rss_feeds_fn=collect_rss_feeds,
        )
        app.state.orchestrator_coordinator = coordinator
        coordinator.start_loop()
        logger.info("✅ Orchestrator coordinator started (collection + processing governance)")
    except Exception as e:
        logger.error("❌ Failed to start Orchestrator coordinator: %s", e, exc_info=True)
        app.state.orchestrator_coordinator = None

    # Start automation manager in background thread
    try:
        from services.automation_manager import AutomationManager
        from services.ml_processing_service import MLProcessingService
        import threading

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

    # Health Monitor Orchestrator — polls health feeds and creates alerts on failure
    try:
        from services.health_monitor_orchestrator import get_health_monitor
        base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        health_monitor = get_health_monitor(base_url=base_url)
        health_monitor.start()
        app.state.health_monitor = health_monitor
        logger.info("✅ Health Monitor Orchestrator started — monitoring health feeds")
    except Exception as e:
        logger.error("❌ Failed to start Health Monitor Orchestrator: %s", e)
        app.state.health_monitor = None
    
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

    # Start Newsroom Orchestrator v6 (optional, feature-flagged)
    try:
        from orchestration.config import load_newsroom_config
        from orchestration.base import NewsroomOrchestrator
        from shared.database.connection import get_db_connection
        newsroom_config = load_newsroom_config()
        if newsroom_config.get("enabled"):
            newsroom_orchestrator = NewsroomOrchestrator(get_db_connection=get_db_connection, config=newsroom_config)
            from orchestration.handlers import register_default_handlers
            register_default_handlers(newsroom_orchestrator)
            def run_newsroom():
                newsroom_orchestrator.start()
            newsroom_thread = threading.Thread(target=run_newsroom, daemon=True, name="NewsroomOrchestrator")
            newsroom_thread.start()
            app.state.newsroom_orchestrator = newsroom_orchestrator
            app.state.newsroom_orchestrator_thread = newsroom_thread
            logger.info("✅ Newsroom Orchestrator v6 started")
        else:
            app.state.newsroom_orchestrator = None
            app.state.newsroom_orchestrator_thread = None
            logger.info("Newsroom Orchestrator disabled (enabled=false or NEWSROOM_ORCHESTRATOR_ENABLED not set)")
    except Exception as e:
        logger.error(f"❌ Failed to start Newsroom Orchestrator: {e}")
        app.state.newsroom_orchestrator = None
        app.state.newsroom_orchestrator_thread = None
    
    yield
    
    # Shutdown
    logger.info("Shutting down News Intelligence System v5.0")
    
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
    
    # Stop Health Monitor Orchestrator
    try:
        if hasattr(app.state, "health_monitor") and app.state.health_monitor:
            app.state.health_monitor.stop()
            logger.info("Health Monitor Orchestrator stopped")
    except Exception as e:
        logger.error("Error stopping Health Monitor Orchestrator: %s", e)

    # Stop Orchestrator coordinator
    try:
        if hasattr(app.state, "orchestrator_coordinator") and app.state.orchestrator_coordinator:
            app.state.orchestrator_coordinator.stop_loop()
            logger.info("Orchestrator coordinator stopped")
    except Exception as e:
        logger.error("Error stopping Orchestrator coordinator: %s", e)

    # Stop Finance Scheduler
    try:
        if hasattr(app.state, 'finance_orchestrator') and app.state.finance_orchestrator:
            app.state.finance_orchestrator.stop_scheduler()
            logger.info("Finance scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping Finance scheduler: {e}")
    
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

    # Stop Newsroom Orchestrator
    try:
        if hasattr(app.state, 'newsroom_orchestrator') and app.state.newsroom_orchestrator:
            app.state.newsroom_orchestrator.is_running = False
            if hasattr(app.state, 'newsroom_orchestrator_thread') and app.state.newsroom_orchestrator_thread:
                app.state.newsroom_orchestrator_thread.join(timeout=5)
                if app.state.newsroom_orchestrator_thread.is_alive():
                    logger.warning("Newsroom Orchestrator thread did not stop gracefully")
                else:
                    logger.info("Newsroom Orchestrator stopped")
    except Exception as e:
        logger.error(f"Error stopping Newsroom Orchestrator: {e}")

# Create FastAPI application
app = FastAPI(
    title="News Intelligence System v5.0",
    description="""
    ## News Intelligence System v5.0 - Domain-Driven AI Platform
    
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
    version="5.0.0",
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

# Add request tracking and standardized API logging
REQUEST_TIMEOUT_SECONDS = 30  # hard ceiling for any single request

@app.middleware("http")
async def request_tracker_middleware(request: Request, call_next):
    """Record API activity and enforce a per-request timeout to prevent runaway queries."""
    import uuid
    from shared.services.api_request_tracker import record_request
    from shared.logging.activity_logger import log_api_request

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    record_request()
    start = time.perf_counter()

    try:
        response = await asyncio.wait_for(
            call_next(request),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        duration_ms = (time.perf_counter() - start) * 1000
        path = request.url.path or "/"
        logger.warning("Request timed out after %.0fms: %s %s", duration_ms, request.method, path)
        response = JSONResponse(
            status_code=504,
            content={
                "success": False,
                "data": None,
                "message": f"Request timed out after {REQUEST_TIMEOUT_SECONDS}s",
                "timestamp": datetime.now().isoformat(),
            },
        )

    duration_ms = (time.perf_counter() - start) * 1000
    status_code = response.status_code if hasattr(response, "status_code") else 200
    path = request.url.path or "/"
    if request.query_params:
        path = f"{path}?{request.query_params}"
    if not (path.rstrip("/").endswith("/health") or "/health" in path.split("?")[0]):
        log_api_request(
            method=request.method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
            request_id=request_id,
        )
    response.headers["X-Request-ID"] = request_id
    return response

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
# Context-centric (tracked_events, report, entity_profiles, etc.) at /api/... so frontend always finds report endpoint
app.include_router(context_centric_router)
app.include_router(finance_router)
app.include_router(user_management_router)
app.include_router(system_monitoring_router)
# app.include_router(pipeline_monitoring_router)

# Include v3.0 compatibility layer
app.include_router(compatibility_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System v5.0",
            "version": "5.0.0",
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
        "message": "News Intelligence System v5.0 is running",
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
