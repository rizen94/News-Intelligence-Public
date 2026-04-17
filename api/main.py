"""
News Intelligence — FastAPI application entry (domain-driven).

What this file does:
  - Loads project-root ``.env`` early so DB and API keys match ops scripts.
  - Builds the FastAPI app: ``lifespan`` starts DB pool checks and background
    automation; middleware order is CORS → TrustedHost → optional SecurityMiddleware
    (see ``config.settings`` ``news_intel_*`` helpers for production tightening).
  - Mounts domain routers (news_aggregation, content_analysis, storyline_management,
    intelligence_hub + context_centric, finance, user_management, system_monitoring).

Where to read next:
  - DB access: ``shared.database.connection`` (single source of truth; never ad-hoc psycopg2).
  - Background work: ``services.automation_manager`` (v8 collection_cycle + scheduled phases).
  - Reviewer docs: repo ``docs/CODEBASE_MAP.md``, ``docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md``.

LLM routing uses Ollama (see ``config.settings`` and ``shared.services.ollama_model_caller``).
"""

# Dump all thread tracebacks on SIGUSR1 for debugging hung processes
import faulthandler
import signal as _signal

faulthandler.enable()
try:
    faulthandler.register(_signal.SIGUSR1)
except (AttributeError, OSError):
    pass

# Reduce GIL switch interval so the main uvicorn thread gets more frequent
# time slices among the many background worker threads
import sys

sys.setswitchinterval(0.001)  # 1ms (default 5ms)

# Load .env before any config — override=False so shell/env take precedence
# API often runs with CWD=api/, so load project-root .env (NEWS_API_KEY, FRED_API_KEY, etc.)
import os

from dotenv import load_dotenv

load_dotenv(override=False)
_env_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
if os.path.isfile(_env_root):
    load_dotenv(_env_root, override=False)
import asyncio
import logging
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), "modules"))
sys.path.append(os.path.join(os.path.dirname(__file__), "shared"))
sys.path.append(os.path.join(os.path.dirname(__file__), "domains"))

# Configure logging from centralized config (uses settings.LOG_LEVEL, LOG_DIR)
try:
    from config.logging_config import setup_logging

    setup_logging()
    logger = logging.getLogger(__name__)
except Exception as e:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger(__name__)
    logger.warning("Centralized logging unavailable, using basicConfig: %s", e)

# Import pipeline monitoring
# from routes.pipeline_monitoring import router as pipeline_monitoring_router
from config.settings import (
    MODELS,
    news_intel_api_docs_enabled,
    news_intel_cors_allow_origins,
    news_intel_expose_error_detail_to_client,
    news_intel_is_production,
    news_intel_rate_limit_per_minute,
    news_intel_security_middleware_enabled,
    news_intel_trusted_hosts,
)
from domains.content_analysis.routes import router as content_analysis_router
from domains.finance.routes.finance import router as finance_router
from domains.intelligence_hub.routes import router as intelligence_hub_router
from domains.intelligence_hub.routes.context_centric import router as context_centric_router

# Import domain routers (consolidated — one per domain)
from domains.news_aggregation.routes import router as news_aggregation_router
from domains.politics.routes import router as politics_router
from domains.storyline_management.routes import router as storyline_management_router
from domains.system_monitoring.routes import router as system_monitoring_router
from domains.user_management.routes.user_management import router as user_management_router

# Import shared services
from shared.services.llm_service import llm_service

# Import database configuration


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting News Intelligence System v5.0")
    if news_intel_is_production():
        logger.info(
            "NEWS_INTEL_ENV=production — see docs/SECURITY_OPERATIONS.md for CORS, hosts, and OpenAPI"
        )
        try:
            from shared.middleware import demo_readonly as _demo_ro

            if _demo_ro.news_intel_demo_readonly_enabled():
                logger.info(
                    "NEWS_INTEL_DEMO_READ_ONLY — demo hosts=%s read_only_all=%s",
                    _demo_ro.news_intel_demo_hosts_list(),
                    _demo_ro.news_intel_demo_readonly_all_hosts(),
                )
        except Exception as e:
            logger.debug("demo readonly env log skipped: %s", e)
        if not news_intel_cors_allow_origins():
            logger.warning(
                "NEWS_INTEL_CORS_ORIGINS is empty: browsers on another origin cannot call the API with CORS. "
                "Set comma-separated origins (e.g. https://app.example.com) if you expose the UI separately."
            )

    # Initialize database connection pool early (persistent connection)
    try:
        from shared.database.connection import _init_pool, get_db_config, get_db_connection

        # get_db_config enforces NAS tunnel rules and logs host/port
        db_config = get_db_config()
        if not (db_config.get("password") or "").strip():
            logger.error(
                "DB_PASSWORD is not set. Set it in project-root .env (e.g. DB_PASSWORD=your_password) "
                "and start the API with that env (e.g. ./start_system.sh). Exiting to avoid 503s on all DB routes."
            )
            sys.exit(1)
        logger.info(
            "Database configuration resolved: %s:%s/%s",
            db_config["host"],
            db_config["port"],
            db_config["database"],
        )

        try:
            _init_pool()
            logger.info("✅ Database connection pool initialized (persistent connections)")
            conn = get_db_connection()
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
            conn.close()
            logger.info("✅ Database connection test successful")
            try:
                from shared.domain_registry import pipeline_url_schema_pairs, url_schema_pairs

                _all = url_schema_pairs()
                _pipe = pipeline_url_schema_pairs()
                if len(_all) > 0 and len(_pipe) == 0:
                    logger.error(
                        "Pipeline config: zero domains in pipeline_url_schema_pairs() but registry has silos — "
                        "check PIPELINE_INCLUDE_DOMAIN_KEYS / PIPELINE_EXCLUDE_DOMAIN_KEYS (automation would idle)."
                    )
                else:
                    logger.info(
                        "Pipeline domains (processing/backlog): %s",
                        [p[0] for p in _pipe],
                    )
            except Exception as _pe:
                logger.debug("Pipeline domain startup log skipped: %s", _pe)
        except ConnectionError as e:
            logger.error("❌ Database connection failed: %s", e)
            logger.error(
                "   Set DB_PASSWORD in project-root .env and restart (e.g. ./start_system.sh). "
                "API will return 503 for DB-dependent routes until then."
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connection pool: {e}")
            logger.error(
                "   Set DB_PASSWORD in project-root .env and restart (e.g. ./start_system.sh). "
                "API will return 503 for DB-dependent routes until then."
            )
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

    # Initialize Finance Orchestrator (runs in its own background thread to avoid
    # blocking the main uvicorn event loop with sync DB/state operations)
    try:
        from domains.finance import data_sources, embedding, stats
        from domains.finance import llm as finance_llm
        from domains.finance.data import evidence_ledger, market_data_store, vector_store
        from domains.finance.orchestrator import FinanceOrchestrator

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

            def _run_finance_background():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                fo = app.state.finance_orchestrator
                fo._schedule_task = None
                fo._queue_task = None

                async def _start():
                    fo._schedule_stop.clear()
                    fo._schedule_task = asyncio.create_task(fo._schedule_loop())
                    fo._queue_stop.clear()
                    fo._queue_task = asyncio.create_task(fo._queue_loop())
                    while True:
                        await asyncio.sleep(60)

                loop.run_until_complete(_start())

            finance_bg_thread = threading.Thread(
                target=_run_finance_background, daemon=True, name="FinanceScheduler"
            )
            finance_bg_thread.start()
            app.state.finance_bg_thread = finance_bg_thread
            logger.info("✅ Finance scheduler and queue worker started (background thread)")
    except Exception as e:
        logger.error("❌ Failed to initialize Finance Orchestrator: %s", e)
        app.state.finance_orchestrator = None

    # Orchestrator coordinator (collection + processing governor, importance, loop: assess/plan/execute/learn)
    # Runs in its own background thread to avoid blocking the main uvicorn event loop
    try:
        from collectors.rss_collector import collect_rss_feeds
        from services.orchestrator_coordinator import OrchestratorCoordinator
        from shared.database.connection import get_db_connection as get_db

        coordinator = OrchestratorCoordinator(
            get_finance_orchestrator=lambda: getattr(app.state, "finance_orchestrator", None),
            get_automation=lambda: getattr(app.state, "automation", None),
            get_db_connection=get_db,
            collect_rss_feeds_fn=collect_rss_feeds,
        )
        app.state.orchestrator_coordinator = coordinator

        def _run_coordinator_background():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            coordinator._task = None

            async def _start():
                coordinator._stop.clear()
                coordinator._task = asyncio.create_task(coordinator._run_loop())
                while True:
                    await asyncio.sleep(60)

            loop.run_until_complete(_start())

        coord_thread = threading.Thread(
            target=_run_coordinator_background, daemon=True, name="OrchestratorCoord"
        )
        coord_thread.start()
        app.state.coordinator_thread = coord_thread
        logger.info("✅ Orchestrator coordinator started (background thread)")
    except Exception as e:
        logger.error("❌ Failed to start Orchestrator coordinator: %s", e, exc_info=True)
        app.state.orchestrator_coordinator = None

    # Start automation manager in background thread
    try:
        from services.automation_manager import AutomationManager
        from services.ml_processing_service import MLProcessingService

        automation = AutomationManager(db_config)

        # Start automation in background thread with limited default executor
        def start_automation():
            import asyncio
            from concurrent.futures import ThreadPoolExecutor

            loop = asyncio.new_event_loop()
            loop.set_default_executor(ThreadPoolExecutor(max_workers=2))
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(automation.start())
            except Exception as exc:
                logger.error(
                    "Automation manager background thread exited: %s",
                    exc,
                    exc_info=True,
                )

        automation_thread = threading.Thread(target=start_automation, daemon=True)
        automation_thread.start()

        logger.info("Automation manager started in background thread")

        # Store automation manager for shutdown
        app.state.automation = automation
        app.state.automation_thread = automation_thread
        # Single process-wide reference so get_automation_manager() returns the *running* instance
        # (not a lazy second AutomationManager that never started — breaks Monitor activity merge).
        import services.automation_manager as _automation_module

        _automation_module.automation_manager = automation
        # Idle-time research topic refinement: automation can submit low-priority analysis tasks
        automation.set_finance_orchestrator_getter(
            lambda: getattr(app.state, "finance_orchestrator", None)
        )

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
            from domains.content_analysis.services.topic_extraction_queue_worker import (
                TopicExtractionQueueWorker,
            )
            from shared.database.connection import get_db_connection

            def start_queue_workers_background():
                """Start queue workers in background thread"""
                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def start_workers():
                    """Start queue workers for all active domains"""
                    from shared.domain_registry import pipeline_url_schema_pairs

                    workers = []
                    for _domain_key, schema in pipeline_url_schema_pairs():
                        try:
                            worker = TopicExtractionQueueWorker(get_db_connection, schema=schema)
                            workers.append(worker)
                            # Start worker in background task
                            asyncio.create_task(worker.start())
                            logger.info(f"✅ Started topic extraction queue worker for {_domain_key} ({schema})")
                        except Exception as e:
                            logger.error(f"❌ Failed to start queue worker for {_domain_key}: {e}")

                    # Keep workers running
                    while True:
                        await asyncio.sleep(60)  # Check every minute

                loop.run_until_complete(start_workers())

            # Start queue workers in background thread
            queue_worker_thread = threading.Thread(
                target=start_queue_workers_background, daemon=True
            )
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
        import services.automation_manager as _automation_module

        _automation_module.automation_manager = None

    # Start Route Supervisor
    try:
        from shared.services.route_supervisor import get_route_supervisor

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
    # Runs in its own thread to keep sync DB writes off the main event loop
    try:
        from services.health_monitor_orchestrator import get_health_monitor

        base_url = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
        health_monitor = get_health_monitor(base_url=base_url)

        def _run_health_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            health_monitor._stop = asyncio.Event()
            health_monitor._task = None

            async def _start():
                health_monitor._stop.clear()
                health_monitor._task = asyncio.create_task(health_monitor._loop())
                while True:
                    await asyncio.sleep(60)

            loop.run_until_complete(_start())

        health_thread = threading.Thread(
            target=_run_health_monitor, daemon=True, name="HealthMonitor"
        )
        health_thread.start()
        app.state.health_monitor = health_monitor
        app.state.health_monitor_thread = health_thread
        logger.info("✅ Health Monitor Orchestrator started (background thread)")
    except Exception as e:
        logger.error("❌ Failed to start Health Monitor Orchestrator: %s", e)
        app.state.health_monitor = None

    # Start unified Consolidation Scheduler (storylines, entities, investigations, events)
    try:
        from services.consolidation_scheduler import (
            CONSOLIDATION_INTERVAL_SECONDS,
            CONSOLIDATION_STARTUP_DELAY_SECONDS,
            CONSOLIDATION_TYPES,
            get_next_step_name,
            run_consolidation_step,
        )

        consolidation_stop_event = threading.Event()
        consolidation_run_count = [0]  # mutable so thread can increment

        def run_consolidation_loop():
            """Run one consolidation type per interval; stagger so each runs ~2x per day."""
            if CONSOLIDATION_STARTUP_DELAY_SECONDS > 0:
                consolidation_stop_event.wait(CONSOLIDATION_STARTUP_DELAY_SECONDS)
            while not consolidation_stop_event.is_set():
                step_name = get_next_step_name(consolidation_run_count[0])
                try:
                    logger.info("🔄 Running scheduled consolidation: %s", step_name)
                    result = run_consolidation_step(step_name)
                    if result.get("success"):
                        logger.info(
                            "✅ Consolidation %s complete: %s", step_name, result.get("message", "")
                        )
                    else:
                        logger.warning(
                            "⚠️ Consolidation %s finished with issues: %s",
                            step_name,
                            result.get("message", ""),
                        )
                except Exception as e:
                    logger.error("❌ Consolidation %s error: %s", step_name, e)
                consolidation_run_count[0] += 1
                consolidation_stop_event.wait(CONSOLIDATION_INTERVAL_SECONDS)

        consolidation_thread = threading.Thread(
            target=run_consolidation_loop,
            daemon=True,
            name="ConsolidationScheduler",
        )
        consolidation_thread.start()
        logger.info(
            "✅ Consolidation Scheduler started — rotation %s every %s s",
            CONSOLIDATION_TYPES,
            CONSOLIDATION_INTERVAL_SECONDS,
        )
        app.state.consolidation_thread = consolidation_thread
        app.state.consolidation_stop_event = consolidation_stop_event
    except Exception as e:
        logger.error("❌ Failed to start Consolidation Scheduler: %s", e)
        app.state.consolidation_thread = None
        app.state.consolidation_stop_event = None

    # Start Newsroom Orchestrator v6 (optional, feature-flagged)
    try:
        from orchestration.base import NewsroomOrchestrator
        from orchestration.config import load_newsroom_config
        from shared.database.connection import get_db_connection

        newsroom_config = load_newsroom_config()
        if newsroom_config.get("enabled"):
            newsroom_orchestrator = NewsroomOrchestrator(
                get_db_connection=get_db_connection, config=newsroom_config
            )
            from orchestration.handlers import register_default_handlers

            register_default_handlers(newsroom_orchestrator)

            def run_newsroom():
                newsroom_orchestrator.start()

            newsroom_thread = threading.Thread(
                target=run_newsroom, daemon=True, name="NewsroomOrchestrator"
            )
            newsroom_thread.start()
            app.state.newsroom_orchestrator = newsroom_orchestrator
            app.state.newsroom_orchestrator_thread = newsroom_thread
            logger.info("✅ Newsroom Orchestrator v6 started")
        else:
            app.state.newsroom_orchestrator = None
            app.state.newsroom_orchestrator_thread = None
            logger.info(
                "Newsroom Orchestrator disabled (enabled=false or NEWSROOM_ORCHESTRATOR_ENABLED not set)"
            )
    except Exception as e:
        logger.error(f"❌ Failed to start Newsroom Orchestrator: {e}")
        app.state.newsroom_orchestrator = None
        app.state.newsroom_orchestrator_thread = None

    yield

    # Shutdown
    logger.info("Shutting down News Intelligence System v5.0")

    # Close LLM service
    try:
        if hasattr(app.state, "llm_service") and app.state.llm_service:
            await app.state.llm_service.close()
            logger.info("LLM service closed")
    except Exception as e:
        logger.error(f"Error closing LLM service: {e}")

    # Stop automation manager
    try:
        if hasattr(app.state, "automation") and app.state.automation:
            # v8: Persist pending collection queue before stop
            try:
                app.state.automation.persist_pending_collection_queue()
            except Exception as e:
                logger.debug("Persist pending collection queue on shutdown: %s", e)
            # Signal automation to stop
            app.state.automation.is_running = False
            logger.info("Automation manager stop signal sent")

            # Wait for automation thread to finish (with timeout)
            if hasattr(app.state, "automation_thread") and app.state.automation_thread:
                app.state.automation_thread.join(timeout=5)
                if app.state.automation_thread.is_alive():
                    logger.warning("Automation thread did not stop gracefully")
                else:
                    logger.info("Automation manager stopped")
            import services.automation_manager as _automation_module

            _automation_module.automation_manager = None
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
        if hasattr(app.state, "finance_orchestrator") and app.state.finance_orchestrator:
            app.state.finance_orchestrator.stop_scheduler()
            logger.info("Finance scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping Finance scheduler: {e}")

    # Stop Route Supervisor
    try:
        if hasattr(app.state, "route_supervisor") and app.state.route_supervisor:
            app.state.route_supervisor.stop_monitoring()
            logger.info("Route Supervisor stopped")
    except Exception as e:
        logger.error(f"Error stopping Route Supervisor: {e}")

    # Stop Consolidation Scheduler
    try:
        if hasattr(app.state, "consolidation_stop_event") and app.state.consolidation_stop_event:
            app.state.consolidation_stop_event.set()
            if hasattr(app.state, "consolidation_thread") and app.state.consolidation_thread:
                app.state.consolidation_thread.join(timeout=5)
            logger.info("Consolidation Scheduler stopped")
    except Exception as e:
        logger.error(f"Error stopping Consolidation Service: {e}")

    # Stop Newsroom Orchestrator
    try:
        if hasattr(app.state, "newsroom_orchestrator") and app.state.newsroom_orchestrator:
            app.state.newsroom_orchestrator.is_running = False
            if (
                hasattr(app.state, "newsroom_orchestrator_thread")
                and app.state.newsroom_orchestrator_thread
            ):
                app.state.newsroom_orchestrator_thread.join(timeout=5)
                if app.state.newsroom_orchestrator_thread.is_alive():
                    logger.warning("Newsroom Orchestrator thread did not stop gracefully")
                else:
                    logger.info("Newsroom Orchestrator stopped")
    except Exception as e:
        logger.error(f"Error stopping Newsroom Orchestrator: {e}")

    # Close DB pools last (releases server-side sessions for this process)
    try:
        from shared.database.connection import close_pool

        close_pool()
        logger.info("Database connection pools closed")
    except Exception as e:
        logger.error("Error closing database pools: %s", e)


# OpenAPI / docs — disabled in production unless NEWS_INTEL_ENABLE_API_DOCS=true
_api_docs_on = news_intel_api_docs_enabled()
_docs_url = "/docs" if _api_docs_on else None
_redoc_url = "/redoc" if _api_docs_on else None
_openapi_url = "/openapi.json" if _api_docs_on else None
_cors_origins = news_intel_cors_allow_origins()
_cors_credentials = "*" not in _cors_origins

# Create FastAPI application
app = FastAPI(
    title="News Intelligence System v5.0",
    description="""
    ## News Intelligence System v5.0 - Domain-Driven AI Platform

    A comprehensive news aggregation and analysis platform featuring:

    * **Domain-Driven Architecture** - Organized into 6 business domains
    * **AI-Powered Analysis** - Using configurable Ollama models (primary + secondary slot; see `config.settings.MODELS`)
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
    - **Secondary Model**: default Mistral-Nemo 12B in the secondary slot (throughput / batch; override via env)
    - **Resource Usage**: 9.3GB total storage (vs 109GB+ with previous models)

    ### Authentication
    No per-user JWT on routes by default — use network isolation or a reverse proxy for access control.

    ### Rate limiting and hardening
    Set `NEWS_INTEL_ENV=production` for stricter CORS, Host header checks, disabled OpenAPI by default,
    generic 500 responses, and in-app rate limiting (see `docs/SECURITY_OPERATIONS.md`).
    """,
    version="5.0.0",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
    openapi_tags=[
        {
            "name": "News Aggregation",
            "description": "RSS feed processing, article ingestion, and content quality assessment",
        },
        {
            "name": "Content Analysis",
            "description": "Sentiment analysis, entity extraction, summarization, and bias detection",
        },
        {
            "name": "Storyline Management",
            "description": "Storyline creation, timeline generation, and RAG-enhanced analysis",
        },
        {
            "name": "Intelligence Hub",
            "description": "Predictive analytics, trend analysis, and strategic insights",
        },
        {
            "name": "User Management",
            "description": "User profiles, preferences, and personalized experiences",
        },
        {
            "name": "System Monitoring",
            "description": "Health checks, performance monitoring, and alerting",
        },
    ],
    contact={
        "name": "News Intelligence System",
        "url": "https://github.com/news-intelligence",
        "email": "support@news-intelligence.com",
    },
    license_info={"name": "MIT License", "url": "https://opensource.org/licenses/MIT"},
)

# Add request tracking and standardized API logging
REQUEST_TIMEOUT_SECONDS = 30  # hard ceiling for any single request


@app.middleware("http")
async def request_tracker_middleware(request: Request, call_next):
    """Record API activity and enforce a per-request timeout to prevent runaway queries."""
    import uuid

    from shared.logging.activity_logger import log_api_request
    from shared.services.api_request_tracker import record_request

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    record_request(path=request.url.path or "")
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


# Add middleware (last added = outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=news_intel_trusted_hosts(),
)

if news_intel_security_middleware_enabled():
    from middleware.security import SecurityMiddleware

    app.add_middleware(
        SecurityMiddleware,
        rate_limit_per_minute=news_intel_rate_limit_per_minute(),
    )

# Public demo read-only (outermost): block mutations when Host matches NEWS_INTEL_DEMO_HOSTS
from shared.middleware.demo_readonly import DemoReadOnlyMiddleware  # noqa: E402

app.add_middleware(DemoReadOnlyMiddleware)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for comprehensive error handling"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    expose = news_intel_expose_error_detail_to_client()
    err_text = str(exc) if expose else "Internal server error"
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "message": "Internal server error",
            "error": err_text,
            "error_type": exc.__class__.__name__ if expose else "InternalServerError",
            "recoverable": False,
            "timestamp": datetime.now().isoformat(),
        },
    )


# Include domain routers
app.include_router(news_aggregation_router)
app.include_router(politics_router)
app.include_router(content_analysis_router)
app.include_router(storyline_management_router)
app.include_router(intelligence_hub_router)
# Context-centric (tracked_events, report, entity_profiles, etc.) at /api/... so frontend always finds report endpoint
app.include_router(context_centric_router)
app.include_router(finance_router)
app.include_router(user_management_router)
app.include_router(system_monitoring_router)
# app.include_router(pipeline_monitoring_router)

@app.get("/api/public/demo_config")
async def public_demo_config(request: Request):
    """Expose whether this request's Host is in read-only demo mode (for SPA UX)."""
    from shared.middleware.demo_readonly import should_apply_demo_readonly

    readonly = should_apply_demo_readonly(request)
    return {
        "success": True,
        "data": {
            "readonly": readonly,
            "hint": "When true, mutating API methods are disabled for this host (see docs/PUBLIC_DEPLOYMENT.md).",
        },
        "message": "ok",
        "timestamp": datetime.now().isoformat(),
    }


# Root endpoint
@app.get("/")
async def root():
    return {
        "success": True,
        "data": {
            "name": "News Intelligence System v5.0",
            "version": "5.0.0",
            "architecture": "Domain-Driven Design",
            "ai_models": {"primary": MODELS["primary"], "secondary": MODELS["secondary"]},
            "domains": [
                "news_aggregation",
                "content_analysis",
                "storyline_management",
                "intelligence_hub",
                "user_management",
                "system_monitoring",
            ],
            "docs": "/docs",
            "redoc": "/redoc",
        },
        "message": "News Intelligence System v5.0 is running",
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
