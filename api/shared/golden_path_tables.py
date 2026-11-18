"""
Golden path table names — keep in sync with docs/GOLDEN_PATH_DATABASE.md.

Use for dynamic SQL formatting; do not use public.* article/storyline stubs.
"""

from __future__ import annotations

# Domain silo (schema from resolve_domain_schema / pipeline domains)
ARTICLES = "{schema}.articles"
STORYLINES = "{schema}.storylines"
STORYLINE_ARTICLES = "{schema}.storyline_articles"
RSS_FEEDS = "{schema}.rss_feeds"

# Cross-domain staging (always public + domain_key column)
STORYLINE_ARTICLE_SUGGESTIONS = "public.storyline_article_suggestions"

# Ops / monitoring (infrastructure + pipeline schemas)
AUTOMATION_RUN_HISTORY = "infrastructure.automation_run_history"
PIPELINE_PHASE_HEARTBEATS = "pipeline.pipeline_phase_heartbeats"

# Deprecated — do not use in new code
DEPRECATED_PUBLIC_ARTICLES = "public.articles"
DEPRECATED_PIPELINE_SUGGESTIONS = "pipeline.storyline_article_suggestions"
