"""
Incremental PhaseSpec registry for high-churn automation phases.

Generates adaptive-batch bounds and Monitor ``BATCH_SIZE_PER_TASK`` defaults from one
place. Legacy registries (``_PHASE_BOUNDS``, ``BATCH_SIZE_PER_TASK``, ``PHASE_POLICIES``)
remain SSOT for phases not listed here — call ``overlay_*`` to merge.

Mins/steps are catch-up oriented: auto-tune may raise further (no max); host headroom
may decrease. Floors must be high enough that backlog can drain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PhaseSpec:
    """Canonical knobs for a workload-driven phase (subset of full policy)."""

    name: str
    adaptive_track: str
    adaptive_min: int
    adaptive_max: int | None
    adaptive_step: int
    batch_size_per_task: int
    skip_when_empty: bool = True
    yield_gate: bool = False


# High-churn phases first (UIE, CTF, chemistry, graph drift) — keep in sync with
# adaptive_batch_policy / backlog_metrics when changing numbers.
HIGH_CHURN_PHASE_SPECS: tuple[PhaseSpec, ...] = (
    PhaseSpec(
        name="unified_intake_extraction",
        adaptive_track="gpu",
        adaptive_min=80,
        adaptive_max=None,
        adaptive_step=40,
        batch_size_per_task=6,
    ),
    PhaseSpec(
        name="claims_to_facts",
        adaptive_track="local",
        adaptive_min=500,
        adaptive_max=None,
        adaptive_step=250,
        batch_size_per_task=200,
    ),
    PhaseSpec(
        name="embedding_link_candidates",
        adaptive_track="chemistry_local",
        adaptive_min=40,
        adaptive_max=None,
        adaptive_step=20,
        batch_size_per_task=12,
    ),
    PhaseSpec(
        name="collision_sampling",
        adaptive_track="chemistry_local",
        adaptive_min=64,
        adaptive_max=None,
        adaptive_step=32,
        batch_size_per_task=8,
    ),
    PhaseSpec(
        name="topic_clustering",
        adaptive_track="gpu",
        adaptive_min=80,
        adaptive_max=None,
        adaptive_step=40,
        batch_size_per_task=40,
    ),
    PhaseSpec(
        name="graph_connection_distillation",
        adaptive_track="local",
        adaptive_min=100,
        adaptive_max=None,
        adaptive_step=50,
        batch_size_per_task=50,
    ),
    PhaseSpec(
        name="stimulus_rag",
        adaptive_track="enrich",
        adaptive_min=40,
        adaptive_max=None,
        adaptive_step=20,
        batch_size_per_task=20,
    ),
    PhaseSpec(
        name="protein_harden",
        adaptive_track="local",
        adaptive_min=80,
        adaptive_max=None,
        adaptive_step=40,
        batch_size_per_task=40,
    ),
    PhaseSpec(
        name="graph_link_drift_review",
        adaptive_track="local",
        adaptive_min=80,
        adaptive_max=None,
        adaptive_step=40,
        batch_size_per_task=40,
    ),
    PhaseSpec(
        name="event_deduplication",
        adaptive_track="local",
        adaptive_min=100,
        adaptive_max=500,
        adaptive_step=50,
        batch_size_per_task=100,
    ),
    PhaseSpec(
        name="story_continuation",
        adaptive_track="local",
        adaptive_min=40,
        adaptive_max=200,
        adaptive_step=20,
        batch_size_per_task=30,
    ),
    PhaseSpec(
        name="entity_organizer",
        adaptive_track="local",
        adaptive_min=200,
        adaptive_max=None,
        adaptive_step=100,
        batch_size_per_task=100,
    ),
    PhaseSpec(
        name="storyline_membership_review",
        adaptive_track="local",
        adaptive_min=100,
        adaptive_max=None,
        adaptive_step=50,
        batch_size_per_task=100,
    ),
)


def _track_constant(track: str) -> Any:
    from shared.catchup_host_metrics import (
        TRACK_BUILD,
        TRACK_CHEMISTRY_LOCAL,
        TRACK_DOSSIER_FAST,
        TRACK_ENRICH,
        TRACK_GPU,
        TRACK_LOCAL,
    )

    return {
        "gpu": TRACK_GPU,
        "local": TRACK_LOCAL,
        "enrich": TRACK_ENRICH,
        "build": TRACK_BUILD,
        "dossier_fast": TRACK_DOSSIER_FAST,
        "chemistry_local": TRACK_CHEMISTRY_LOCAL,
    }.get(track, TRACK_LOCAL)


def phase_spec_by_name() -> dict[str, PhaseSpec]:
    return {s.name: s for s in HIGH_CHURN_PHASE_SPECS}


def adaptive_bounds_from_specs() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for spec in HIGH_CHURN_PHASE_SPECS:
        entry: dict[str, Any] = {
            "track": _track_constant(spec.adaptive_track),
            "min": spec.adaptive_min,
            "max": spec.adaptive_max,
            "step": spec.adaptive_step,
        }
        if spec.yield_gate:
            entry["yield_gate"] = True
        out[spec.name] = entry
    return out


def overlay_adaptive_bounds(bounds: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Return a copy of ``bounds`` with HIGH_CHURN_PHASE_SPECS overlaid (spec wins)."""
    merged = dict(bounds)
    merged.update(adaptive_bounds_from_specs())
    return merged


def overlay_batch_size_per_task(batch_sizes: dict[str, int]) -> dict[str, int]:
    merged = dict(batch_sizes)
    for spec in HIGH_CHURN_PHASE_SPECS:
        merged[spec.name] = spec.batch_size_per_task
    return merged


def skip_when_empty_from_specs() -> frozenset[str]:
    return frozenset(s.name for s in HIGH_CHURN_PHASE_SPECS if s.skip_when_empty)


def overlay_skip_when_empty(phases: frozenset[str] | set[str]) -> frozenset[str]:
    """Union base SKIP_WHEN_EMPTY with PhaseSpec skip flags (spec phases always included when True)."""
    return frozenset(set(phases) | set(skip_when_empty_from_specs()))
