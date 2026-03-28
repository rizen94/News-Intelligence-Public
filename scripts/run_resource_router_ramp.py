#!/usr/bin/env python3
"""
Apply staged CPU/GPU/DB gateway profiles for hybrid resource routing.

Usage examples (from repo root):
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --list
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step baseline
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step step1 --apply
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step step2 --apply --restart
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step step3 --apply --status-url http://localhost:8000/api/system_monitoring/automation/status
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step step4 --apply --restart
  PYTHONPATH=api uv run python scripts/run_resource_router_ramp.py --step step5 --apply --restart
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

_ENV_LINE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# Staged profiles: conservative -> aggressive.
PROFILES: dict[str, Dict[str, str]] = {
    "baseline": {
        "AUTOMATION_DYNAMIC_RESOURCE_ROUTING_ENABLED": "true",
        "MAX_CONCURRENT_OLLAMA_TASKS": "12",
        "AUTOMATION_MAX_CONCURRENT_TASKS": "12",
        "AUTOMATION_EXECUTOR_MAX_WORKERS": "6",
        "OLLAMA_DUAL_HOST_ROUTING_ENABLED": "true",
        "OLLAMA_CPU_CONCURRENCY": "6",
        "OLLAMA_GPU_CONCURRENCY": "6",
        "AUTOMATION_ROUTER_GPU_SATURATED_HEADROOM": "0.15",
        "AUTOMATION_ROUTER_GPU_EXTRA_HEADROOM": "0.55",
        "AUTOMATION_ROUTER_CPU_HOT_HEADROOM": "0.20",
        "AUTOMATION_ROUTER_CPU_EXTRA_HEADROOM": "0.55",
        "AUTOMATION_ROUTER_DB_PRESSURE_HEADROOM": "0.20",
        "AUTOMATION_ROUTER_DB_EXTRA_HEADROOM": "0.65",
    },
    "step1": {
        # Allow more GPU work first.
        "MAX_CONCURRENT_OLLAMA_TASKS": "14",
        "OLLAMA_GPU_CONCURRENCY": "8",
        "AUTOMATION_ROUTER_GPU_EXTRA_HEADROOM": "0.45",
    },
    "step2": {
        # Then open CPU lane.
        "AUTOMATION_MAX_CONCURRENT_TASKS": "14",
        "AUTOMATION_EXECUTOR_MAX_WORKERS": "8",
        "OLLAMA_CPU_CONCURRENCY": "8",
        "AUTOMATION_ROUTER_CPU_EXTRA_HEADROOM": "0.45",
    },
    "step3": {
        # Finally permit more DB-heavy progression.
        "AUTOMATION_MAX_CONCURRENT_TASKS": "16",
        "AUTOMATION_EXECUTOR_MAX_WORKERS": "10",
        "AUTOMATION_ROUTER_DB_PRESSURE_HEADROOM": "0.15",
        "AUTOMATION_ROUTER_DB_EXTRA_HEADROOM": "0.55",
    },
    "step4": {
        # Optional max ramp: all lanes + allocator slightly tighter (more eager scheduling).
        "MAX_CONCURRENT_OLLAMA_TASKS": "18",
        "OLLAMA_GPU_CONCURRENCY": "10",
        "OLLAMA_CPU_CONCURRENCY": "10",
        "AUTOMATION_MAX_CONCURRENT_TASKS": "18",
        "AUTOMATION_EXECUTOR_MAX_WORKERS": "12",
        "AUTOMATION_ROUTER_GPU_EXTRA_HEADROOM": "0.40",
        "AUTOMATION_ROUTER_CPU_EXTRA_HEADROOM": "0.40",
        "AUTOMATION_ROUTER_DB_PRESSURE_HEADROOM": "0.12",
        "AUTOMATION_ROUTER_DB_EXTRA_HEADROOM": "0.50",
    },
    "step5": {
        # CPU emphasis: more CPU-lane Ollama concurrency + workers; GPU concurrency unchanged from step4.
        # Router: harder to spill cpu_light → gpu (raise GPU bar, require hotter CPU before spill).
        "OLLAMA_CPU_CONCURRENCY": "16",
        "MAX_CONCURRENT_OLLAMA_TASKS": "24",
        "AUTOMATION_MAX_CONCURRENT_TASKS": "24",
        "AUTOMATION_EXECUTOR_MAX_WORKERS": "16",
        "AUTOMATION_ROUTER_GPU_EXTRA_HEADROOM": "0.52",
        "AUTOMATION_ROUTER_CPU_HOT_HEADROOM": "0.14",
        # Scheduling + throughput (matches code defaults / env hints)
        "AUTOMATION_SCHEDULER_TICK_SECONDS": "3",
        "AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS": "6",
        "WORKLOAD_BALANCER_ENABLED": "false",
        "AUTOMATION_DISABLE_DYNAMIC_TASK_SCALING": "true",
        "EVENT_EXTRACTION_PARALLEL": "8",
        "CLAIM_EXTRACTION_BATCH_LIMIT": "4000",
        "CLAIM_EXTRACTION_PARALLEL": "48",
        "DB_POOL_WORKER_MAX": "28",
        "AUTOMATION_ROUTER_COOLDOWN_MULT_DB_PRESSURE": "2.0",
        "AUTOMATION_ROUTER_COOLDOWN_MULT_GPU_SATURATED": "1.5",
        "AUTOMATION_ROUTER_COOLDOWN_MULT_CPU_HOT": "1.3",
        "AUTOMATION_ROUTER_COOLDOWN_MULT_HEADROOM": "0.85",
    },
}

PROFILE_ORDER = ("baseline", "step1", "step2", "step3", "step4", "step5")


def _load_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _apply_env_updates(lines: list[str], updates: Dict[str, str]) -> list[str]:
    out = list(lines)
    seen: set[str] = set()
    for i, line in enumerate(out):
        m = _ENV_LINE_RE.match(line.strip())
        if not m:
            continue
        key = m.group(1)
        if key in updates:
            out[i] = f"{key}={updates[key]}"
            seen.add(key)
    missing = [k for k in updates.keys() if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# Added by scripts/run_resource_router_ramp.py")
        for key in missing:
            out.append(f"{key}={updates[key]}")
    return out


def _merge_profiles(target: str) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for name in PROFILE_ORDER:
        merged.update(PROFILES[name])
        if name == target:
            break
    return merged


def _print_profile(name: str, updates: Dict[str, str]) -> None:
    print(f"\nProfile: {name}")
    print("-" * (9 + len(name)))
    for k in sorted(updates.keys()):
        print(f"{k}={updates[k]}")


def _restart_services() -> int:
    restart_script = ROOT / "restart_system.sh"
    if not restart_script.exists():
        print("restart_system.sh not found; skipping restart", file=sys.stderr)
        return 1
    print("\nRestarting services via restart_system.sh ...")
    result = subprocess.run(["bash", str(restart_script)], cwd=str(ROOT))
    return int(result.returncode)


def _print_status(url: str) -> int:
    print(f"\nFetching status: {url}")
    try:
        with urlopen(url, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except URLError as e:
        print(f"Status fetch failed: {e}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print("Status response was not JSON", file=sys.stderr)
        return 1

    data = payload.get("data") or {}
    router = data.get("resource_router") or {}
    headroom = router.get("headroom") or {}
    queued = data.get("queued_tasks_by_lane") or {}
    active = data.get("active_tasks_by_lane") or {}
    runs = data.get("runs_last_60m_by_lane") or {}

    print("Resource router:")
    print(f"  enabled: {router.get('enabled')}")
    print(f"  cpu_percent: {headroom.get('cpu_percent')}")
    print(f"  gpu_percent: {headroom.get('gpu_percent')}")
    print(f"  cpu_headroom: {headroom.get('cpu_headroom')}")
    print(f"  gpu_headroom: {headroom.get('gpu_headroom')}")
    print(f"  db_headroom: {headroom.get('db_headroom')}")
    print(f"  queued cpu/gpu: {queued.get('cpu', 0)}/{queued.get('gpu', 0)}")
    print(f"  active cpu/gpu: {active.get('cpu', 0)}/{active.get('gpu', 0)}")
    print(f"  runs60m cpu/gpu: {runs.get('cpu', 0)}/{runs.get('gpu', 0)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply staged resource-router ramp profiles")
    ap.add_argument(
        "--step",
        choices=PROFILE_ORDER,
        default="baseline",
        help="Profile step to apply (default: baseline)",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="Show all profiles and exit",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to .env (default: dry-run)",
    )
    ap.add_argument(
        "--restart",
        action="store_true",
        help="Restart services after apply (runs restart_system.sh)",
    )
    ap.add_argument(
        "--status-url",
        default="",
        help="Optional automation status URL to print lane/headroom snapshot",
    )
    args = ap.parse_args()

    if args.list:
        for step in PROFILE_ORDER:
            _print_profile(step, PROFILES[step])
        return 0

    merged = _merge_profiles(args.step)
    _print_profile(args.step, merged)
    print(
        "\nStep guidance: run each step for ~20-30 min, then check CPU/GPU utilization, "
        "DB pool pressure, queue depth, and failures before continuing."
    )

    lines = _load_env_lines(ENV_PATH)
    new_lines = _apply_env_updates(lines, merged)

    if not args.apply:
        print("\nDry-run only (no file changes). Re-run with --apply to write .env.")
        return 0

    if ENV_PATH.exists():
        backup = ENV_PATH.with_suffix(".env.backup")
        shutil.copyfile(ENV_PATH, backup)
        print(f"\nBacked up .env -> {backup}")

    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"Updated {ENV_PATH}")

    if args.restart:
        rc = _restart_services()
        if rc != 0:
            return rc

    if args.status_url:
        return _print_status(args.status_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

