"""Eight-step loop orchestrator (shadow mode default)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nri_core.loop.detect.cooccurrence import detect_cooccurrence, reject_missing_base_rate
from nri_core.loop.promote.gate import check_promotion
from nri_core.loop.queue.selector import select_entities
from nri_core.loop.reason.ach_synthesizer import reason_candidate
from nri_core.loop.reassess.rules import ReassessMetrics, reassess_hypotheses
from nri_core.loop.skeptic.agent import apply_skeptic_corrections, review_note
from nri_core.loop.delta.gather import gather_delta
from nri_core.config import get_config, require_prod_safety
from vault.writer.git_writer import commit_iteration, write_note


def run_iteration(iteration: int, shadow: bool = True) -> dict[str, Any]:
    cfg = get_config()
    if not cfg.loop_enabled:
        return {"skipped": True, "reason": "NRI_LOOP_ENABLED=false"}
    require_prod_safety()

    batch = select_entities(limit=5, prune_slots=2)
    summary: dict[str, Any] = {
        "iteration": iteration,
        "entities": batch.entity_ids,
        "metrics": ReassessMetrics().__dict__,
        "candidates": 0,
        "hypotheses_written": 0,
    }

    total_metrics = ReassessMetrics()
    for ftm_id in batch.entity_ids:
        delta = gather_delta(ftm_id)
        candidates = detect_cooccurrence([ftm_id], since_context_id=0)
        candidates = [c for c in candidates if reject_missing_base_rate(c.to_dict())]
        summary["candidates"] += len(candidates)

        metrics = reassess_hypotheses(ftm_id, new_evidence_ids=delta.get("new_fact_ids", []), iteration=iteration)
        total_metrics.killed += metrics.killed
        total_metrics.demoted += metrics.demoted
        total_metrics.dormant += metrics.dormant

        for cand in candidates[:3]:
            dossier = {"facts": delta.get("facts", []), "hypotheses": delta.get("hypotheses", [])}
            ach = reason_candidate(cand.to_dict(), dossier)
            hyp_id = f"hyp-{ftm_id[:8]}-{iteration}-{cand.pattern_type}"
            content = f"""---
hyp_id: {hyp_id}
claim: Pattern {cand.pattern_type} for {ftm_id}
status: open
confidence: {ach.confidence}
supports: []
competing_hypotheses: {ach.competing_hypotheses}
disconfirming_test: {ach.cheapest_test}
test_status: pending
mundane_explanation: {ach.mundane_explanation}
iteration_introduced: {iteration}
subject_ftm_id: {ftm_id}
---

{ach.mundane_explanation}
"""
            if cfg.vault_write:
                write_note(Path("hypotheses") / f"{hyp_id}.md", content, shadow=shadow)
                total_metrics.added += 1
                summary["hypotheses_written"] += 1

                note_path = Path(cfg.vault_path) / "hypotheses" / f"{hyp_id}.md"
                skeptic = review_note(note_path.read_text(encoding="utf-8"))
                apply_skeptic_corrections(str(note_path), skeptic)

                check_promotion({"test_status": "pending"})

    reassess_label = "killed" if total_metrics.killed else "demoted" if total_metrics.demoted else "added"
    if cfg.vault_write and batch.entity_ids:
        commit_iteration(iteration, batch.entity_ids[0], reassess_label)

    summary["metrics"] = {
        "killed": total_metrics.killed,
        "demoted": total_metrics.demoted,
        "dormant": total_metrics.dormant,
        "added": total_metrics.added,
    }
    _record_loop_run(iteration, batch.entity_ids[0] if batch.entity_ids else None, total_metrics, shadow)
    return summary


def _record_loop_run(
    iteration: int,
    entity_ftm_id: str | None,
    metrics: ReassessMetrics,
    shadow: bool,
) -> None:
    from nri_core.evidence import ni_reader
    from nri_core.config import get_config

    cfg = get_config()
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {cfg.nri_schema}.loop_run
                    (iteration, entity_ftm_id, killed, demoted, dormant, added, shadow_branch, finished_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    iteration,
                    entity_ftm_id,
                    metrics.killed,
                    metrics.demoted,
                    metrics.dormant,
                    metrics.added,
                    "shadow/iteration" if shadow else "main",
                ),
            )
        conn.commit()
