"""
Canonical Postgres silo surface for YAML-onboarded domains (migration 180/187 pattern).

Shared by verify_domain_provision.py, generate_domain_artifacts.py, and operators.
"""

from __future__ import annotations

# Tables created via create_domain_table(..., template schema) in order.
SILO_CORE_TABLES: tuple[str, ...] = (
    "articles",
    "topics",
    "storylines",
    "rss_feeds",
    "article_topic_assignments",
    "storyline_articles",
    "topic_clusters",
    "topic_cluster_memberships",
    "topic_learning_history",
    "entity_canonical",
    "article_entities",
)

# Added in migration 193 for optional silos; default ON for new domains via manifest.
SILO_OPTIONAL_TABLES: tuple[str, ...] = ("article_topic_clusters",)

# Minimum for pipeline + UI smoke checks.
SILO_CRITICAL_TABLES: frozenset[str] = frozenset({"articles", "rss_feeds", "storylines", "topics"})

# Full parity with create_domain_table + story_entity_index (migration 180).
SILO_EXTENDED_TABLES: frozenset[str] = frozenset(
    {
        "article_topic_assignments",
        "storyline_articles",
        "topic_clusters",
        "topic_cluster_memberships",
        "topic_learning_history",
        "entity_canonical",
        "article_entities",
        "story_entity_index",
        "article_topic_clusters",
    }
)

DEFAULT_CLONE_FROM_SCHEMA = "politics"
