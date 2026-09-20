#!/usr/bin/env python3
"""
One-line bulk / pipeline catch-up status for a second terminal.

  cd /opt/news-intelligence
  PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup_status.py
  PYTHONPATH=api .venv/bin/python3 api/scripts/bulk_catchup_status.py --watch 60
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_ROOT.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

CHECKPOINT = _REPO_ROOT / "data" / "bulk_catchup_state.json"
PAUSE_MARKER = _REPO_ROOT / "data" / "bulk_catchup_competition_pause.json"
PROGRESS = _REPO_ROOT / "data" / "bulk_catchup_progress.json"
BULK_SINCE = "2026-06-10T14:00:00"
PROGRESS_PHASES = ("event_tracking", "context_sync", "content_enrichment")

# Phases shown in the generic pending list (independent queues — not summable).
OPERATOR_PENDING_PHASES = (
    "unified_intake_extraction",
    "claim_extraction",
    "entity_profile_build",
    "event_tracking",
    "context_sync",
    "content_enrichment",
    "topic_clustering",
)


def _load_env() -> None:
    env_file = _REPO_ROOT / ".env"
    if env_file.is_file():
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)


def _bulk_pid() -> str | None:
    try:
        out = subprocess.check_output(["pgrep", "-f", "bulk_catchup.py"], text=True).strip()
        for line in out.splitlines():
            if "bash" not in line and "bulk_catchup_status" not in line:
                return line.split()[0] if line else None
        return out.splitlines()[0].split()[0] if out else None
    except subprocess.CalledProcessError:
        return None


def _bulk_elapsed(pid: str | None) -> str:
    if not pid:
        return "-"
    try:
        out = subprocess.check_output(["ps", "-p", pid, "-o", "etime="], text=True).strip()
        return out or "-"
    except subprocess.CalledProcessError:
        return "-"


def _checkpoint() -> dict:
    if CHECKPOINT.is_file():
        try:
            return json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _backlog() -> dict[str, int]:
    import importlib.util

    path = _API_ROOT / "services" / "backlog_metrics.py"
    spec = importlib.util.spec_from_file_location("_bulk_status_bm", path)
    if not spec or not spec.loader:
        return {}
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_all_pending_counts()


def _unified_intake_stats() -> dict[str, int]:
    try:
        from shared.unified_intake_backlog import get_unified_intake_backlog_stats

        return get_unified_intake_backlog_stats()
    except Exception:
        return {}


def _claim_stats() -> dict[str, int]:
    try:
        from services.claim_extraction_service import get_context_claim_backlog_stats

        return get_context_claim_backlog_stats()
    except Exception:
        return {}


def _intake_mode_label() -> str:
    try:
        from shared.pipeline_resource_policy import intake_extraction_suppressed

        return "unified" if intake_extraction_suppressed() else "legacy"
    except Exception:
        return "unknown"


def _entity_stats() -> dict:
    from shared.database.connection import get_db_connection_context

    schemas = ("politics", "finance", "legal", "medicine", "artificial_intelligence")
    parts = []
    for sch in schemas:
        parts.append(
            f"""
            SELECT metadata::jsonb->'pipeline'->'entity_extraction'->>'last_outcome' AS outcome,
                   metadata::jsonb->'pipeline'->'entity_extraction'->>'last_terminal_state' AS terminal,
                   metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at' AS pass_at
            FROM {sch}.articles
            WHERE metadata::jsonb->'pipeline'->'entity_extraction'->>'last_pass_at' > %s
            """
        )
    sql = f"""
        SELECT
          COUNT(*) FILTER (WHERE outcome = 'entities_stored') AS total_stored,
          COUNT(*) FILTER (WHERE terminal = 'failed_needs_retry') AS needs_retry,
          COUNT(*) FILTER (
            WHERE pass_at::timestamptz >= NOW() - INTERVAL '1 hour'
              AND outcome = 'entities_stored'
          ) AS stored_1h,
          MAX(pass_at) AS last_pass
        FROM ({' UNION ALL '.join(parts)}) x
    """
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (BULK_SINCE,) * len(schemas))
            row = cur.fetchone()
    if not row:
        return {}
    return {
        "total_stored": int(row[0] or 0),
        "needs_retry": int(row[1] or 0),
        "stored_1h": int(row[2] or 0),
        "last_pass": str(row[3]) if row[3] else None,
    }


def _progress_baseline() -> dict | None:
    if not PROGRESS.is_file():
        return None
    try:
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    except Exception:
        return None


def _bar(done: int, total: int, width: int = 36) -> str:
    if total <= 0:
        return "[" + ("-" * width) + "]"
    ratio = min(1.0, max(0.0, done / total))
    filled = int(width * ratio)
    return "[" + ("#" * filled) + ("-" * (width - filled)) + "]"


def render_progress() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pid = _bulk_pid()
    running = "RUNNING" if pid else "STOPPED"
    baseline = _progress_baseline() or {}
    pending = _backlog()
    ck = _checkpoint()
    current = baseline.get("current_phase") or ck.get("current_phase") or "-"
    phase_info = (ck.get("phases") or {}).get(current) or {}
    lines = [
        f"=== Bulk progress @ {now} ===",
        f"bulk_catchup: {running}  pid={pid or '-'}  elapsed={_bulk_elapsed(pid)}",
        f"active phase: {current}  loops={phase_info.get('loops', '-')}",
        "",
    ]
    for phase in PROGRESS_PHASES:
        init = int((baseline.get("phases") or {}).get(phase, {}).get("initial_pending") or 0)
        remain = int(pending.get(phase) or 0)
        if init > 0:
            done = max(0, init - remain)
            pct = 100.0 * done / init
            status = (baseline.get("phases") or {}).get(phase, {}).get("status", "")
            marker = ">" if phase == current and pid else " "
            lines.append(
                f"{marker}{phase:22} {_bar(done, init)} {done:,}/{init:,} ({pct:5.1f}%)  left {remain:,}  {status}"
            )
        else:
            lines.append(f" {phase:22} (no baseline)  pending {remain:,}")
    lines.append("")
    lines.append(f"log: /tmp/bulk_catchup.log")
    return "\n".join(lines)


def _recent_errors(limit: int = 5) -> list[tuple[str, int]]:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT LEFT(COALESCE(error_message, 'unknown'), 90), COUNT(*)
                FROM public.automation_run_history
                WHERE success = false
                  AND started_at >= NOW() - INTERVAL '48 hours'
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [(str(r[0]), int(r[1])) for r in cur.fetchall()]


def render() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    pid = _bulk_pid()
    running = "RUNNING" if pid else "STOPPED"
    ck = _checkpoint()
    phase = ck.get("current_phase") or "-"
    phase_info = (ck.get("phases") or {}).get(phase) or {}
    pending = _backlog()
    unified = _unified_intake_stats()
    claims = _claim_stats()
    ent = _entity_stats()
    intake_mode = _intake_mode_label()
    lines = [
        f"=== Bulk / pipeline status @ {now} ===",
        f"bulk_catchup: {running}  pid={pid or '-'}  elapsed={_bulk_elapsed(pid)}",
        f"competition_pause: {'ON' if PAUSE_MARKER.is_file() else 'OFF'}",
        f"checkpoint phase: {phase}  loops={phase_info.get('loops', '-')}  last_batch={phase_info.get('last_result', {})}",
        f"intake_mode: {intake_mode}",
        "",
        "Note: phase queues are independent (articles vs contexts vs profiles). Do not sum rows.",
        "",
    ]

    if intake_mode == "unified":
        lines.extend(
            [
                "Unified intake backlog (articles):",
                f"  actionable (LLM work):      {unified.get('actionable_unified_intake', pending.get('unified_intake_extraction', 0)):,}",
                f"  legacy_backfill_eligible:   {unified.get('legacy_backfill_eligible', 0):,}  (marker-only, no GPU)",
                f"  inventory_missing_pass:     {unified.get('inventory_missing_pass', unified.get('total_missing_unified_pass', 0)):,}  (inventory)",
                f"  total_missing_unified_pass: {unified.get('total_missing_unified_pass', 0):,}  (legacy alias)",
                "",
                "Claim extraction backlog (contexts):",
                f"  actionable (queue):         {claims.get('actionable_no_claims', pending.get('claim_extraction', 0)):,}",
                f"  total_no_claims:            {claims.get('total_no_claims', 0):,}  (inventory, not all actionable)",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Legacy intake mode — unified_intake_extraction masked in Monitor.",
                f"  entity_extraction pending:  {pending.get('entity_extraction', 0):,}",
                "",
                "Claim extraction backlog (contexts):",
                f"  actionable (queue):         {claims.get('actionable_no_claims', pending.get('claim_extraction', 0)):,}",
                f"  total_no_claims:            {claims.get('total_no_claims', 0):,}  (inventory)",
                "",
            ]
        )

    lines.append("Per-phase pending (independent — do not sum):")
    for ph in OPERATOR_PENDING_PHASES:
        if ph == "unified_intake_extraction" and intake_mode != "unified":
            continue
        if ph == "entity_extraction":
            continue
        val = int(pending.get(ph) or 0)
        if val > 0 or ph in ("unified_intake_extraction", "claim_extraction", "entity_profile_build"):
            lines.append(f"  {ph:28} {val:,}")

    if intake_mode == "unified":
        legacy_ent = int(pending.get("entity_extraction") or 0)
        lines.append(
            f"  {'entity_extraction (masked)':28} {legacy_ent:,}  (Monitor shows 0 in unified mode)"
        )

    lines.extend(
        [
            "",
            "Entity extraction pass markers (since bulk start — historical, not current queue):",
            f"  total_stored: {ent.get('total_stored', 0):,}  needs_retry: {ent.get('needs_retry', 0):,}",
            f"  last_1h: {ent.get('stored_1h', 0):,}/hr  last_pass: {ent.get('last_pass', '-')}",
        ]
    )

    actionable = unified.get("actionable_unified_intake") or pending.get("unified_intake_extraction")
    if intake_mode == "unified" and ent.get("stored_1h") and actionable:
        eta_h = actionable / max(ent["stored_1h"], 1)
        lines.append(f"  unified intake ETA @ entity 1h rate (rough): ~{eta_h:.1f}h")

    errs = _recent_errors()
    if errs:
        lines.append("")
        lines.append("Top errors (48h automation_run_history):")
        for msg, n in errs:
            lines.append(f"  [{n}x] {msg}")
    return "\n".join(lines)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description="Bulk catch-up status snapshot")
    parser.add_argument("--watch", type=int, default=0, metavar="SEC", help="Refresh every N seconds")
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Progress bars for event_tracking → context_sync → content_enrichment chain",
    )
    args = parser.parse_args()
    render_fn = render_progress if args.progress else render
    if args.watch > 0:
        try:
            while True:
                print(render_fn())
                print()
                time.sleep(args.watch)
        except KeyboardInterrupt:
            return 0
    print(render_fn())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
