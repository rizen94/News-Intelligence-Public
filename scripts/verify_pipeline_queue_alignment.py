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
