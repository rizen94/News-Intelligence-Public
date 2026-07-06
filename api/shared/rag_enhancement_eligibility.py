"""Shared eligibility for rag_enhancement (scheduler, backlog, automation).

Enhance when:
  - no row in ``intelligence.storyline_rag_context`` (first pass), or
  - new storyline articles linked after last RAG ``updated_at``, or
  - optional calendar stale when ``RAG_ENHANCEMENT_STALE_HOURS`` > 0.

Uses ``storyline_rag_context.updated_at`` — not the legacy ``storylines.rag_enhanced_at`` column
(which was never migrated to prod).
"""

from __future__ import annotations

from config.runtime import env_str
from shared.domain_registry import iter_pipeline_url_schema_pairs


def rag_enhancement_stale_hours() -> int:
    """Optional calendar stale window; 0 disables time-based re-queue."""
    raw = env_str("RAG_ENHANCEMENT_STALE_HOURS", "0").strip()
    try:
        return max(0, min(8760, int(raw)))
    except ValueError:
        return 0


def sql_rag_storyline_has_articles(s_alias: str = "s", schema: str = "legal") -> str:
    return f"""EXISTS (
        SELECT 1 FROM {schema}.storyline_articles sa
        WHERE sa.storyline_id = {s_alias}.id
    )"""


def sql_rag_never_enhanced(domain_key: str, s_alias: str = "s") -> str:
    dk = domain_key.replace("'", "''")
    return f"""NOT EXISTS (
        SELECT 1 FROM intelligence.storyline_rag_context src
        WHERE src.domain_key = '{dk}' AND src.storyline_id = {s_alias}.id
    )"""


def sql_rag_new_articles_since_enhance(domain_key: str, schema: str, s_alias: str = "s") -> str:
    dk = domain_key.replace("'", "''")
    return f"""EXISTS (
        SELECT 1
        FROM {schema}.storyline_articles sa2
        JOIN {schema}.articles a ON a.id = sa2.article_id
        JOIN intelligence.storyline_rag_context src
          ON src.domain_key = '{dk}' AND src.storyline_id = {s_alias}.id
        WHERE sa2.storyline_id = {s_alias}.id
          AND COALESCE(a.published_at, a.created_at) > src.updated_at
    )"""


def sql_rag_calendar_stale(domain_key: str, s_alias: str = "s") -> str:
    hours = rag_enhancement_stale_hours()
    if hours <= 0:
        return "FALSE"
    dk = domain_key.replace("'", "''")
    return f"""EXISTS (
        SELECT 1 FROM intelligence.storyline_rag_context src
        WHERE src.domain_key = '{dk}'
          AND src.storyline_id = {s_alias}.id
          AND src.updated_at < NOW() - INTERVAL '{int(hours)} hours'
    )"""


def sql_rag_storyline_needs_enhance(domain_key: str, schema: str, s_alias: str = "s") -> str:
    """Pending predicate for one domain schema."""
    never = sql_rag_never_enhanced(domain_key, s_alias)
    articles = sql_rag_new_articles_since_enhance(domain_key, schema, s_alias)
    calendar = sql_rag_calendar_stale(domain_key, s_alias)
    return f"(({never}) OR ({articles}) OR ({calendar}))"


def sql_rag_select_storylines_for_domain(
    domain_key: str,
    schema: str,
    *,
    limit: int,
    s_alias: str = "s",
) -> str:
    """SELECT id, title for storylines due for RAG in one domain."""
    needs = sql_rag_storyline_needs_enhance(domain_key, schema, s_alias)
    has_articles = sql_rag_storyline_has_articles(s_alias, schema)
    dk = domain_key.replace("'", "''")
    return f"""
        SELECT {s_alias}.id, {s_alias}.title
        FROM {schema}.storylines {s_alias}
        WHERE {s_alias}.status = 'active'
          AND {has_articles}
          AND {needs}
        ORDER BY (
            SELECT src.updated_at FROM intelligence.storyline_rag_context src
            WHERE src.domain_key = '{dk}' AND src.storyline_id = {s_alias}.id
        ) ASC NULLS FIRST
        LIMIT {int(limit)}
    """


def count_rag_enhancement_pending() -> int:
    """Count storylines due for RAG across pipeline-active domains."""
    total = 0
    try:
        from shared.database.connection import get_db_connection

        conn = get_db_connection()
        if not conn:
            return 0
        try:
            for domain_key, schema in iter_pipeline_url_schema_pairs():
                needs = sql_rag_storyline_needs_enhance(domain_key, schema)
                has_articles = sql_rag_storyline_has_articles("s", schema)
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '5s'")
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.storylines s
                        WHERE s.status = 'active'
                          AND {has_articles}
                          AND {needs}
                        """
                    )
                    total += int(cur.fetchone()[0] or 0)
        finally:
            conn.close()
    except Exception:
        return 0
    return total
