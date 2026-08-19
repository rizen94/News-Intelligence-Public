#!/usr/bin/env python3
"""Continuous AutomationManager / backlog sampler for overnight watch.

Writes a human-readable summary + NDJSON sidecar until killed (SIGTERM/SIGINT).

Usage:
  python3 scripts/scheduler_backlog_watch.py --interval 300 \\
    --log logs/scheduler_backlog_watch.log \\
    --api http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_STOP = False


def _handle_stop(signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True
    print(f"stop signal {signum}", flush=True)


def _get_json(url: str, timeout: float = 45.0) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _phase_rows(progress: dict[str, Any]) -> list[dict[str, Any]]:
    data = progress.get("data") or progress
    rows = data.get("phase_dashboard") or []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("phase") or row.get("name") or row.get("phase_key")
        if not name:
            continue
        qd = row.get("queue_depth")
        if qd is None:
            qd = row.get("pending_records")
        try:
            qd_i = int(qd or 0)
        except (TypeError, ValueError):
            qd_i = 0
        out.append(
            {
                "phase": str(name),
                "queue_depth": qd_i,
                "scheduling_backlog": row.get("scheduling_backlog"),
                "runs_1h": row.get("runs_1h"),
                "runs_24h": row.get("runs_24h"),
                "queue_stale": bool(row.get("queue_stale")),
                "scheduling_status": row.get("scheduling_status"),
                "rows_per_run": row.get("rows_per_run"),
            }
        )
    return out


def _sample(api: str) -> dict[str, Any]:
    base = api.rstrip("/")
    auto = _get_json(f"{base}/api/system_monitoring/automation/status")
    prog = _get_json(
        f"{base}/api/system_monitoring/processing_progress"
        "?include_pending_metrics=false&use_backlog_snapshot=true"
    )
    runs = _get_json(f"{base}/api/system_monitoring/process_run_summary?hours=6")

    a = auto.get("data") or auto
    p = prog.get("data") or prog
    r = runs.get("data") or runs
    pc = a.get("pipeline_controller") or {}
    popos = a.get("popos_phase_worker") or {}
    remote = list(a.get("remote_owned_phases") or [])
    disabled = list(a.get("disabled_schedules") or [])
    phases = _phase_rows(prog)

    stale = [x for x in phases if x.get("queue_stale") and x["queue_depth"] > 0]
    backlog = [x for x in phases if x["queue_depth"] > 0]
    backlog.sort(key=lambda x: x["queue_depth"], reverse=True)

    # Starved = backlog + not remote-owned + no recent Widow runs (queue_stale)
    remote_set = set(remote)
    starved = [
        x
        for x in stale
        if x["phase"] not in remote_set
        and (x.get("scheduling_status") or "active") == "active"
    ]
    remote_backlog = [x for x in backlog if x["phase"] in remote_set]

    enqueue = [
        x
        for x in (pc.get("queue_actions_last_replan") or [])
        if isinstance(x, str) and x.startswith("enqueue:")
    ]
    drops = [
        x
        for x in (pc.get("queue_actions_last_replan") or [])
        if isinstance(x, str) and x.startswith("drop_")
    ]

    uib = p.get("unified_intake_breakdown") or {}
    signal = p.get("signal_lane_metrics") or {}

    return {
        "ts_utc": _utc_now(),
        "automation_running": bool(a.get("is_running")),
        "catchup_active": pc.get("catchup_active"),
        "tree_branch": pc.get("last_tree_branch"),
        "plan_generation": pc.get("plan_generation"),
        "enqueue": enqueue,
        "drops": drops,
        "stalled_phases": pc.get("stalled_phases") or [],
        "remote_owned_phases": remote,
        "disabled_schedules": disabled,
        "popos_worker": {
            "alive": popos.get("alive"),
            "age_sec": popos.get("age_sec"),
            "cycle": popos.get("cycle"),
            "phases": popos.get("phases"),
        },
        "unified_intake": {
            "actionable": uib.get("actionable_unified_intake"),
            "inventory_missing_pass": uib.get("inventory_missing_pass"),
            "spine_queue_depth": uib.get("spine_queue_depth"),
        },
        "signal_lane": signal,
        "intake_first_pass_sum": p.get("intake_first_pass_sum"),
        "phases_with_backlog": backlog[:40],
        "starved_phases": starved,
        "remote_backlog_phases": remote_backlog[:20],
        "phases_run_recently": [
            {
                "name": x.get("name") or x.get("phase"),
                "last_run": x.get("last_run"),
            }
            for x in (r.get("phases_run_recently") or [])[:30]
            if isinstance(x, dict)
        ],
        "phases_not_run_recently": [
            x.get("name") or x.get("phase")
            for x in (r.get("phases_not_run_recently") or [])[:40]
            if isinstance(x, dict)
        ],
    }


def _format_human(s: dict[str, Any]) -> str:
    lines = [
        f"===== {_utc_now()} =====",
        f"automation_running={s.get('automation_running')} catchup={s.get('catchup_active')} "
        f"branch={s.get('tree_branch')} plan_gen={s.get('plan_generation')}",
        f"popos_worker alive={s['popos_worker'].get('alive')} age_sec={s['popos_worker'].get('age_sec')} "
        f"cycle={s['popos_worker'].get('cycle')}",
        f"enqueue={s.get('enqueue')}",
        f"drops={s.get('drops')}",
        f"stalled={s.get('stalled_phases')}",
        f"unified_intake={s.get('unified_intake')} signal={s.get('signal_lane')} "
        f"intake_first_pass_sum={s.get('intake_first_pass_sum')}",
    ]
    starved = s.get("starved_phases") or []
    if starved:
        lines.append("STARVED (backlog + queue_stale, not remote-owned):")
        for x in starved:
            lines.append(
                f"  ! {x['phase']}: depth={x['queue_depth']} "
                f"runs_1h={x.get('runs_1h')} runs_24h={x.get('runs_24h')}"
            )
    else:
        lines.append("STARVED: none")

    backlog = s.get("phases_with_backlog") or []
    lines.append(f"BACKLOG phases ({len(backlog)} shown, top by depth):")
    for x in backlog[:25]:
        tag = "remote" if x["phase"] in set(s.get("remote_owned_phases") or []) else "local"
        stale = " stale" if x.get("queue_stale") else ""
        lines.append(
            f"  - [{tag}{stale}] {x['phase']}: depth={x['queue_depth']} "
            f"runs_1h={x.get('runs_1h')} runs_24h={x.get('runs_24h')} "
            f"status={x.get('scheduling_status')}"
        )

    not_run = s.get("phases_not_run_recently") or []
    if not_run:
        lines.append(f"phases_not_run_6h ({len(not_run)}): {', '.join(map(str, not_run[:25]))}")

    recent = s.get("phases_run_recently") or []
    if recent:
        lines.append("recent runs (6h sample):")
        for x in recent[:15]:
            lines.append(f"  + {x.get('name')} last={x.get('last_run')}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--interval", type=int, default=300, help="Seconds between samples")
    ap.add_argument(
        "--log",
        default="logs/scheduler_backlog_watch.log",
        help="Human-readable append log",
    )
    ap.add_argument(
        "--ndjson",
        default="",
        help="Optional NDJSON path (default: <log>.ndjson)",
    )
    ap.add_argument("--once", action="store_true", help="Single sample then exit")
    args = ap.parse_args()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ndjson_path = Path(args.ndjson) if args.ndjson else log_path.with_suffix(".ndjson")

    header = (
        f"# scheduler_backlog_watch started {_utc_now()} "
        f"api={args.api} interval={args.interval}s\n"
        f"# stop: kill $(cat {log_path.with_suffix('.pid')}) or send stop in chat\n\n"
    )
    log_path.write_text(header, encoding="utf-8")
    pid_path = log_path.with_suffix(".pid")
    pid_path.write_text(str(__import__("os").getpid()), encoding="utf-8")

    print(f"logging -> {log_path}", flush=True)
    print(f"ndjson  -> {ndjson_path}", flush=True)
    print(f"pid     -> {pid_path} ({pid_path.read_text().strip()})", flush=True)

    while not _STOP:
        try:
            sample = _sample(args.api)
            human = _format_human(sample)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(human)
            with ndjson_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(sample, default=str) + "\n")
            print(human.splitlines()[0], f"backlog={len(sample.get('phases_with_backlog') or [])} "
                  f"starved={len(sample.get('starved_phases') or [])}", flush=True)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            err = f"===== {_utc_now()} ERROR {exc!r} =====\n"
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(err)
            print(err, flush=True)

        if args.once or _STOP:
            break
        # Sleep in small slices so stop is responsive
        for _ in range(max(1, args.interval)):
            if _STOP:
                break
            time.sleep(1)

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"# stopped {_utc_now()}\n")
    print(f"stopped {_utc_now()}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
