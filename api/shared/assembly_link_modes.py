"""
Storyline assembly link modes (Mode A / B / C).

One similarity score must not answer three different questions:

- **same_event** (A): multi-source corroboration of one real-world beat
- **sequence** (B): later development of the same matter / arc
- **causal** (C): consequence link — proposals only, never silent membership

See docs/STORYLINE_CANONICAL_MODEL.md § Assembly link modes.
"""

from __future__ import annotations

from typing import Final

LINK_MODE_SAME_EVENT: Final = "same_event"
LINK_MODE_SEQUENCE: Final = "sequence"
LINK_MODE_CAUSAL: Final = "causal"
LINK_MODE_CAUSAL_REJECTED: Final = "causal_rejected"
LINK_MODE_COSINE_PEER: Final = "cosine_peer"

# Allowed on storyline_articles.metadata->>'link_mode' for silent auto membership
AUTO_MEMBERSHIP_MODES: Final[frozenset[str]] = frozenset(
    {LINK_MODE_SAME_EVENT, LINK_MODE_SEQUENCE}
)

# Entity types that count as durable identity for SQL prefilters (not topical glue)
DURABLE_ENTITY_TYPES: Final[frozenset[str]] = frozenset(
    {
        "person",
        "organization",
        "case_number",
        "legislation_id",
        "company",
        "legal_entity",
    }
)

# Topical / hub types that must not alone admit Mode A/B auto membership
DENY_SOLO_ENTITY_TYPES: Final[frozenset[str]] = frozenset(
    {
        "subject",
        "other",
        "location",
        "recurring_event",
    }
)
