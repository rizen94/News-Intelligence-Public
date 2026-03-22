"""
Domain-Aware Service Base Class

Provides domain context and schema management for all domain-aware services.
All services that work with domain-specific data should inherit from this class.
"""

import logging
import re
from typing import Any

from psycopg2.extras import RealDictCursor
from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)


class DomainAwareService:
    """
    Base class for all domain-aware services.
    Provides domain context and schema management.
    """

    def __init__(self, domain: str):
        """
        Initialize service with domain context.

        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')

        Raises:
            ValueError: If domain is invalid or not active
        """
        self.domain = domain
        self.schema = self._normalize_schema_name(domain)
        self._validate_domain()

    def _normalize_schema_name(self, domain: str) -> str:
        """
        Convert domain key to schema name.

        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')

        Returns:
            Schema name (e.g., 'politics', 'finance', 'science_tech')
        """
        return domain.replace("-", "_")

    def _validate_domain(self):
        """
        Validate that domain exists and is active.

        Raises:
            ValueError: If domain is invalid or not active
        """
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, schema_name, is_active
                    FROM domains
                    WHERE domain_key = %s
                """,
                    (self.domain,),
                )
                result = cur.fetchone()

                if not result:
                    raise ValueError(f"Domain '{self.domain}' not found in domains table")

                if not result[2]:  # is_active
                    raise ValueError(f"Domain '{self.domain}' is not active")

                self.domain_id = result[0]
                self.schema = result[1]  # Use schema from database
                logger.info(
                    f"Domain validated: {self.domain} -> {self.schema} (ID: {self.domain_id})"
                )
        finally:
            conn.close()

    def get_db_connection(self):
        """
        Get database connection with domain schema context.
        Sets search_path to domain schema + public.

        Returns:
            psycopg2 connection with schema context
        """
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Set search path to domain schema first, then public
            cur.execute(f"SET search_path TO {self.schema}, public")
        return conn

    def execute_in_domain_schema(self, query: str, params: tuple = None):
        """
        Execute query in domain schema context.
        Automatically prefixes table names with schema if needed.

        Args:
            query: SQL query string
            params: Query parameters tuple

        Returns:
            Query results
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Replace table references with schema-qualified names
                qualified_query = self._qualify_table_names(query)
                cur.execute(qualified_query, params)
                return cur.fetchall()
        finally:
            conn.close()

    def _qualify_table_names(self, query: str) -> str:
        """
        Qualify table names with schema.
        This is a simplified version - may need more sophisticated parsing.

        Args:
            query: SQL query string

        Returns:
            Query with schema-qualified table names
        """
        # List of tables that should be schema-qualified
        domain_tables = [
            "articles",
            "topics",
            "storylines",
            "rss_feeds",
            "article_topic_assignments",
            "storyline_articles",
            "topic_clusters",
            "topic_cluster_memberships",
            "topic_learning_history",
        ]

        qualified_query = query
        for table in domain_tables:
            # Replace unqualified table references (but not schema-qualified ones)
            # Pattern: word boundary, table name, word boundary (not preceded by schema)
            pattern = f"(?<!{self.schema}\\.)\\b{table}\\b"
            replacement = f"{self.schema}.{table}"
            qualified_query = re.sub(pattern, replacement, qualified_query)

        return qualified_query

    def get_domain_info(self) -> dict[str, Any]:
        """
        Get information about the current domain.

        Returns:
            Dictionary with domain information
        """
        return {"domain_key": self.domain, "schema_name": self.schema, "domain_id": self.domain_id}


def validate_domain(domain: str) -> bool:
    """
    Validate that a domain exists and is active.

    Args:
        domain: Domain key to validate

    Returns:
        True if domain is valid and active, False otherwise
    """
    try:
        conn = get_db_connection()
        if conn is None:
            logger.debug("validate_domain %s: no DB connection", domain)
            return False
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT is_active
                    FROM domains
                    WHERE domain_key = %s
                """,
                    (domain,),
                )
                result = cur.fetchone()
                return result is not None and result[0]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error validating domain {domain}: {e}")
        return False


def get_all_domains() -> list:
    """
    Get list of all active domains.

    Returns:
        List of domain dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT domain_key, name, schema_name, display_order
                FROM domains
                WHERE is_active = TRUE
                ORDER BY display_order
            """)
            return cur.fetchall()
    finally:
        conn.close()


def get_domain_data_schemas() -> tuple[str, ...]:
    """Postgres schema names for all active domains (built-in + YAML). Single source: domain_registry."""
    from shared.domain_registry import get_schema_names_active

    return get_schema_names_active()


def normalize_domain_to_schema(domain_key: str) -> str:
    """Map route/domain key to DB schema (e.g. science-tech → science_tech)."""
    return (domain_key or "").replace("-", "_")


def resolve_article_id_to_schema(article_id: int) -> str | None:
    """Return which domain schema contains this article id, or None."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            for sch in get_domain_data_schemas():
                cur.execute(
                    f"SELECT 1 FROM {sch}.articles WHERE id = %s LIMIT 1",
                    (article_id,),
                )
                if cur.fetchone():
                    return sch
        return None
    except Exception as e:
        logger.debug("resolve_article_id_to_schema(%s): %s", article_id, e)
        return None
    finally:
        conn.close()


def resolve_storyline_id_to_schema(storyline_id: int) -> str | None:
    """Return which domain schema contains this storyline id, or None."""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            for sch in get_domain_data_schemas():
                cur.execute(
                    f"SELECT 1 FROM {sch}.storylines WHERE id = %s LIMIT 1",
                    (storyline_id,),
                )
                if cur.fetchone():
                    return sch
        return None
    except Exception as e:
        logger.debug("resolve_storyline_id_to_schema(%s): %s", storyline_id, e)
        return None
    finally:
        conn.close()


def parse_optional_domain_to_schema(domain: str | None) -> str | None:
    """
    Validate optional domain string and return schema name.
    Raises ValueError if domain is non-empty but invalid.
    """
    if domain is None or str(domain).strip() == "":
        return None
    s = normalize_domain_to_schema(domain.strip())
    if s not in get_domain_data_schemas():
        raise ValueError(f"Invalid domain: {domain}")
    return s
