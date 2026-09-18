"""
Arc-stage inference for typed storyline patterns (Phase 5).

Maps domain storyline_patterns (filing→hearing→ruling, bill-to-law, etc.)
onto the furthest stage evidenced by chronological_events / titles.
Persists into storylines.quality_metrics.arc_stage for attach priors.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)

# Ordered stages per named pattern. First match wins when choosing pattern.
ARC_PATTERN_STAGES: dict[str, list[str]] = {
    "litigation": ["filing", "hearing", "ruling", "appeal"],
    "bill_to_law": ["introduction", "committee", "vote", "signature", "effective"],
    "regulatory_rulemaking": ["proposal", "comment", "final_rule", "enforcement"],
    "local_ordinance": ["hearing", "vote", "implementation"],
    "campaign": ["candidacy", "primary", "general", "outcome"],
    "policy_battle": ["proposal", "debate", "vote", "implementation"],
    "conflict": ["escalation", "diplomacy", "resolution"],
    "trade_war": ["tariff", "retaliation", "negotiation", "settlement"],
    "research_evidence": ["hypothesis", "trial", "result", "replication"],
}

_STAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "filing": ("filed", "complaint", "lawsuit filed", "indictment", "petition filed"),
    "hearing": ("hearing", "oral argument", "preliminary hearing", "motion hearing"),
    "ruling": ("ruled", "ruling", "judgment", "decision", "held that", "opinion issued"),
    "appeal": ("appeal", "appealed", "appellate", "certiorari"),
    "introduction": ("introduced", "bill introduced", "filed a bill", "sponsor"),
    "committee": ("committee", "markup", "reported out", "subcommittee"),
    "vote": ("vote", "passed", "defeated", "floor vote", "approved the bill"),
    "signature": ("signed into law", "signed the bill", "vetoed", "enacted"),
    "effective": ("takes effect", "effective date", "went into effect"),
    "proposal": ("proposed rule", "notice of proposed", "nprm", "proposed"),
    "comment": ("comment period", "public comment", "seeking comments"),
    "final_rule": ("final rule", "finalized", "adopted the rule"),
    "enforcement": ("enforcement action", "fine", "penalty", "cited for"),
    "implementation": ("implement", "implementation", "rolled out"),
    "candidacy": ("announced candidacy", "running for", "enters the race"),
    "primary": ("primary", "primaries", "nomination"),
    "general": ("general election", "election day", "ballot"),
    "outcome": ("won the election", "elected", "defeated", "concession"),
    "debate": ("debate", "markup fight", "floor fight"),
    "escalation": ("escalat", "attack", "invasion", "strike"),
    "diplomacy": ("ceasefire", "talks", "negotiat", "summit"),
    "resolution": ("peace deal", "treaty", "resolved", "withdrawal"),
    "tariff": ("tariff", "duty", "import tax"),
    "retaliation": ("retaliat", "counter-tariff", "tit-for-tat"),
    "negotiation": ("trade talks", "negotiation", "deal talks"),
    "settlement": ("settlement", "trade deal", "agreement reached"),
    "hypothesis": ("hypothesis", "propose that", "theorize"),
    "trial": ("clinical trial", "phase 1", "phase 2", "phase 3", "study enrolled"),
    "result": ("results show", "findings", "efficacy", "endpoint met"),
    "replication": ("replication", "replicated", "confirmed findings"),
}

_PATTERN_ALIASES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"litigation|court|lawsuit|docket", re.I), "litigation"),
    (re.compile(r"bill.?to.?law|legislation|legislative", re.I), "bill_to_law"),
    (re.compile(r"rulemaking|regulatory", re.I), "regulatory_rulemaking"),
    (re.compile(r"ordinance|municipal", re.I), "local_ordinance"),
    (re.compile(r"campaign|election", re.I), "campaign"),
    (re.compile(r"policy battle|policy", re.I), "policy_battle"),
    (re.compile(r"conflict|war|geopolit", re.I), "conflict"),
    (re.compile(r"trade war|tariff", re.I), "trade_war"),
    (re.compile(r"research|trial|evidence", re.I), "research_evidence"),
]


@dataclass
class ArcStageResult:
    pattern: str | None
    stage: str | None
    stage_index: int
    stages: list[str]
    matched_event_ids: list[int]
    evidence: list[str]


def arc_stage_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("arc_stage_inference", default=False):
            return True
    except Exception:
        pass
    return env_bool("ARC_STAGE_INFERENCE_ENABLED", False)


def choose_pattern(domain_key: str, patterns: list[str] | None = None) -> str | None:
    """Pick the best typed pattern for a domain from config text or defaults."""
    blob = " ".join(patterns or [])
    for pat, key in _PATTERN_ALIASES:
        if pat.search(blob):
            return key
    defaults = {
        "legal": "litigation",
        "politics": "policy_battle",
        "finance": "trade_war",
        "medicine": "research_evidence",
        "artificial-intelligence": "research_evidence",
    }
    return defaults.get(domain_key)


def detect_stages_in_text(text: str, stages: list[str]) -> list[str]:
    """Return stages whose keywords appear in text, in pattern order."""
    lower = (text or "").lower()
    found: list[str] = []
    for stage in stages:
        kws = _STAGE_KEYWORDS.get(stage, (stage.replace("_", " "),))
        if any(kw in lower for kw in kws):
            found.append(stage)
    return found


def furthest_stage(stages: list[str], detected: list[str]) -> tuple[str | None, int]:
    best_idx = -1
    best: str | None = None
    for d in detected:
        try:
            idx = stages.index(d)
        except ValueError:
            continue
        if idx > best_idx:
            best_idx = idx
            best = d
    return best, best_idx


def infer_arc_stage(
    domain_key: str,
    storyline_id: int,
    *,
    persist: bool = True,
    conn=None,
) -> dict[str, Any]:
    """
    Infer arc_stage for a storyline from chronological events + pattern config.

    Returns dict with pattern, stage, stage_index, stages, matched_event_ids.
    When persist=True, merges into quality_metrics.
    """
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(domain_key)
    patterns: list[str] = []
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain_key)
        patterns = list(cfg.storyline_patterns or [])
    except Exception:
        pass

    pattern = choose_pattern(domain_key, patterns)
    stages = list(ARC_PATTERN_STAGES.get(pattern or "", []))
    if not stages:
        return {
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "pattern": pattern,
            "stage": None,
            "stage_index": -1,
            "stages": [],
            "matched_event_ids": [],
            "enabled": arc_stage_enabled(),
        }

    def _run(db) -> dict[str, Any]:
        detected: list[str] = []
        evidence: list[str] = []
        matched_ids: list[int] = []
        with db.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(title, ''), COALESCE(event_type, ''),
                       COALESCE(description, '')
                FROM public.chronological_events
                WHERE storyline_id = %s
                ORDER BY COALESCE(actual_event_date, created_at) ASC NULLS LAST
                LIMIT 80
                """,
                (storyline_id,),
            )
            rows = list(cur.fetchall() or [])
            if not rows:
                cur.execute(
                    f"""
                    SELECT ce.id, COALESCE(ce.title, ''), COALESCE(ce.event_type, ''),
                           COALESCE(ce.description, '')
                    FROM public.chronological_events ce
                    JOIN {schema}.storyline_articles sa
                      ON sa.article_id = ce.source_article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY COALESCE(ce.actual_event_date, ce.created_at) ASC NULLS LAST
                    LIMIT 80
                    """,
                    (storyline_id,),
                )
                rows = list(cur.fetchall() or [])

        for eid, title, etype, desc in rows:
            blob = f"{title} {etype} {desc}"
            hits = detect_stages_in_text(blob, stages)
            if hits:
                matched_ids.append(int(eid))
                for h in hits:
                    if h not in detected:
                        detected.append(h)
                        evidence.append(f"{h}:{title[:80]}")

        stage, idx = furthest_stage(stages, detected)
        result = ArcStageResult(
            pattern=pattern,
            stage=stage,
            stage_index=idx,
            stages=stages,
            matched_event_ids=matched_ids,
            evidence=evidence[:12],
        )
        if persist and stage:
            _persist_arc_stage(schema, storyline_id, result, conn=db)
        return {
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "pattern": result.pattern,
            "stage": result.stage,
            "stage_index": result.stage_index,
            "stages": result.stages,
            "matched_event_ids": result.matched_event_ids,
            "evidence": result.evidence,
            "enabled": arc_stage_enabled(),
        }

    try:
        if conn is not None:
            return _run(conn)
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as db:
            return _run(db)
    except Exception as e:
        logger.warning("infer_arc_stage %s/%s: %s", domain_key, storyline_id, e)
        return {
            "domain_key": domain_key,
            "storyline_id": storyline_id,
            "pattern": pattern,
            "stage": None,
            "stage_index": -1,
            "stages": stages,
            "error": str(e)[:200],
        }


def arc_stage_attach_prior(
    domain_key: str | None,
    storyline_id: int | None,
    *,
    article_text: str | None = None,
) -> float:
    """
    Small [0,1] prior for blend_link_score when article text advances/continues
    the inferred arc stage. Returns 0.5 neutral when disabled/unknown.
    """
    if not domain_key or not storyline_id or not arc_stage_enabled():
        return 0.5
    try:
        info = infer_arc_stage(domain_key, int(storyline_id), persist=False)
        stages = info.get("stages") or []
        stage = info.get("stage")
        if not stages or not stage:
            return 0.5
        idx = int(info.get("stage_index") or -1)
        # Prefer next expected stage keywords in the candidate article
        next_stage = stages[idx + 1] if 0 <= idx < len(stages) - 1 else stage
        hits = detect_stages_in_text(article_text or "", [next_stage, stage])
        if next_stage in hits:
            return 0.85
        if stage in hits:
            return 0.7
        return 0.45
    except Exception:
        return 0.5


def _persist_arc_stage(
    schema: str,
    storyline_id: int,
    result: ArcStageResult,
    *,
    conn,
) -> None:
    patch = {
        "arc_stage": result.stage,
        "arc_pattern": result.pattern,
        "arc_stage_index": result.stage_index,
        "arc_stage_inferred_at": datetime.now(timezone.utc).isoformat(),
    }
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {schema}.storylines
            SET quality_metrics = COALESCE(quality_metrics, '{{}}'::jsonb) || %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (json.dumps(patch), storyline_id),
        )
    try:
        conn.commit()
    except Exception:
        pass
