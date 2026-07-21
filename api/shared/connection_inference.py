"""
Chemistry-style connection inference stages.

hypothesized → candidate → established | quarantined
"""

from __future__ import annotations

from typing import Final

INFERENCE_HYPOTHESIZED: Final = "hypothesized"
INFERENCE_CANDIDATE: Final = "candidate"
INFERENCE_ESTABLISHED: Final = "established"
INFERENCE_QUARANTINED: Final = "quarantined"

INFERENCE_STAGES: frozenset[str] = frozenset(
    {
        INFERENCE_HYPOTHESIZED,
        INFERENCE_CANDIDATE,
        INFERENCE_ESTABLISHED,
        INFERENCE_QUARANTINED,
    }
)

# Monitor / backlog vocabulary aliases
PHASE_COLLISION_SAMPLING = "collision_sampling"
PHASE_STIMULUS_RAG = "stimulus_rag"
PHASE_PROTEIN_HARDEN = "protein_harden"


def normalize_inference_stage(raw: str | None, *, default: str = INFERENCE_CANDIDATE) -> str:
    s = (raw or "").strip().lower()
    return s if s in INFERENCE_STAGES else default


def stage_for_embedding_source(*, exploratory: bool) -> str:
    """Random collisions start hypothesized; prior-driven neighbors are candidates."""
    return INFERENCE_HYPOTHESIZED if exploratory else INFERENCE_CANDIDATE


def promote_stage(current: str, *, survived_stimulus: bool) -> str:
    cur = normalize_inference_stage(current)
    if not survived_stimulus:
        return INFERENCE_QUARANTINED
    if cur == INFERENCE_HYPOTHESIZED:
        return INFERENCE_CANDIDATE
    if cur == INFERENCE_CANDIDATE:
        return INFERENCE_ESTABLISHED
    return cur
