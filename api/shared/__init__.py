"""Shared package — public facade for api.domains.* and services.*.

Every shared module that other parts of the application depend on should be
re-exported here so callers can import from ``shared`` (flat, no deep nesting).

Usage:

    api.shared.database import insert_or_upsert, get_db_connection  # database utilities
    api.shared.domain_registry import DOMAIN_PATH_PATTERN              # domain constants
    api.shared.pipeline_state_constants import ARTICLE_PENDING        # pipeline states
    from shared import ROUTERS                                          # all domain routers

"""

# ── Database layer ───────────────────────────────────────────────────────────
# All connection management, health checks, accessors, and upsert helpers.

from .database.connection import (
    get_db_connection,
    get_db_connection_context,
    get_health_db_connection,
    get_health_db_connection_context,
    get_ui_db_connection,
    get_ui_db_connection_context,
    get_db_cursor,
    get_ephemeral_db_connection,
    ephemeral_db_connection_context,
    get_db,
    get_db_session,
    get_database_url,
    get_db_pool_snapshot,
    automation_db_pool_should_defer_phase,
    close_pool,
)

from .database.db_availability import (
    is_database_ready,
    is_automation_db_ready,
    is_database_available,
    wait_for_database_availability,
    get_database_status,
)

from .database.health_check import (
    check_system_health,
    check_automation_phase_health,
    is_database_healthy,
    wait_for_database_ready,
)

from .database.storyline_merger import StorylineMerger

from .database.accessors import (
    db_execute,
    db_fetch_one,
    db_fetch_many,
    db_execute_many,
    db_heartbeat,
)

from .database.upsert import (
    insert_or_upsert,
    insert_or_ignore,
    insert_many,
)

# ── Domain constants & registry ─────────────────────────────────────────────

from .domain_registry import DOMAIN_PATH_PATTERN, ACTIVE_DOMAIN_KEYS_SET
VALID_DOMAIN_KEYS = ACTIVE_DOMAIN_KEYS_SET  # alias for backward compatibility
from .domain_registry import domain_key_to_schema, is_valid_domain_key
from .constants import (
    DEFAULT_CACHE_TTL_SECONDS,
    CACHE_TTL_30MIN,
    CACHE_TTL_24H,
)

# ── Pipeline state constants ────────────────────────────────────────────────

from .pipeline_state_constants import (
    ARTICLE_PENDING,
    ARTICLE_ENRICHED,
    ARTICLE_FAILED,
    ARTICLE_INACCESSIBLE,
    ARTICLE_CONTENT_SHORT,
    ARTICLE_TERMINAL_STATES,
    ARTICLE_NON_TERMINAL_STATES,
    QUEUE_PENDING,
    QUEUE_PROCESSING,
    QUEUE_COMPLETED,
    QUEUE_FAILED,
    QUEUE_TERMINAL_STATES,
    ML_PENDING,
    ML_RUNNING,
    ML_COMPLETED,
    ML_FAILED,
    PIPELINE_PHASES,
    PHASE_GROUP,
)

# ── Key domain routers (mount these on your FastAPI app) ─────────────────────

# from ..domains.storyline_management.routes import router as storyline_router
# from ..domains.content_analysis.routes import router as content_analysis_router
# from ..domains.finance.routes import router as finance_router
# from ..domains.intelligence_hub.routes import router as intelligence_hub_router
# from ..domains.news_aggregation.routes import router as news_aggregation_router
# from ..domains.politics.routes import router as politics_router
# from ..domains.public_auth.routes import router as public_auth_router
# from ..domains.reader.routes import router as reader_router
# from ..domains.search.routes import router as search_router
# from ..domains.system_monitoring.routes import router as system_monitoring_router
# from ..domains.user_management.routes import router as user_management_router

# Convenience tuple for mounting all routers in order
ROUTERS = ()
#     public_auth_router,
#     finance_router,
#     news_aggregation_router,
#     storyline_router,
#     content_analysis_router,
#     politics_router,
#     intelligence_hub_router,
#     reader_router,
#     search_router,
#     system_monitoring_router,
#     user_management_router,
# )

__all__ = [  # PATCHED: skip for diagnostics
    # Database
    "get_db_connection",
    "get_db_connection_context",
    "get_health_db_connection",
    "get_health_db_connection_context",
    "get_ui_db_connection",
    "get_ui_db_connection_context",
    "get_db_cursor",
    "get_ephemeral_db_connection",
    "ephemeral_db_connection_context",
    "get_db",
    "get_db_session",
    "get_database_url",
    "get_db_pool_snapshot",
    "automation_db_pool_should_defer_phase",
    "close_pool",
    "is_database_ready",
    "is_automation_db_ready",
    "is_database_available",
    "wait_for_database_availability",
    "get_database_status",
    "check_system_health",
    "check_automation_phase_health",
    "is_database_healthy",
    "wait_for_database_ready",
    "StorylineMerger",
    "db_execute",
    "db_fetch_one",
    "db_fetch_many",
    "db_execute_many",
    "db_heartbeat",
    "insert_or_upsert",
    "insert_or_ignore",
    "insert_many",
    # Domain constants & registry
    "DOMAIN_PATH_PATTERN",
    "VALID_DOMAIN_KEYS",
    "domain_key_to_schema",
    "is_valid_domain_key",
    "DEFAULT_CACHE_TTL_SECONDS",
    "CACHE_TTL_30MIN",
    "CACHE_TTL_24H",
    # Pipeline state constants
    "ARTICLE_PENDING",
    "ARTICLE_ENRICHED",
    "ARTICLE_FAILED",
    "ARTICLE_INACCESSIBLE",
    "ARTICLE_CONTENT_SHORT",
    "ARTICLE_TERMINAL_STATES",
    "ARTICLE_NON_TERMINAL_STATES",
    "QUEUE_PENDING",
    "QUEUE_PROCESSING",
    "QUEUE_COMPLETED",
    "QUEUE_FAILED",
    "QUEUE_TERMINAL_STATES",
    "ML_PENDING",
    "ML_RUNNING",
    "ML_COMPLETED",
    "ML_FAILED",
    "PIPELINE_PHASES",
    "PHASE_GROUP",
    # Domain routers
    "storyline_router",
    "content_analysis_router",
    "finance_router",
    "intelligence_hub_router",
    "news_aggregation_router",
    "politics_router",
    "public_auth_router",
    "reader_router",
    "search_router",
    "system_monitoring_router",
    "user_management_router",
    "ROUTERS",
]
# Shared services and utilities
