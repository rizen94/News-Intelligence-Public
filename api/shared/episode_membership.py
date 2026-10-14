"""Episode membership reads via intelligence.event_episode_links (v12 SSOT).

``chronological_events.storyline_id`` may be stamped as a legacy mirror after a
successful EEL insert, but product counts/citations must join through EEL —
never treat the CE stamp alone as membership.
"""

from __future__ import annotations

from typing import Any


def list_episode_articles_sql(schema: str, *, with_content: bool = False) -> str:
    """
    SELECT list for articles linked to an episode through EEL → CE.source_article_id.

    Params: (domain_key, episode_id)
    """
    content_col = (
        ", left(coalesce(a.content, ''), 8000) AS content" if with_content else ""
    )
    return f"""
        SELECT DISTINCT a.id, a.title, a.url, a.source_domain, a.published_at, a.summary
               {content_col}
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
          AND COALESCE(eel.inference_stage, '') <> 'quarantined'
        ORDER BY a.published_at DESC NULLS LAST
    """


def list_episode_entities_sql(schema: str) -> str:
    """
    Entities on articles that have at least one non-quarantined EEL for this episode.

    Params: (domain_key, episode_id)
    """
    return f"""
        SELECT DISTINCT ON (e.id)
            e.id, e.name, e.entity_type, e.description
        FROM {schema}.entities e
        JOIN {schema}.article_entities ae ON ae.entity_id = e.id
        JOIN public.chronological_events ce ON ce.source_article_id = ae.article_id
        JOIN intelligence.event_episode_links eel ON eel.event_id = ce.id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND COALESCE(eel.inference_stage, '') <> 'quarantined'
        ORDER BY e.id, e.name
        LIMIT 40
    """


def list_episode_source_coverage_sql(schema: str) -> str:
    """Params: (domain_key, episode_id)"""
    return f"""
        SELECT COALESCE(NULLIF(TRIM(a.source_domain), ''), '(unknown)') AS src,
               COUNT(DISTINCT a.id)::int
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
        GROUP BY 1
        ORDER BY COUNT(DISTINCT a.id) DESC, src ASC
    """


def episode_article_count_subquery(schema: str, storyline_alias: str, domain_key: str) -> str:
    """Scalar subquery: distinct article count via EEL for one storyline row."""
    dk = domain_key.replace("'", "''")
    return f"""(
        SELECT COUNT(DISTINCT ce.source_article_id)::int
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = '{dk}'
          AND eel.episode_id = {storyline_alias}.id
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
    )"""


def episode_last_article_at_subquery(schema: str, storyline_alias: str, domain_key: str) -> str:
    """Scalar subquery: MAX(published_at) for EEL-linked articles."""
    dk = domain_key.replace("'", "''")
    return f"""(
        SELECT MAX(a.published_at)
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = '{dk}'
          AND eel.episode_id = {storyline_alias}.id
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
    )"""


def list_unlinked_articles_sql(schema: str) -> str:
    """
    Articles not in the EEL chain for a domain.

    Optional params after domain_key: storyline_id to exclude current episode members.
    """
    return f"""
        SELECT a.id
        FROM {schema}.articles a
        WHERE (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
          AND NOT EXISTS (
              SELECT 1
              FROM public.chronological_events ce
              JOIN intelligence.event_episode_links eel ON eel.event_id = ce.id
              WHERE ce.source_article_id = a.id
                AND eel.domain_key = %s
          )
    """


def count_episode_articles(
    cur,
    *,
    schema: str,
    domain_key: str,
    episode_id: int,
) -> int:
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT ce.source_article_id)::int
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
          AND COALESCE(eel.inference_stage, '') <> 'quarantined'
        """,
        (domain_key, int(episode_id)),
    )
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def episode_last_article_at(
    cur,
    *,
    schema: str,
    domain_key: str,
    episode_id: int,
) -> Any:
    cur.execute(
        f"""
        SELECT MAX(a.published_at)
        FROM intelligence.event_episode_links eel
        JOIN public.chronological_events ce ON ce.id = eel.event_id
        JOIN {schema}.articles a ON a.id = ce.source_article_id
        WHERE eel.domain_key = %s
          AND eel.episode_id = %s
          AND ce.source_article_id IS NOT NULL
          AND (a.enrichment_status IS NULL OR a.enrichment_status != 'removed')
        """,
        (domain_key, int(episode_id)),
    )
    row = cur.fetchone()
    return row[0] if row else None


def fetch_episode_articles(
    cur,
    *,
    schema: str,
    domain_key: str,
    episode_id: int,
) -> list[tuple[Any, ...]]:
    cur.execute(
        list_episode_articles_sql(schema),
        (domain_key, int(episode_id)),
    )
    return list(cur.fetchall() or [])
