#!/usr/bin/env python3
"""
Full system status: resource usage (CPU, RAM, disk, optional GPU) and data quality (articles, phases, storylines, contexts).
Run from project root: uv run python scripts/full_system_status_check.py
"""
import os
import sys
from datetime import datetime, timezone

# Paths: project root and api for DB/GPU; scripts dir for check_v7_data_collection
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
API = os.path.join(ROOT, "api")
for p in (ROOT, SCRIPTS, API):
    if p not in sys.path:
        sys.path.insert(0, p)

env_path = os.path.join(ROOT, ".env")
if os.path.isfile(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key in ("DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER"):
                    os.environ.setdefault(key, val.strip().strip('"').strip("'"))
if not os.environ.get("DB_PASSWORD") and os.path.isfile(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())

try:
    import psutil
except ImportError:
    psutil = None


def _resource_section():
    """Return list of lines for resource usage (CPU, RAM, disk; GPU if available)."""
    lines = []
    lines.append("--- Resource usage (this host) ---")
    if not psutil:
        lines.append("  psutil not installed; install with: uv add psutil")
        return lines

    # CPU
    try:
        cpu_pct = psutil.cpu_percent(interval=1)
        cpu_per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        lines.append(f"  CPU: {cpu_pct:.1f}% overall ({len(cpu_per_cpu)} cores)")
    except Exception as e:
        lines.append(f"  CPU: error - {e}")

    # RAM
    try:
        v = psutil.virtual_memory()
        lines.append(
            f"  RAM: {v.used / (1024**3):.1f} / {v.total / (1024**3):.1f} GB ({v.percent}%)"
        )
    except Exception as e:
        lines.append(f"  RAM: error - {e}")

    # Disk (root)
    try:
        d = psutil.disk_usage("/")
        lines.append(
            f"  Disk (/): {d.used / (1024**3):.1f} / {d.total / (1024**3):.1f} GB ({d.percent}%)"
        )
    except Exception as e:
        lines.append(f"  Disk: error - {e}")

    # Optional: GPU (ResourceManager from api)
    try:
        from shared.llm.resource_manager import ResourceManager
        rm = ResourceManager()
        snap = rm.monitor()
        gpu = snap["gpu"]
        ram = snap["ram"]
        lines.append("")
        lines.append(f"  GPU: {gpu.get('name', 'N/A')}")
        lines.append(
            f"    VRAM: {gpu.get('vram_used_gb', 0):.1f} / {gpu.get('vram_total_gb', 0):.1f} GB "
            f"(util {gpu.get('utilization_pct', 0):.0f}%, temp {gpu.get('temperature_c', 0):.0f}°C)"
        )
        lines.append(
            f"    RAM (budget): used {ram.get('used_gb', 0):.1f} / total {ram.get('total_gb', 0):.1f} GB, "
            f"budget {ram.get('ram_budget_gb', 0):.1f} GB"
        )
    except Exception as e:
        lines.append("")
        lines.append(f"  GPU: not available ({e})")

    return lines


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print("=" * 60)
    print(f"Full system status — {now}")
    print("=" * 60)

    # 1) Resource usage
    for line in _resource_section():
        print(line)

    # 2) Data quality (reuse v7 check)
    from check_v7_data_collection import get_conn, run_checks
    conn = get_conn()
    if not conn:
        print("")
        print("--- Data quality ---")
        print("  Database: not connected (set DB_* or .db_password_widow)")
    else:
        print("")
        print("--- Data quality ---")
        for line in run_checks(conn):
            print(line)
        conn.close()

    print("")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
