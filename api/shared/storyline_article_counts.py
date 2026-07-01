"""Helpers to keep storyline article_count / total_articles aligned with storyline_articles."""

from __future__ import annotations

from typing import Any, Protocol


class _HasArticleIds(Protocol):
    article_ids: list[int]


def distinct_article_count(members: list[_HasArticleIds]) -> int:
    """Distinct article_id count across storylines (ignores stale article_count columns)."""
    seen: set[int] = set()
    for member in members:
        for aid in member.article_ids or []:
            if aid:
                seen.add(int(aid))
    return len(seen)


def storyline_article_count_subquery(schema: str, storyline_alias: str = "s") -> str:
    """SQL scalar subquery: COUNT(*) for one storyline row."""
    return (
        f"(SELECT COUNT(*)::int FROM {schema}.storyline_articles sa "
        f"WHERE sa.storyline_id = {storyline_alias}.id)"
    )


def sync_counts_update_sql(schema: str, storyline_id_placeholder: str = "%s") -> str:
    """SET clause syncing article_count and total_articles from storyline_articles."""
    return f"""article_count = (
            SELECT COUNT(*)::int FROM {schema}.storyline_articles
            WHERE storyline_id = {storyline_id_placeholder}
        ),
        total_articles = (
            SELECT COUNT(*)::int FROM {schema}.storyline_articles
            WHERE storyline_id = {storyline_id_placeholder}
        )"""


def reconcile_all_storyline_counts(cur, schema: str, *, include_merged: bool = True) -> int:
    """
    Reconcile article_count and total_articles from storyline_articles.
    By default includes archived/merged rows (folded megas often retain inflated counts).
    Returns number of rows updated.
    """
    merged_filter = "" if include_merged else "WHERE s2.merged_into_id IS NULL"
    cur.execute(
        f"""
        UPDATE {schema}.storylines s
        SET article_count = c.cnt,
            total_articles = c.cnt,
            updated_at = NOW()
        FROM (
            SELECT s2.id,
                   (
                       SELECT COUNT(*)::int
                       FROM {schema}.storyline_articles sa
                       WHERE sa.storyline_id = s2.id
                   ) AS cnt
            FROM {schema}.storylines s2
            {merged_filter}
        ) c
        WHERE s.id = c.id
          AND (
            s.article_count IS DISTINCT FROM c.cnt
            OR s.total_articles IS DISTINCT FROM c.cnt
          )
        """
    )
    return int(cur.rowcount or 0)


def sync_derived_metrics_update_sql(schema: str, storyline_id_placeholder: str = "%s") -> str:
    """SET clause for total_entities and time_span_days derived from index + articles."""
    return f"""total_entities = (
            SELECT COUNT(DISTINCT entity_name)::int
            FROM {schema}.story_entity_index
            WHERE storyline_id = {storyline_id_placeholder}
        ),
        time_span_days = COALESCE((
            SELECT GREATEST(
                0,
                EXTRACT(DAY FROM MAX(a.published_at) - MIN(a.published_at))
            )::int
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = {storyline_id_placeholder}
              AND a.published_at IS NOT NULL
        ), 0)"""


def sync_storyline_derived_metrics(cur, schema: str, storyline_id: int) -> None:
    """Refresh total_entities and time_span_days for one storyline."""
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET {sync_derived_metrics_update_sql(schema)},
            updated_at = NOW()
        WHERE id = %s
        """,
        (storyline_id, storyline_id, storyline_id),
    )


def reconcile_all_storyline_derived_metrics(cur, schema: str) -> int:
    """Backfill total_entities and time_span_days for all non-merged storylines."""
    cur.execute(
        f"""
        UPDATE {schema}.storylines s
        SET total_entities = COALESCE(ent.cnt, 0),
            time_span_days = COALESCE(span.span, 0),
            updated_at = NOW()
        FROM {schema}.storylines s2
        LEFT JOIN (
            SELECT storyline_id, COUNT(DISTINCT entity_name)::int AS cnt
            FROM {schema}.story_entity_index
            GROUP BY storyline_id
        ) ent ON ent.storyline_id = s2.id
        LEFT JOIN (
            SELECT sa.storyline_id,
                   GREATEST(
                       0,
                       EXTRACT(DAY FROM MAX(a.published_at) - MIN(a.published_at))
                   )::int AS span
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE a.published_at IS NOT NULL
            GROUP BY sa.storyline_id
        ) span ON span.storyline_id = s2.id
        WHERE s.id = s2.id
          AND s2.merged_into_id IS NULL
          AND (
            s.total_entities IS DISTINCT FROM COALESCE(ent.cnt, 0)
            OR s.time_span_days IS DISTINCT FROM COALESCE(span.span, 0)
          )
        """
    )
    return int(cur.rowcount or 0)


def reconcile_topics_article_count(cur, schema: str) -> int:
    """Sync topics.article_count from article_topic_assignments."""
    cur.execute(
        f"""
        UPDATE {schema}.topics t
        SET article_count = sub.cnt,
            updated_at = NOW()
        FROM (
            SELECT topic_id, COUNT(DISTINCT article_id)::int AS cnt
            FROM {schema}.article_topic_assignments
            GROUP BY topic_id
        ) sub
        WHERE t.id = sub.topic_id
          AND t.article_count IS DISTINCT FROM sub.cnt
        """
    )
    return int(cur.rowcount or 0)


def reconcile_article_word_counts(cur, schema: str) -> int:
    """Backfill articles.word_count from content where zero or null."""
    cur.execute(
        f"""
        UPDATE {schema}.articles
        SET word_count = CASE
            WHEN content IS NULL OR trim(content) = '' THEN 0
            ELSE cardinality(regexp_split_to_array(trim(content), '\\s+'))
        END,
        updated_at = NOW()
        WHERE word_count IS NULL OR word_count = 0
        """
    )
    return int(cur.rowcount or 0)
