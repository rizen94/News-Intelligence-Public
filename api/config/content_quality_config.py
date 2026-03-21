"""
Content quality thresholds for briefings, storylines, and events.
See docs/CONTENT_QUALITY_STANDARDS.md.
"""

# Minimum quality tier for inclusion (1=best, 4=clickbait)
MIN_TIER_FOR_STORYLINES = 3  # Tier 3 and above eligible for storyline discovery
MIN_TIER_FOR_BRIEFINGS = 2  # Tier 2 and above preferred for briefing lead/key developments
MIN_TIER_FOR_EVENTS = 2  # Tier 2 and above for event extraction

# Clickbait: score >= this (0-1) → treat as Tier 4
AUTO_REJECT_CLICKBAIT_THRESHOLD = 0.8

# Analysis
MIN_WORD_COUNT_FOR_ANALYSIS = 200
EMOTION_WORD_DENSITY_THRESHOLD = 0.3

# When True, Tier 1 requires named sources in content
REQUIRE_NAMED_SOURCES_FOR_TIER_1 = True
