"""
Chemistry beaker — connection lifecycle after RSS / intake preprocess clears.

Atoms → loose collisions → stimuli (score/RAG) → protein harden.
Master gate: CHEMISTRY_BEAKER_ENABLED (default true). Per-phase env vars override when set
to a non-empty value.
"""

from __future__ import annotations

from typing import Final

from config.runtime import env_str

# Ordered stir sequence after intake preprocess is stable (Widow-local / DB-heavy first).
POST_INTAKE_BEAKER_PHASES: Final[tuple[str, ...]] = (
    "graph_connection_distillation",
    "embedding_link_candidates",
    "collision_sampling",
    "stimulus_rag",
    "protein_harden",
)

BEAKER_PHASE_SET: Final[frozenset[str]] = frozenset(POST_INTAKE_BEAKER_PHASES)


def chemistry_beaker_enabled() -> bool:
    """Master switch — default on so the beaker runs after RSS intake processing."""
    return env_str("CHEMISTRY_BEAKER_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )


def _phase_enabled(env_name: str) -> bool:
    """Non-empty env overrides master; empty → follow CHEMISTRY_BEAKER_ENABLED."""
    raw = env_str(env_name, "")
    if raw:
        return raw.lower() in ("1", "true", "yes")
    return chemistry_beaker_enabled()


def collision_sampling_enabled() -> bool:
    return _phase_enabled("COLLISION_SAMPLING_ENABLED")


def stimulus_rag_enabled() -> bool:
    return _phase_enabled("RAG_EVIDENCE_PULL_ENABLED")


def protein_harden_enabled() -> bool:
    return _phase_enabled("PROTEIN_HARDEN_ENABLED")


def embedding_link_candidates_enabled() -> bool:
    return _phase_enabled("EMBEDDING_LINK_CANDIDATES_ENABLED")


def get_post_intake_beaker_phases() -> list[str]:
    """Phases to request when RSS intake preprocess is clear (governance override)."""
    try:
        from config.orchestrator_governance import get_orchestrator_governance_config

        raw = (get_orchestrator_governance_config().get("pipeline_controller") or {}).get(
            "post_intake_beaker_phases"
        )
        if isinstance(raw, list) and raw:
            return [str(p).strip() for p in raw if str(p).strip()]
    except Exception:
        pass
    return list(POST_INTAKE_BEAKER_PHASES)


def intake_preprocess_clear_for_beaker(pending: dict[str, int] | None = None) -> bool:
    """True when enrichment + unified intake are low enough to stir the beaker."""
    if not chemistry_beaker_enabled():
        return False
    p = pending
    if p is None:
        try:
            from services.backlog_metrics import get_all_pending_counts

            p = get_all_pending_counts()
        except Exception:
            p = {}
    try:
        from services.pipeline_controller import catchup_clear_threshold

        thresh = max(1, int(catchup_clear_threshold()))
    except Exception:
        thresh = 50
    enrich = int((p or {}).get("content_enrichment", 0) or 0)
    uie = int((p or {}).get("unified_intake_extraction", 0) or 0)
    return (enrich + uie) <= thresh


def kickoff_beaker_phases(automation: object, *, reason: str = "post_intake") -> list[str]:
    """
    Request beaker phases on AutomationManager when intake is clear.
    Returns phase names that were requested.
    """
    if not chemistry_beaker_enabled():
        return []
    if not intake_preprocess_clear_for_beaker():
        return []
    request = getattr(automation, "request_phase", None)
    if not callable(request):
        return []
    requested: list[str] = []
    for phase in get_post_intake_beaker_phases():
        if phase == "collision_sampling" and not collision_sampling_enabled():
            continue
        if phase == "stimulus_rag" and not stimulus_rag_enabled():
            continue
        if phase == "protein_harden" and not protein_harden_enabled():
            continue
        if phase == "embedding_link_candidates" and not embedding_link_candidates_enabled():
            continue
        try:
            request(phase)
            requested.append(phase)
        except Exception:
            continue
    if requested:
        import logging

        logging.getLogger(__name__).info(
            "Chemistry beaker kickoff (%s): %s", reason, ", ".join(requested)
        )
    return requested
