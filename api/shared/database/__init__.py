"""
Database utilities for the News Intelligence system.

This package provides database connection management and utilities
for the News Intelligence application.
"""

# Import all necessary database utilities
from .connection import (
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
    check_database_health,
    probe_database_server_reachable,
    test_database_connection,
    get_database_config,
    get_db_config,
    get_db_connect_kwargs,
    _init_pool,
)

from .db_availability import (
    is_database_ready,
    is_automation_db_ready,
    is_database_available,
    wait_for_database_availability,
    get_database_status,
)

from .health_check import (
    check_system_health,
    check_automation_phase_health,
    is_database_healthy,
    wait_for_database_ready,
)

from .storyline_merger import StorylineMerger

# Import high-level accessors so services can use the facade instead of connection internals.
from .accessors import (
    db_execute,
    db_fetch_one,
    db_fetch_many,
    db_execute_many,
    db_heartbeat,
)

# ── Upsert helpers (replaces raw f-string INSERT patterns) ────────────
from .upsert import (
    insert_or_upsert,
    insert_or_ignore,
    insert_many,
)

# Package version
__version__ = "1.0.0"

# Package metadata
__all__ = [
    # Connection utilities
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
    "check_database_health",
    "probe_database_server_reachable",
    "test_database_connection",
    "get_database_config",
    "get_db_config",
    "get_db_connect_kwargs",
    
    # Availability utilities
    "is_database_ready",
    "is_automation_db_ready",
    "is_database_available",
    "wait_for_database_availability",
    "get_database_status",
    
    # Health check utilities
    "check_system_health",
    "check_automation_phase_health",
    "is_database_healthy",
    "wait_for_database_ready",
    
    # Storyline merger
    "StorylineMerger",

    # High-level accessors (prefer these over connection internals)
    "db_execute",
    "db_fetch_one",
    "db_fetch_many",
    "db_execute_many",
    "db_heartbeat",

    # Upsert helpers (replaces raw f-string INSERT patterns)
    "insert_or_upsert",
    "insert_or_ignore",
    "insert_many",
]