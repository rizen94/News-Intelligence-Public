"""
Shared constants for cache TTLs and other tunables.
Use these instead of magic numbers when adding or tuning cache/interval values.
"""

# Cache TTLs (seconds)
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hour
CACHE_TTL_30MIN = 1800  # 30 minutes
CACHE_TTL_24H = 86400  # 24 hours

# Pipeline state constants — re-exported for backward compatibility.
# Prefer direct imports from shared.pipeline_state_constants instead.
from shared.pipeline_state_constants import (
    ARTICLE_PENDING, ARTICLE_ENRICHED, ARTICLE_FAILED, ARTICLE_INACCESSIBLE,
    ARTICLE_CONTENT_SHORT, ARTICLE_TERMINAL_STATES, ARTICLE_NON_TERMINAL_STATES,
    QUEUE_PENDING, QUEUE_PROCESSING, QUEUE_COMPLETED, QUEUE_FAILED,
    QUEUE_TERMINAL_STATES, ML_PENDING, ML_RUNNING, ML_COMPLETED, ML_FAILED,
    PIPELINE_PHASES, PHASE_GROUP,
)
