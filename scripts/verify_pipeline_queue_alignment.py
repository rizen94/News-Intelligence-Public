#!/usr/bin/env python3
"""Verify pipeline queue_depth aligns with actionable SQL (Monitor / bulk catch-up SSOT)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
if str(API) not in sys.path:
    sys.path.insert(0, str(API))


def _static_regressions() -> list[str]:
    errors: list[str] = []
    bm = API / "services" / "backlog_metrics.py"
    text = bm.read_text(encoding="utf-8")

    for fn_name in ("_count_unified_intake_extraction_pending", "_count_content_enrichment_backlog"):
        marker = f"def {fn_name}"
        if marker not in text:
            errors.append(f"missing {fn_name} in backlog_metrics.py")
            continue
        start = text.index(marker)
        next_def = text.find("\ndef ", start + len(marker))
        body = text[start:next_def] if next_def != -1 else text[start:]
        if "count_all_pending" in body:
            errors.append(f"{fn_name} must not use spine count_all_pending for queue_depth")
        if "spine_work_queues_enabled" in body and "return q" in body:
            errors.append(f"{fn_name} must not prefer spine queue over eligibility SQL")

    for rel in (
        "services/spine_pipeline_conductor.py",
        "services/assembly_conductor_service.py",
    ):
        path = API / rel
        if not path.is_file():
            continue
        ctext = path.read_text(encoding="utf-8")
        if re.search(
            r'pending\s*=\s*int\s*\(\s*get_all_backlog_counts\s*\(\s*\)',
            ctext,
        ):
            errors.append(f"{rel}: shadow pending must not come from get_all_backlog_counts()")
        if '"queue_depth"' in ctext and "get_phase_queue_depth" not in ctext:
            errors.append(f"{rel}: shadow mode must use get_phase_queue_depth for queue_depth")

    claim_path = API / "services" / "claim_extraction_service.py"
    if claim_path.is_file():
        ctext = claim_path.read_text(encoding="utf-8")
        if re.search(
            r'persist_automation_run_history\s*\(\s*["\']claims_to_facts["\']',
            ctext,
        ):
            errors.append(
                "claim_extraction_service: claims_to_facts must use record_phase_batch_completion "
                "(not persist_automation_run_history with empty metadata)"
            )

    # storyline_assembly queue_depth must use threshold-gated domains (drain/idle SSOT)
    sa_start = text.find("def _count_storyline_assembly_pending")
    if sa_start == -1:
        errors.append("missing _count_storyline_assembly_pending in backlog_metrics.py")
    else:
        sa_end = text.find("\ndef ", sa_start + 1)
        sa_body = text[sa_start:sa_end if sa_end != -1 else None]
        if "count_assembly_actionable_pending" not in sa_body:
            errors.append(
                "_count_storyline_assembly_pending must use count_assembly_actionable_pending "
                "(domains_needing_assembly semantics)"
            )
        if "get_pipeline_active_domain_keys" in sa_body and "count_assembly_actionable_pending" not in sa_body:
            errors.append(
                "_count_storyline_assembly_pending must not sum all-domain unlinked without threshold"
            )

    # topic_clustering queue_depth must match select_pending_article_ids / count_pending_articles
    tc_start = text.find("def _count_topic_clustering_pending")
    if tc_start == -1:
        errors.append("missing _count_topic_clustering_pending in backlog_metrics.py")
    else:
        tc_end = text.find("\ndef ", tc_start + 1)
        tc_body = text[tc_start:tc_end if tc_end != -1 else None]
        if "count_pending_articles" not in tc_body:
            errors.append(
                "_count_topic_clustering_pending must use TopicClusteringService.count_pending_articles"
            )
        if "sql_article_pass_null" in tc_body:
            errors.append(
                "_count_topic_clustering_pending must not use sql_article_pass_null "
                "(that includes retries; drain is first-pass-only by default)"
            )

    # Membership / collision / embedding / CTF must delegate to drain SSOT helpers
    memb = text.find("def _count_storyline_membership_review_pending")
    if memb == -1:
        errors.append("missing _count_storyline_membership_review_pending")
    else:
        memb_end = text.find("\ndef ", memb + 1)
        memb_body = text[memb:memb_end if memb_end != -1 else None]
        if "count_storylines_needing_membership_review" not in memb_body:
            errors.append(
                "_count_storyline_membership_review_pending must use "
                "count_storylines_needing_membership_review"
            )
        if "storyline_membership_actions" in memb_body:
            errors.append(
                "_count_storyline_membership_review_pending must not count pending actions "
                "(automation drains megas via _pick_storylines)"
            )

    coll = text.find("def _count_collision_sampling_pending")
    if coll == -1:
        errors.append("missing _count_collision_sampling_pending")
    else:
        coll_end = text.find("\ndef ", coll + 1)
        coll_body = text[coll:coll_end if coll_end != -1 else None]
        if "count_collision_sampling_actionable" not in coll_body:
            errors.append(
                "_count_collision_sampling_pending must use count_collision_sampling_actionable"
            )
        if "graph_connection_proposals" in coll_body:
            errors.append(
                "_count_collision_sampling_pending must not count hypothesized proposals "
                "(those belong to graph_connection_distillation)"
            )

    emb = text.find("def _count_embedding_link_candidates_pending")
    if emb == -1:
        errors.append("missing _count_embedding_link_candidates_pending")
    else:
        emb_end = text.find("\ndef ", emb + 1)
        emb_body = text[emb:emb_end if emb_end != -1 else None]
        if "count_embedding_link_candidates_due" not in emb_body:
            errors.append(
                "_count_embedding_link_candidates_pending must use "
                "count_embedding_link_candidates_due"
            )

    ctf = API / "services" / "claim_extraction_service.py"
    if ctf.is_file():
        ctf_text = ctf.read_text(encoding="utf-8")
        mode_fn = ctf_text.find("def get_claims_to_facts_backlog_count_mode")
        if mode_fn == -1:
            errors.append("missing get_claims_to_facts_backlog_count_mode")
        else:
            mode_end = ctf_text.find("\ndef ", mode_fn + 1)
            mode_body = ctf_text[mode_fn:mode_end if mode_end != -1 else None]
            if 'env_str("CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE", "batch_candidate")' not in mode_body:
                errors.append(
                    "CLAIMS_TO_FACTS_BACKLOG_COUNT_MODE default must be batch_candidate "
                    "(queue_depth == promote SELECT)"
                )

    return errors


def _runtime_alignment() -> list[str]:
    errors: list[str] = []
    try:
        from services.backlog_metrics import get_all_pending_counts, invalidate_backlog_metrics_cache
        from services.phase_work_queue_metrics import get_all_phase_work_queues
        from shared.monitor_dimension_metrics import DIMENSION_PHASE_MAP, get_all_dimension_backlogs
        from shared.pipeline_queue_counts import get_all_phase_queue_depths, verify_unified_intake_alignment
        from shared.queue_audit import build_queue_audit
    except Exception as exc:
        msg = str(exc).lower()
        if any(x in msg for x in ("password", "connection", "connect", "refused")):
            print(f"runtime alignment skipped (no DB): {exc}", file=sys.stderr)
            return []
        return [f"import failed: {exc}"]

    try:
        invalidate_backlog_metrics_cache()
        pending = get_all_pending_counts()
        queue_depths = get_all_phase_queue_depths()
        alignment = verify_unified_intake_alignment(pending)
        if not alignment.get("matches_actionable_sql"):
            errors.append(
                "unified_intake queue_depth != actionable_unified_intake: "
                f"queue_depth={alignment.get('queue_depth')} "
                f"actionable={alignment.get('actionable_unified_intake')} "
                f"spine_queue_depth={alignment.get('spine_queue_depth')}"
            )

        audit = build_queue_audit(pending)
        ui = (audit.get("phases") or {}).get("unified_intake_extraction") or {}
        if ui and not ui.get("error"):
            if not ui.get("matches_actionable_sql"):
                errors.append("queue_audit unified_intake matches_actionable_sql is false")

        claim = (audit.get("phases") or {}).get("claim_extraction") or {}
        if claim and not claim.get("error"):
            if not claim.get("matches_actionable_sql"):
                errors.append("queue_audit claim_extraction matches_actionable_sql is false")

        for phase in (
            "claims_to_facts",
            "storyline_membership_review",
            "collision_sampling",
            "embedding_link_candidates",
        ):
            row = (audit.get("phases") or {}).get(phase) or {}
            if row.get("error"):
                errors.append(f"queue_audit {phase} error: {row.get('error')}")
            elif row and not row.get("matches_actionable_sql"):
                errors.append(
                    f"queue_audit {phase} matches_actionable_sql is false: "
                    f"queue_depth={row.get('queue_depth')} ssot={row.get('ssot_count')}"
                )

        # Live SSOT recount must equal the counters that feed queue_depth (no cache).
        from shared.pipeline_queue_counts import verify_claims_to_facts_alignment
        from services.backlog_metrics import (
            _count_claims_to_facts_pending,
            _count_collision_sampling_pending,
            _count_embedding_link_candidates_pending,
            _count_storyline_membership_review_pending,
        )
        from services.storyline_membership_review_service import (
            count_storylines_needing_membership_review,
        )
        from services.embedding_link_candidate_service import (
            count_collision_sampling_actionable,
            count_embedding_link_candidates_due,
        )

        pairs = [
            ("claims_to_facts", _count_claims_to_facts_pending, _count_claims_to_facts_pending),
            (
                "storyline_membership_review",
                _count_storyline_membership_review_pending,
                count_storylines_needing_membership_review,
            ),
            (
                "collision_sampling",
                _count_collision_sampling_pending,
                count_collision_sampling_actionable,
            ),
            (
                "embedding_link_candidates",
                _count_embedding_link_candidates_pending,
                count_embedding_link_candidates_due,
            ),
        ]
        for phase, backlog_fn, drain_fn in pairs:
            b = int(backlog_fn() or 0)
            d = int(drain_fn() or 0)
            if b != d:
                errors.append(
                    f"{phase} backlog counter != drain SSOT: backlog={b} drain_ssot={d}"
                )

        ctf_align = verify_claims_to_facts_alignment(
            {"claims_to_facts": int(_count_claims_to_facts_pending() or 0)}
        )
        if not ctf_align.get("matches_actionable_sql"):
            errors.append(
                "claims_to_facts queue_depth != promote-eligible count: "
                f"queue_depth={ctf_align.get('queue_depth')} "
                f"promote_eligible={ctf_align.get('promote_eligible_count')}"
            )

        work_queues = get_all_phase_work_queues(pending)
        for phase in ("unified_intake_extraction", "claim_extraction", "entity_profile_build"):
            wq = work_queues.get(phase) or {}
            expected = int(pending.get(phase) or 0)
            total = int(wq.get("total_pending") or 0)
            if total != expected:
                errors.append(
                    f"phase_work_queue total_pending != queue_depth for {phase}: "
                    f"{total} != {expected}"
                )

        dim_backlogs = get_all_dimension_backlogs(queue_depths)
        for dim_id, phase in DIMENSION_PHASE_MAP.items():
            expected = int(queue_depths.get(phase) or 0)
            actual = int(dim_backlogs.get(dim_id) or 0)
            if actual != expected:
                errors.append(
                    f"dimension {dim_id} backlog != queue_depth({phase}): {actual} != {expected}"
                )

        try:
            from services.claim_extraction_service import get_context_claim_backlog_stats

            stats = get_context_claim_backlog_stats()
            actionable = int(stats.get("actionable_no_claims") or 0)
            claim_depth = int(queue_depths.get("claim_extraction") or 0)
            if actionable != claim_depth:
                errors.append(
                    f"actionable_no_claims != queue_depth(claim_extraction): "
                    f"{actionable} != {claim_depth}"
                )
        except Exception as exc:
            msg = str(exc).lower()
            if not any(x in msg for x in ("password", "connection", "connect", "refused")):
                errors.append(f"claim actionable alignment check failed: {exc}")
    except Exception as exc:
        msg = str(exc).lower()
        if "password" in msg or "connection" in msg or "connect" in msg:
            print(f"runtime alignment skipped (no DB): {exc}", file=sys.stderr)
            return []
        errors.append(f"runtime alignment check failed: {exc}")

    return errors


def main() -> int:
    errors = _static_regressions()
    errors.extend(_runtime_alignment())

    if errors:
        print("Pipeline queue alignment FAILED:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Pipeline queue alignment OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
