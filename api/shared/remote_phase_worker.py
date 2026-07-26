"""
Remote phase worker ownership — Widow schedules/admits; PopOS (or other hosts) execute.

Env (Widow API — declare which phases are executed elsewhere):
  REMOTE_PHASE_WORKER_OWNED_PHASES=unified_intake_extraction[,other_phase...]

Env (PopOS worker process):
  WORKER_EXECUTION_HOST=popos
  WORKER_PHASES=unified_intake_extraction[,...]

When a phase is remote-owned, Widow AutomationManager disables its schedule and the
pipeline controller will not request local drains for that phase. Backlog metrics still count.

Placement rule: ownership CSV is the only true offload. Policy labels (popos_gpu) do not
move work by themselves.
"""

from __future__ import annotations

from config.runtime import env_str

# Default MVP ownership when Widow opts in via REMOTE_PHASE_WORKER_ENABLED=true
_DEFAULT_OWNED = ("unified_intake_extraction",)

# Recommended ownership CSV for Widow REMOTE_PHASE_WORKER_OWNED_PHASES
# (must match PopOS WORKER_PHASES / split units; claims_to_facts is parallel-only — do not own).
POPOS_WORKER_EXPAND_PHASES: tuple[str, ...] = (
    "unified_intake_extraction",
    "claim_extraction",
    "topic_clustering",
    "storyline_assembly",
    "editorial_research_pass",
    "editorial_narrative_pass",
    "editorial_reduction_pass",
    "chronological_events_catchup",
)

# Allowlist for run_popos_phase_worker — MUST be ⊆ DRAINABLE_PHASES (phase_drain_dispatch).
# claims_to_facts may run on PopOS *in parallel* with Widow (SKIP LOCKED) via a future drain;
# do not add it to REMOTE_PHASE_WORKER_OWNED_PHASES or Widow will stop draining.
POPOS_WORKER_SUPPORTED_PHASES: frozenset[str] = frozenset(
    {
        "unified_intake_extraction",
        "claim_extraction",
        "topic_clustering",
        "storyline_assembly",
        "content_enrichment",
        "entity_profile_build",
        "spine_sql_tail",
        "editorial_research_pass",
        "editorial_narrative_pass",
        "editorial_reduction_pass",
        "chronological_events_catchup",
    }
)


def _parse_phase_csv(raw: str) -> frozenset[str]:
    return frozenset(x.strip() for x in (raw or "").split(",") if x.strip())


def is_remote_phase_worker_process() -> bool:
    """True when this process is the PopOS (or dedicated) phase worker, not Widow API."""
    host = env_str("WORKER_EXECUTION_HOST", "").strip().lower()
    return host in ("popos", "remote", "worker")


def worker_phases() -> frozenset[str]:
    """Phases this worker process is configured to drain."""
    raw = env_str("WORKER_PHASES", "").strip()
    if raw:
        return _parse_phase_csv(raw)
    if is_remote_phase_worker_process():
        return frozenset(_DEFAULT_OWNED)
    return frozenset()


def remote_owned_phases() -> frozenset[str]:
    """
    Phases Widow must not drain locally (executed by a remote worker).

    Explicit CSV wins. If REMOTE_PHASE_WORKER_ENABLED=true and CSV empty, defaults to UIE.
    """
    raw = env_str("REMOTE_PHASE_WORKER_OWNED_PHASES", "").strip()
    if raw:
        return _parse_phase_csv(raw)
    flag = env_str("REMOTE_PHASE_WORKER_ENABLED", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return frozenset(_DEFAULT_OWNED)
    return frozenset()


def phase_owned_by_remote_worker(phase: str) -> bool:
    """True when Widow must skip local execution for ``phase``."""
    if is_remote_phase_worker_process():
        return False
    name = (phase or "").strip()
    return bool(name) and name in remote_owned_phases()


def phase_supported_by_popos_worker(phase: str) -> bool:
    return (phase or "").strip() in POPOS_WORKER_SUPPORTED_PHASES
