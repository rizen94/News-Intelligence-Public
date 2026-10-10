"""
Corpus vs research processing-mode SSOT.

Domains with ``processing_mode='corpus'`` run intake / fact-check / index phases only.
Domains with ``processing_mode='research'`` (default) also run storyline / chemistry /
narrative assembly.

Queue depth counters MUST use the same gate as drains — otherwise corpus domains
produce phantom research backlog (same class of bug as CTF / membership miscounts).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

from config.runtime import env_str

logger = logging.getLogger(__name__)

PROCESSING_MODE_CORPUS = "corpus"
PROCESSING_MODE_RESEARCH = "research"
VALID_PROCESSING_MODES: frozenset[str] = frozenset(
    {PROCESSING_MODE_CORPUS, PROCESSING_MODE_RESEARCH}
)

# Intake → appraisal → promote → index. Corpus domains stop here.
CORPUS_PHASES: frozenset[str] = frozenset(
    {
        "collection_cycle",
        "content_enrichment",
        "unified_intake_extraction",
        "spine_sql_tail",
        "claim_extraction",
        "claims_to_facts",
        "extracted_claims_dedupe",
        "claim_subject_gap_refresh",
        "claim_evidence_appraisal",
        "fact_verification",
        "context_sync",
        "embeddings_worker",
        "document_processing",
        "topic_clustering",
        # Literature collectors (neurodiversity / corpus domains)
        "europepmc_collector",
        "pubmed_eutils_collector",
    }
)

# Storyline / chemistry / narrative — research domains only.
RESEARCH_PHASES: frozenset[str] = frozenset(
    {
        "entity_organizer",
        "graph_connection_distillation",
        "entity_profile_build",
        "entity_profile_sync",
        "event_tracking",
        "story_continuation",
        "storyline_assembly",
        "storyline_automation",
        "storyline_membership_review",
        "editorial_room_loop",
        "entity_dossier_compile",
        "collision_sampling",
        "embedding_link_candidates",
        "stimulus_rag",
        "protein_harden",
        "rag_enhancement",
        "mention_resolution",
        "investigation_report_refresh",
        "arc_report_generation",
        "narrative_thread_build",
        "storyline_discovery",
        "proactive_detection",
        "graph_link_drift_review",
        "event_coreference",
        "rolling_arc_refresh",
    }
)


def normalize_processing_mode(raw: str | None) -> str:
    mode = (raw or PROCESSING_MODE_RESEARCH).strip().lower()
    if mode not in VALID_PROCESSING_MODES:
        return PROCESSING_MODE_RESEARCH
    return mode


def normalize_phase_name(phase: str | None) -> str:
    return (phase or "").strip().lower().replace("-", "_")


@lru_cache(maxsize=1)
def _modes_from_yaml() -> dict[str, str]:
    """Bootstrap map from domain YAML when DB column is unavailable."""
    out: dict[str, str] = {}
    try:
        from shared.domain_registry import _load_yaml_domain_files

        for entry in _load_yaml_domain_files():
            dk = str(entry.get("domain_key") or "").strip()
            if not dk:
                continue
            out[dk] = normalize_processing_mode(entry.get("processing_mode"))
    except Exception as e:  # pragma: no cover
        logger.debug("processing_mode yaml load skipped: %s", e)
    return out


def clear_processing_mode_caches() -> None:
    _modes_from_yaml.cache_clear()
    cached = get_domain_processing_modes
    if hasattr(cached, "cache_clear"):
        cached.cache_clear()


@lru_cache(maxsize=1)
def get_domain_processing_modes() -> dict[str, str]:
    """
    Map domain_key → processing_mode from ``public.domains`` when available,
    else YAML bootstrap.
    """
    yaml_modes = dict(_modes_from_yaml())
    try:
        from psycopg2.extras import RealDictCursor

        from shared.database.connection import get_ui_db_connection
    except Exception:
        return yaml_modes

    conn = get_ui_db_connection()
    if not conn:
        return yaml_modes
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Column may not exist pre-migration 282
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'domains'
                  AND column_name = 'processing_mode'
                """
            )
            if not cur.fetchone():
                return yaml_modes
            cur.execute(
                """
                SELECT domain_key, processing_mode
                FROM public.domains
                """
            )
            rows = cur.fetchall()
    except Exception as e:
        logger.debug("processing_mode DB load failed: %s", e)
        return yaml_modes
    finally:
        try:
            conn.close()
        except Exception:
            pass

    out = dict(yaml_modes)
    for r in rows or []:
        dk = str(r.get("domain_key") or "").strip()
        if not dk:
            continue
        out[dk] = normalize_processing_mode(r.get("processing_mode"))
    return out


def get_domain_processing_mode(domain_key: str | None) -> str:
    dk = (domain_key or "").strip()
    if not dk:
        return PROCESSING_MODE_RESEARCH
    return get_domain_processing_modes().get(dk, PROCESSING_MODE_RESEARCH)


def is_corpus_domain(domain_key: str | None) -> bool:
    return get_domain_processing_mode(domain_key) == PROCESSING_MODE_CORPUS


def is_research_domain(domain_key: str | None) -> bool:
    return get_domain_processing_mode(domain_key) == PROCESSING_MODE_RESEARCH


def phase_band(phase: str | None) -> str | None:
    """
    Return ``corpus``, ``research``, or None when the phase is shared / unknown.

    Shared/unknown phases are allowed for both modes (fail-open for ops safety
    on unclassified schedule names).
    """
    p = normalize_phase_name(phase)
    if not p:
        return None
    if p in RESEARCH_PHASES:
        return PROCESSING_MODE_RESEARCH
    if p in CORPUS_PHASES:
        return PROCESSING_MODE_CORPUS
    return None


def domain_runs_phase(domain_key: str | None, phase: str | None) -> bool:
    """
    True when ``domain_key`` should execute / count work for ``phase``.

    Override: ``PROCESSING_MODE_ENFORCE=0`` disables the gate (emergency).
    """
    if env_str("PROCESSING_MODE_ENFORCE", "true").lower() in ("0", "false", "no", "off"):
        return True
    band = phase_band(phase)
    if band is None:
        return True
    mode = get_domain_processing_mode(domain_key)
    if mode == PROCESSING_MODE_RESEARCH:
        return True
    # corpus domain: only corpus-band phases
    return band == PROCESSING_MODE_CORPUS


def filter_domains_for_phase(
    domains: Iterable[str],
    phase: str | None,
) -> list[str]:
    return [d for d in domains if domain_runs_phase(d, phase)]


def corpus_domain_keys() -> list[str]:
    return sorted(
        dk
        for dk, mode in get_domain_processing_modes().items()
        if mode == PROCESSING_MODE_CORPUS
    )


def research_domain_keys() -> list[str]:
    return sorted(
        dk
        for dk, mode in get_domain_processing_modes().items()
        if mode == PROCESSING_MODE_RESEARCH
    )
