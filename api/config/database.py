#!/usr/bin/env python3
"""
Database compatibility shim - re-exports from shared.database.connection.
All DB access uses the single pooled connection in shared.
"""

from shared.database.connection import (
    get_db_connection,
    get_db_connection_context,
    get_db_config,
    get_db_connect_kwargs,
    get_db,
    get_db_session,
    get_db_cursor,
    test_database_connection,
    check_database_health,
    get_database_url,
    get_database_config,
)

__all__ = [
    "get_db_connection",
    "get_db_connection_context",
    "get_db_config",
    "get_db_connect_kwargs",
    "get_db",
    "get_db_session",
    "get_db_cursor",
    "test_database_connection",
    "check_database_health",
    "get_database_url",
    "get_database_config",
]
