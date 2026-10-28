"""NRI resolver triage constants (parked cross-domain noise, bridge QA captions)."""

from __future__ import annotations

# Parked mentions that recur across domains but are poor alias candidates.
PARKED_GENERIC_MENTIONS: frozenset[str] = frozenset(
    {
        "us",
        "eu",
        "ai",
        "war",
        "trial",
        "trials",
        "election",
        "elections",
        "hearing",
        "united states",
        "earnings call / summit / hearing",
        "full name",
        "org name",
    }
)

# FtM captions that often indicate non-entity topic resolution, not a person/org.
GENERIC_FTM_CAPTIONS: frozenset[str] = frozenset(
    {
        "hearing",
        "trial",
        "trials",
        "lawsuit",
        "election",
        "elections",
        "war",
    }
)

# Similarity thresholds for bridge QA (pure-Python path when pg_trgm unavailable).
BRIDGE_QA_OK_SIMILARITY = 0.85
BRIDGE_QA_SUSPECT_SIMILARITY = 0.60
