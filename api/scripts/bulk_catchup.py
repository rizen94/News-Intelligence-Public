#!/usr/bin/env python3
"""
One-time bulk pipeline catch-up (operator-run, resumable, idempotent).

Bypasses quiet-hour gating with --force (one-time historical drain only).

  PYTHONPATH=api python3 api/scripts/bulk_catchup.py --dry-run
  PYTHONPATH=api python3 api/scripts/bulk_catchup.py --force --phase entity_extraction
  PYTHONPATH=api python3 api/scripts/bulk_catchup.py --force

Checkpoint: data/bulk_catchup_state.json
"""
from __future__ import annotations
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str


import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

_REPO_ROOT = _API_ROOT.parent
CHECKPOINT_PATH = _REPO_ROOT / "data" / "bulk_catchup_state.json"

logger = logging.getLogger(__name__)


def _load_env() -> None:
    from shared.catchup_bootstrap import bootstrap_catchup

    bootstrap_catchup(bulk_active=False)


def _get_backlog_metrics_module():
    """Import backlog_metrics without loading services/__init__.py (pulls AutomationManager)."""
    import importlib.util

    path = _API_ROOT / "services" / "backlog_metrics.py"
    spec = importlib.util.spec_from_file_location("_bulk_backlog_metrics", path)
    if not spec or not spec.loader:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

BULK_PHASE_ORDER: tuple[str, ...] = (
    "content_enrichment",
    "unified_intake_extraction",
    "spine_sql_tail",
    "metadata_enrichment",
    "context_sync",
    "claim_extraction",
    "event_tracking",
    "embeddings_worker",
    "topic_clustering",
    "storyline_discovery",
)


def _load_checkpoint() -> dict:
    if CHECKPOINT_PATH.is_file():
        try:
            return json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"started_at": None, "phases": {}, "current_phase": None}


def _save_checkpoint(state: dict) -> None:
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _schedule_allowed(force: bool) -> bool:
    if force:
        return True
    from services.pipeline_schedule_service import automation_phase_allowed

    return automation_phase_allowed("entity_extraction")


def _queue_depth_for_phase(phase: str) -> int:
    """Actionable queue depth for phase (same semantics as Monitor queue_depth)."""
    mod = _get_backlog_metrics_module()
    return int(mod.get_all_pending_counts().get(phase) or 0)


def _pending_for_phase(phase: str) -> int:
    """Deprecated alias for _queue_depth_for_phase."""
    return _queue_depth_for_phase(phase)


def _format_phase_queue_line(phase: str, depth: int) -> str:
    """Log queue_depth; for unified intake include inventory when it differs."""
    if phase != "unified_intake_extraction":
        return f"Phase {phase}: queue_depth={depth}"
    try:
        from shared.pipeline_queue_counts import get_unified_intake_breakdown

        b = get_unified_intake_breakdown()
        inv = int(b["inventory_missing_pass"])
        spine = int(b["spine_queue_depth"])
        extra = []
        if inv != depth:
            extra.append(f"inventory_missing_pass={inv}")
        if spine and spine != depth:
            extra.append(f"spine_queue_depth={spine}")
        suffix = f" ({', '.join(extra)})" if extra else ""
        return f"Phase {phase}: queue_depth={depth}{suffix}"
    except Exception:
        return f"Phase {phase}: queue_depth={depth}"


def _log_nri_watermark_lag() -> None:
    """PR6: log NRI mention_resolver lag after entity batches (read-only)."""
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                from config.investigation_tables import T_WATERMARKS

                cur.execute(
                    f"SELECT last_value FROM {T_WATERMARKS} WHERE name = 'mention_resolver'"
                )
                row = cur.fetchone()
                wm = int(row[0]) if row else 0
                cur.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM intelligence.context_entity_mentions"
                )
                max_id = int(cur.fetchone()[0] or 0)
        lag = max_id - wm
        if lag > 5000:
            logger.warning(
                "NRI mention_resolver lag %s ids (watermark=%s max_mention=%s); "
                "consider increasing BULK_NRI_MENTION_BATCH_PAUSE",
                lag,
                wm,
                max_id,
            )
        else:
            logger.info("NRI mention_resolver lag %s ids", lag)
    except Exception as e:
        logger.debug("NRI watermark check: %s", e)


def _run_content_enrichment(batch: int) -> int:
    from services.article_content_enrichment_service import enrich_articles_batch

    return int(enrich_articles_batch(batch_size=batch) or 0)


def _run_context_sync(limit: int) -> int:
    from services.context_processor_service import sync_domain_articles_to_contexts
    from shared.domain_registry import get_pipeline_active_domain_keys

    total = 0
    for dk in get_pipeline_active_domain_keys():
        total += int(sync_domain_articles_to_contexts(dk, limit=limit) or 0)
    return total


async def _run_entity_extraction(domains: list[str] | None, max_articles: int, parallel: int) -> dict:
    import importlib.util

    from shared.bulk_catchup_llm_routing import bulk_dual_lane_catchup_active, create_lane_semaphores
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    spec = importlib.util.spec_from_file_location(
        "run_entity_extraction_catchup",
        Path(__file__).resolve().parents[1] / "_archived" / "scripts" / "run_entity_extraction_catchup.py",
    )
    assert spec and spec.loader
    rec = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rec)

    keys = domains or list(get_pipeline_active_domain_keys())
    per_domain = max(50, max_articles // max(len(keys), 1))
    gpu_sem, cpu_sem, sem, gpu_p, cpu_p, dual = create_lane_semaphores(parallel=parallel)

    batches: list[tuple[str, str, list]] = []
    offset = 0
    for dk in keys:
        schema = resolve_domain_schema(dk)
        rows = rec._fetch_batch(schema, limit=per_domain)
        if rows:
            batches.append((dk, schema, rows))
            offset += len(rows)

    if dual:
        logger.info(
            "entity_extraction dual-lane: PopOS gpu=%s + Widow local=%s, %s domains in parallel",
            gpu_p,
            cpu_p,
            len(batches),
        )

    async def _domain_batch(i: int, dk: str, schema: str, rows: list) -> dict:
        row_offset = sum(len(b[2]) for b in batches[:i])
        return await rec._extract_batch(
            dk,
            schema,
            rows,
            parallel=parallel,
            gpu_sem=gpu_sem,
            cpu_sem=cpu_sem,
            sem=sem,
            lane_index_offset=row_offset,
        )

    results = await asyncio.gather(
        *[_domain_batch(i, dk, schema, rows) for i, (dk, schema, rows) in enumerate(batches)]
    )
    stats: dict = {"ok": 0, "fail": 0}
    lane_totals = {"gpu": 0, "cpu": 0}
    for r in results:
        stats["ok"] += r.get("ok", 0)
        stats["fail"] += r.get("fail", 0)
        for lane, n in (r.get("lane_articles") or {}).items():
            lane_totals[lane] = lane_totals.get(lane, 0) + n
    if dual and lane_totals:
        stats["lane_articles"] = lane_totals
    stats["dual_lane"] = bulk_dual_lane_catchup_active()
    return stats


def _run_claim_extraction(limit: int) -> int:
    from services.claim_extraction_service import drain_claim_extraction_for_automation_task

    async def _drain():
        total, _batches = await drain_claim_extraction_for_automation_task(nightly_limit=limit)
        return total

    return asyncio.run(_drain())


def _run_event_tracking(limit: int) -> int:
    from services.event_tracking_service import discover_events_from_contexts

    async def _go():
        r = await discover_events_from_contexts(domain_key=None, limit=limit)
        return int(r.get("events_created") or 0) if isinstance(r, dict) else 0

    return asyncio.run(_go())


def _run_embeddings(batch: int) -> int:
    from services.embeddings_worker_service import run_embeddings_worker_batch

    return int(run_embeddings_worker_batch(limit=batch) or 0)


def _run_storyline_discovery(domain: str) -> int:
    from services.ai_storyline_discovery import get_discovery_service

    svc = get_discovery_service()
    r = svc.discover_storylines(domain=domain, hours=None, save_to_db=True)
    return len(r.get("saved_storylines") or [])


def _run_topic_clustering() -> int:
    """Best-effort single pass — automation owns steady-state clustering."""
    return 0


def _run_metadata_enrichment(limit_per_domain: int) -> int:
    from shared.legacy_intake_rollback import (
        legacy_intake_rollback_active,
        load_metadata_enrichment_service,
    )

    if not legacy_intake_rollback_active():
        logger.warning(
            "metadata_enrichment requires LEGACY_INTAKE_EXTRACTION_ENABLED=true; use unified_intake_extraction"
        )
        return 0
    mod = load_metadata_enrichment_service()
    return int(asyncio.run(mod.run_metadata_enrichment_batch_for_domains(limit_per_domain=limit_per_domain)) or 0)


def _execute_phase(phase: str, args: argparse.Namespace) -> dict:
    if phase == "content_enrichment":
        n = _run_content_enrichment(args.enrich_batch)
        return {"processed": n}
    if phase == "metadata_enrichment":
        n = _run_metadata_enrichment(args.metadata_limit)
        return {"processed": n}
    if phase == "context_sync":
        n = _run_context_sync(args.context_sync_limit)
        return {"processed": n}
    if phase == "unified_intake_extraction":
        from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

        result = asyncio.run(run_unified_intake_extraction_batch_drain(budget_seconds=0))
        return {"processed": int(result.get("articles_processed") or 0)}
    if phase == "spine_sql_tail":
        from services.spine_sql_tail_service import run_spine_sql_tail_drain

        result = asyncio.run(run_spine_sql_tail_drain(budget_seconds=0))
        return dict(result)
    if phase == "entity_extraction":
        from shared.pipeline_resource_policy import intake_extraction_suppressed

        if intake_extraction_suppressed():
            from shared.unified_intake_extraction_runner import run_unified_intake_extraction_batch_drain

            result = asyncio.run(run_unified_intake_extraction_batch_drain())
            return {
                "processed": int(result.get("articles_processed") or 0),
                "unified_intake": True,
            }
        stats = asyncio.run(
            _run_entity_extraction(args.domains, args.entity_max, args.parallel)
        )
        return stats
    if phase == "claim_extraction":
        n = _run_claim_extraction(args.claim_limit)
        return {"processed": n}
    if phase == "event_tracking":
        n = _run_event_tracking(args.event_limit)
        return {"processed": n}
    if phase == "embeddings_worker":
        n = _run_embeddings(args.embed_batch)
        return {"processed": n}
    if phase == "storyline_discovery":
        total = 0
        from shared.domain_registry import get_pipeline_active_domain_keys

        for dk in get_pipeline_active_domain_keys():
            total += _run_storyline_discovery(dk)
        return {"processed": total}
    if phase == "topic_clustering":
        return {"processed": _run_topic_clustering(), "skipped": True}
    return {"error": "unknown_phase"}


def main() -> int:
    _load_env()
    from shared.bulk_catchup_pause import clear_pause_marker, write_pause_marker

    write_pause_marker(reason="bulk_catchup.py")
    parser = argparse.ArgumentParser(description="Bulk pipeline catch-up (one-time operator job)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore quiet hours (one-time exception)")
    parser.add_argument("--phase", choices=BULK_PHASE_ORDER, default=None)
    parser.add_argument("--loops", type=int, default=50, help="Max loops per phase")
    parser.add_argument("--enrich-batch", type=int, default=int(env_str("BULK_ENRICH_BATCH", "120")))
    parser.add_argument(
        "--metadata-limit",
        type=int,
        default=int(env_str("BULK_METADATA_LIMIT_PER_DOMAIN", "40")),
        help="Articles per domain schema per metadata_enrichment loop",
    )
    parser.add_argument("--context-sync-limit", type=int, default=int(env_str("BULK_CONTEXT_SYNC_LIMIT", "500")))
    parser.add_argument("--entity-max", type=int, default=int(env_str("BULK_ENTITY_EXTRACTION_PER_DOMAIN", "500")))
    parser.add_argument("--claim-limit", type=int, default=int(env_str("BULK_CLAIM_LIMIT", "500")))
    parser.add_argument("--event-limit", type=int, default=int(env_str("BULK_EVENT_LIMIT", "300")))
    parser.add_argument("--embed-batch", type=int, default=int(env_str("BULK_EMBED_BATCH", "200")))
    parser.add_argument(
        "--parallel",
        type=int,
        default=int(env_str("BULK_ENTITY_PARALLEL", env_str("BULK_GPU_PARALLEL", "3"))),
        help="PopOS GPU lane concurrency per domain (default 4 with dual-lane catch-up)",
    )
    parser.add_argument(
        "--cpu-parallel",
        type=int,
        default=int(env_str("BULK_CPU_PARALLEL", "2")),
        help="Widow local CPU-lane concurrency per domain (default 2; match OLLAMA_NUM_PARALLEL)",
    )
    parser.add_argument(
        "--ollama-timeout",
        type=int,
        default=int(env_str("BULK_OLLAMA_TIMEOUT", "600")),
        help="HTTP timeout (seconds) for remote GPU lane during catch-up (default 600)",
    )
    parser.add_argument(
        "--use-popos-gpu",
        action=argparse.BooleanOptionalAction,
        default=env_str("BULK_USE_POPOS_GPU", "true").lower() in ("1", "true", "yes"),
        help="Route GPU lane to PopOS RTX 5090 (OLLAMA_POP_OS_HOST)",
    )
    parser.add_argument(
        "--dual-lane",
        action=argparse.BooleanOptionalAction,
        default=env_str("BULK_DUAL_LANE_CATCHUP", "true").lower() in ("1", "true", "yes"),
        help="Use PopOS GPU + Widow local CPU in parallel during catch-up (default on)",
    )
    parser.add_argument("--domains", nargs="*", default=None)
    parser.add_argument("--floor", type=int, default=int(env_str("BULK_STEADY_STATE_FLOOR", "50")))
    parser.add_argument(
        "--skip-phases",
        nargs="*",
        default=None,
        help="Phases to skip (e.g. content_enrichment context_sync)",
    )
    parser.add_argument(
        "--stall-loops",
        type=int,
        default=int(env_str("BULK_STALL_LOOPS", "5")),
        help="Skip phase after N loops with zero processed and unchanged pending",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        return _run_bulk_catchup(args)
    finally:
        clear_pause_marker()
        env_pop("BULK_CATCHUP_ACTIVE", None)


def _run_bulk_catchup(args: argparse.Namespace) -> int:
    if not _schedule_allowed(args.force):
        print("Outside allowed schedule window. Use --force for one-time bulk catch-up.", file=sys.stderr)
        return 2

    env_set("BULK_CATCHUP_ACTIVE", "1")
    from config.catchup_defaults import apply_catchup_env_defaults

    apply_catchup_env_defaults(bulk_active=True)
    from shared.bulk_catchup_llm_routing import configure_catchup_extraction_routing

    configure_catchup_extraction_routing(
        use_popos_gpu=args.use_popos_gpu,
        dual_lane=args.dual_lane and args.use_popos_gpu,
        gpu_parallel=max(1, args.parallel),
        cpu_parallel=max(1, args.cpu_parallel),
        ollama_timeout=max(120, args.ollama_timeout),
    )

    skip_phases = frozenset(args.skip_phases or [])
    env_skip = env_str("BULK_SKIP_PHASES", "").strip()
    if env_skip:
        skip_phases = skip_phases | frozenset(p.strip() for p in env_skip.split(",") if p.strip())
    phases = [args.phase] if args.phase else [p for p in BULK_PHASE_ORDER if p not in skip_phases]
    state = _load_checkpoint()
    if not state.get("started_at"):
        state["started_at"] = datetime.now(timezone.utc).isoformat()

    print("=== Bulk catch-up ===")
    for phase in phases:
        pending = _queue_depth_for_phase(phase)
        print(_format_phase_queue_line(phase, pending))
        if args.dry_run:
            continue
        if pending <= args.floor and phase not in ("embeddings_worker",):
            state["phases"][phase] = {"status": "skipped_floor", "pending": pending}
            _save_checkpoint(state)
            continue

        state["current_phase"] = phase
        _save_checkpoint(state)
        loops = 0
        stall_count = 0
        last_pending = pending
        while loops < args.loops:
            pending = _queue_depth_for_phase(phase)
            if pending <= args.floor:
                break
            loops += 1
            print(f"  {phase} loop {loops} queue_depth={pending}")
            try:
                result = _execute_phase(phase, args)
                print(f"    result: {result}")
                processed = int(
                    result.get("processed")
                    or result.get("ok")
                    or 0
                )
                if processed == 0 and pending >= last_pending and args.stall_loops > 0:
                    stall_count += 1
                    if stall_count >= args.stall_loops:
                        logger.warning(
                            "bulk %s: no progress for %s loops (pending=%s) — skipping phase",
                            phase,
                            stall_count,
                            pending,
                        )
                        state["phases"][phase] = {
                            "status": "skipped_stall",
                            "pending": pending,
                            "loops": loops,
                        }
                        _save_checkpoint(state)
                        break
                else:
                    stall_count = 0
                last_pending = pending
            except Exception as e:
                logger.exception("bulk %s failed: %s", phase, e)
                state["phases"][phase] = {"status": "error", "error": str(e)[:200]}
                _save_checkpoint(state)
                break
            state["phases"][phase] = {
                "status": "running",
                "loops": loops,
                "last_pending": pending,
                "last_result": result,
            }
            _save_checkpoint(state)
            pause = float(env_str("BULK_NRI_MENTION_BATCH_PAUSE", "2"))
            time.sleep(pause)
            if phase == "entity_extraction":
                _log_nri_watermark_lag()

        state["phases"][phase] = {
            "status": "done",
            "loops": loops,
            "pending_after": _queue_depth_for_phase(phase),
        }
        _save_checkpoint(state)

    state["current_phase"] = None
    state["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_checkpoint(state)
    print(f"Checkpoint: {CHECKPOINT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
