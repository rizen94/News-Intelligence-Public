"""Single source of truth for operator catch-up env defaults.

Tuned June 2026: PopOS GPU for LLM lanes, fast dossier compile on Widow DB/CPU,
parallel narrative backfill on PopOS, relaxed dossier auto-tune (TRACK_DOSSIER_FAST).

Shell operators source ``scripts/catchup_env.sh`` (mirrors these keys).
Python catch-up scripts call :func:`apply_catchup_env_defaults` after loading ``.env``.
"""

from __future__ import annotations

from config.runtime import env_set, env_setdefault, env_str

# Defaults apply only when the key is unset (operator / .env wins).
CATCHUP_ENV_DEFAULTS: dict[str, str] = {
    "OLLAMA_DUAL_HOST_ROUTING_ENABLED": "true",
    "BULK_USE_POPOS_GPU": "true",
    "MAJOR_CATCHUP_USE_POPOS_GPU": "true",
    "BULK_DUAL_LANE_CATCHUP": "true",
    "DOSSIER_CATCHUP_SKIP_NARRATIVE": "true",
    "DOSSIER_COMPILE_PARALLEL": "12",
    "MAJOR_CATCHUP_DOSSIER_BATCH_MIN": "100",
    "DOSSIER_CATCHUP_GPU_NARRATIVE": "true",
    "DOSSIER_NARRATIVE_PARALLEL": "4",
    "MAJOR_CATCHUP_NARRATIVE_BATCH_INITIAL": "40",
    "BULK_EXTRACTION_MODEL": "qwen2.5:32b-instruct",
    "BULK_CPU_EXTRACTION_MODEL": "llama3.1:8b",
    "EVENT_EXTRACTION_PARALLEL": "9",
    "EVENT_EXTRACTION_BATCH_SIZE": "3",
    "MAJOR_CATCHUP_GPU_PARALLEL": "3",
    "MAJOR_CATCHUP_CPU_PARALLEL": "3",
    "BULK_GPU_PARALLEL": "3",
    "BULK_CPU_PARALLEL": "3",
    "MAJOR_CATCHUP_BATCH_INITIAL": "200",
    "MAJOR_CATCHUP_BUILD_BATCH_INITIAL": "120",
    "MAJOR_CATCHUP_STORY_FACTS_ONLY": "true",
    "MAJOR_CATCHUP_CUT_STALE_FACTS_DAYS": "30",
    "MAJOR_CATCHUP_GPU_METRICS_SSH": "pete@192.168.93.99",
    "MAJOR_CATCHUP_BATCH_MIN": "10",
    "MAJOR_CATCHUP_BATCH_MAX": "500",
    "MAJOR_CATCHUP_BATCH_STEP": "10",
    "MAJOR_CATCHUP_BUILD_BATCH_MAX": "200",
    "MAJOR_CATCHUP_ENRICH_BATCH_MAX": "500",
    "BULK_OLLAMA_TIMEOUT": "600",
    "MAJOR_CATCHUP_OLLAMA_TIMEOUT": "600",
    "DOSSIER_CATCHUP_PARALLEL_DEFAULT": "8",
    "DOSSIER_NARRATIVE_PARALLEL_DEFAULT": "4",
    "ENTITY_EXTRACTION_BATCH_SIZE": "3",
    "ENTITY_EXTRACTION_PARALLEL": "6",
    "AUTOMATION_USE_POPOS_GPU": "true",
    "AUTOMATION_DUAL_LANE": "true",
    "AUTOMATION_GPU_PARALLEL": "3",
    "AUTOMATION_CPU_PARALLEL": "2",
    "AUTOMATION_FIXED_RESOURCE_POLICY": "true",
    "EVENT_EXTRACTION_RUN_BUDGET_SECONDS": "0",
    "ENTITY_EXTRACTION_RUN_BUDGET_SECONDS": "0",
    "PIPELINE_REFINEMENT_BULK_CLEAR_THRESHOLD": "50",
    "STORY_ENHANCEMENT_FACTS_ONLY": "true",
    "UNIFIED_INTAKE_EXTRACTION_ENABLED": "true",
    "FAST_NER_ENABLED": "true",
    "FAST_NER_BACKEND": "both",
    "CONTEXT_CHUNKING_ENABLED": "true",
    "UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE": "3",
    "UNIFIED_INTAKE_EXTRACTION_PARALLEL": "6",
    "UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS": "0",
    "PIPELINE_DRAIN_STALL_ROUNDS": "3",
    "INTAKE_FUSION_ENABLED": "true",
    "ENTITY_PROFILE_BUILD_UPSTREAM_GATE": "true",
}

# Applied when bulk_active=True (burn-down / catch-up scripts). Operator .env wins via setdefault.
AGGRESSIVE_BURN_DOWN_DEFAULTS: dict[str, str] = {
    "CLAIM_EXTRACTION_BATCH_LIMIT": "3500",
    "CLAIM_EXTRACTION_PARALLEL": "40",
    "CLAIM_EXTRACTION_DRAIN_MAX_SECONDS": "0",
    "CLAIM_EXTRACTION_DRAIN_MAX_ZERO_CLAIM_BATCHES": "25",
    "CLAIM_EXTRACTION_DRAIN_MAX_BATCHES": "0",
    "CLAIMS_TO_FACTS_BATCH_LIMIT": "15000",
    "ENTITY_EXTRACTION_PARALLEL": "8",
    "ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN": "40",
    "ENTITY_EXTRACTION_RUN_BUDGET_SECONDS": "7200",
    "EVENT_EXTRACTION_PARALLEL": "12",
    "EVENT_EXTRACTION_RUN_BUDGET_SECONDS": "7200",
    "BULK_GPU_PARALLEL": "8",
    "BULK_CPU_PARALLEL": "4",
    "OLLAMA_GPU_CONCURRENCY": "8",
    "OLLAMA_CPU_CONCURRENCY": "4",
    "AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES": "claim_extraction:1",
    "UNIFIED_INTAKE_EXTRACTION_RUN_BUDGET_SECONDS": "7200",
    "UNIFIED_INTAKE_EXTRACTION_BATCH_SIZE": "6",
    "UNIFIED_INTAKE_EXTRACTION_PARALLEL": "8",
    "BULK_EXTRACTION_MODEL": "qwen2.5:14b-instruct",
    "FAST_NER_BACKEND": "spacy",
}

_POPOS_GPU_FALLBACK = "http://192.168.93.99:11434"


def apply_aggressive_burn_down_defaults() -> None:
    """PopOS-saturated parallel defaults for one-shot backlog burn-down."""
    for key, value in AGGRESSIVE_BURN_DOWN_DEFAULTS.items():
        env_setdefault(key, value)


def apply_catchup_env_defaults(*, bulk_active: bool = False) -> None:
    """Apply catch-up defaults without overriding explicit operator env."""
    for key, value in CATCHUP_ENV_DEFAULTS.items():
        env_setdefault(key, value)

    popos = env_str("OLLAMA_POP_OS_HOST", "").strip()
    env_setdefault("OLLAMA_GPU_HOST", popos or _POPOS_GPU_FALLBACK)

    if bulk_active:
        env_set("BULK_CATCHUP_ACTIVE", "1")
        apply_aggressive_burn_down_defaults()
