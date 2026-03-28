#!/usr/bin/env python3
"""
Long-run CPU/GPU sampling (what you would watch in htop / nvidia-smi) with a
summary and conservative .env tuning hints for the News Intelligence stack.

Also samples **network**: established TCP connections toward ``DB_HOST:DB_PORT``
(via ``ss``) and, optionally, **PostgreSQL** session counts from ``pg_stat_activity``
(one short query per interval when ``--db-stats`` is set).

htop is interactive and cannot be driven by this script; we use psutil for CPU
and RAM and optional nvidia-smi for GPU utilization.

Examples:
  uv run python scripts/host_resource_watch.py --minutes 45 --interval 5
  uv run python scripts/host_resource_watch.py --minutes 120 --csv .local/host_resource_watch.csv
  uv run python scripts/host_resource_watch.py --minutes 60 --db-stats

See docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md and configs/env.example for the
variables referenced in the recommendations section.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import os
import re
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

try:
    import psycopg2
except ImportError:
    psycopg2 = None


# --- .env bootstrap (same idea as full_system_status_check.py; no api imports) ---

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _load_dotenv_db_keys() -> None:
    env_path = os.path.join(ROOT, ".env")
    if not os.path.isfile(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                if key.startswith("DB_"):
                    os.environ.setdefault(key, val.strip().strip('"').strip("'"))
    if not os.environ.get("DB_PASSWORD") and os.path.isfile(
        os.path.join(ROOT, ".db_password_widow")
    ):
        with open(os.path.join(ROOT, ".db_password_widow"), encoding="utf-8") as f:
            os.environ.setdefault("DB_PASSWORD", f.read().splitlines()[0].strip())


def _db_connect_kwargs_lightweight() -> dict[str, Any]:
    """Minimal kwargs for monitoring queries; avoids importing api connection pools."""
    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    return {
        "host": host,
        "port": port,
        "dbname": os.getenv("DB_NAME", "news_intel"),
        "user": os.getenv("DB_USER", "newsapp"),
        "password": os.getenv("DB_PASSWORD", ""),
        "connect_timeout": 5,
        "options": "-c statement_timeout=5000",
    }


def _resolve_host_to_ip(host: str) -> set[str]:
    """IPs and normalized forms to match ``ss`` peer addresses."""
    out: set[str] = set()
    host = host.strip()
    if not host:
        return out
    out.add(host)
    try:
        if host.startswith("[") and "]" in host:
            inner = host[1 : host.index("]")]
            out.add(inner)
            return out
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        for info in infos:
            ip = info[4][0]
            out.add(ip)
            try:
                ip_obj = ipaddress.ip_address(ip)
                if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
                    out.add(str(ip_obj.ipv4_mapped))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def _parse_ss_peer_address(line: str) -> tuple[str | None, int | None]:
    """
    Parse ``ss -tn`` line; return (peer_host, peer_port) for the remote endpoint.
    """
    line = line.strip()
    if not line or line.startswith("State"):
        return None, None
    parts = line.split()
    if len(parts) < 5:
        return None, None
    peer = parts[-1]
    # peer like 192.168.1.1:5432 or [2001:db8::1]:5432
    if peer.startswith("["):
        m = re.match(r"^\[([^\]]+)\]:(\d+)$", peer)
        if m:
            return m.group(1), int(m.group(2))
        return None, None
    if ":" in peer:
        host_part, _, port_s = peer.rpartition(":")
        if host_part and port_s.isdigit():
            return host_part, int(port_s)
    return None, None


def _count_tcp_established_to_db(db_host: str, db_port: int) -> int | None:
    """
    Count established TCP connections from this host whose **peer** is db_host:db_port.
    Uses ``ss`` (Linux). Returns None if ``ss`` is unavailable.
    """
    try:
        p = subprocess.run(
            ["ss", "-tn", "state", "established"],
            capture_output=True,
            text=True,
            timeout=12,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if p.returncode != 0:
        return None

    want_hosts = _resolve_host_to_ip(db_host)
    count = 0
    for line in p.stdout.splitlines():
        peer_host, peer_port = _parse_ss_peer_address(line)
        if peer_host is None or peer_port is None:
            continue
        if peer_port != db_port:
            continue
        if peer_host in want_hosts:
            count += 1
            continue
        if db_host in ("localhost", "127.0.0.1", "::1") and peer_host in (
            "127.0.0.1",
            "::1",
        ):
            count += 1
    return count


def _pg_stat_sample() -> tuple[int | None, int | None, int | None]:
    """
    Return (sessions_total, sessions_active, max_connections_server) or Nones on failure.
    """
    if not psycopg2:
        return None, None, None
    kw = _db_connect_kwargs_lightweight()
    conn = None
    try:
        conn = psycopg2.connect(**kw)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  (SELECT COUNT(*)::int FROM pg_stat_activity
                   WHERE datname = current_database()),
                  (SELECT COUNT(*)::int FROM pg_stat_activity
                   WHERE datname = current_database() AND state = 'active'),
                  (SELECT setting::int FROM pg_settings WHERE name = 'max_connections')
                """
            )
            row = cur.fetchone()
            if not row:
                return None, None, None
            return int(row[0]), int(row[1]), int(row[2])
    except Exception:
        return None, None, None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _pool_budget_hint() -> tuple[int, int, int, int]:
    """Approximate max psycopg2 + SA slots per process from env (same defaults as connection.py)."""
    ui = int(os.getenv("DB_POOL_UI_MAX", "16"))
    legacy = int(os.getenv("DB_POOL_MAX", "28"))
    worker = int(os.getenv("DB_POOL_WORKER_MAX", str(legacy)))
    health = int(os.getenv("DB_POOL_HEALTH_MAX", "2"))
    sa = int(os.getenv("DB_POOL_SA_SIZE", "3")) + int(os.getenv("DB_POOL_SA_OVERFLOW", "8"))
    return ui, worker, health, sa


def _process_is_stack_relevant(name: str, cmd: str) -> bool:
    """True for Python API, Ollama, Postgres, Node/Vite — avoid false positives."""
    nl = (name or "").lower()
    cl = (cmd or "").lower()
    blob = f"{nl} {cl}"

    # Linux often reports comm as "python3" for systemd Python services — exclude known noise.
    _py_noise = (
        "networkd-dispatcher",
        "fail2ban",
        "execsnoop",
        "unattended-upgrade",
    )
    if any(x in cl for x in _py_noise):
        return False

    if nl.startswith("python") or "/python" in cl or "uvicorn" in blob or "gunicorn" in blob:
        return True
    if "ollama" in blob:
        return True
    if "postgres" in blob or "postmaster" in blob:
        return True
    # Do not use \\bnode\\b on full cmdline — Electron passes node.mojom.* (false positive).
    parts = cl.split()
    if parts:
        base = parts[0].rsplit("/", 1)[-1]
        if base in ("node", "nodejs", "npx"):
            return True
    if "vite" in blob or re.search(r"\bnpm\b", blob):
        return True
    return False


def _top_relevant_processes(limit: int = 8) -> list[tuple[int, str, float, float]]:
    """
    Snapshot: PID, name, CPU%, RSS MB for python/uvicorn/ollama/node/postgres-related.
    """
    if not psutil:
        return []
    # prime CPU counters
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(interval=None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.35)
    rows: list[tuple[int, str, float, float]] = []
    for p in psutil.process_iter(
        ["pid", "name", "cpu_percent", "memory_info", "cmdline"]
    ):
        try:
            info = p.info
            name = info.get("name") or ""
            cmd = " ".join(info.get("cmdline") or [])
            if not _process_is_stack_relevant(name, cmd):
                continue
            cpu = p.cpu_percent(interval=None)
            rss = p.memory_info().rss / (1024 * 1024)
            rows.append((p.pid, name or "?", cpu, rss))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    rows.sort(key=lambda x: x[2], reverse=True)
    return rows[:limit]


@dataclass
class Sample:
    ts: float
    cpu_pct: float | None
    mem_pct: float | None
    load_1: float | None
    gpu_util: float | None
    gpu_mem_pct: float | None
    tcp_to_db: int | None
    pg_sessions: int | None
    pg_active: int | None
    pg_max_conn: int | None


@dataclass
class RunStats:
    cpu: list[float] = field(default_factory=list)
    mem: list[float] = field(default_factory=list)
    load_1: list[float] = field(default_factory=list)
    gpu_util: list[float] = field(default_factory=list)
    gpu_mem_pct: list[float] = field(default_factory=list)
    tcp_to_db: list[int] = field(default_factory=list)
    pg_sessions: list[int] = field(default_factory=list)
    pg_active: list[int] = field(default_factory=list)
    pg_max_conn: int | None = None


def _nvidia_sample() -> tuple[float | None, float | None]:
    """Return (gpu_util_0_100, vram_used_ratio_0_1) or (None, None)."""
    try:
        p = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None, None
    if p.returncode != 0 or not p.stdout.strip():
        return None, None
    line = p.stdout.strip().splitlines()[0]
    parts = [x.strip() for x in line.split(",")]
    if len(parts) < 3:
        return None, None
    try:
        util = float(parts[0])
        used = float(parts[1])
        total = float(parts[2])
        mem_pct = (used / total * 100.0) if total > 0 else None
        return util, mem_pct
    except (ValueError, ZeroDivisionError):
        return None, None


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _collect_one(
    interval_s: float,
    *,
    db_host: str,
    db_port: int,
    db_stats: bool,
) -> Sample:
    cpu = mem = None
    load_1 = None
    if psutil:
        cpu = psutil.cpu_percent(interval=interval_s)
        mem = psutil.virtual_memory().percent
        try:
            load_1 = os.getloadavg()[0]
        except (AttributeError, OSError):
            load_1 = None
    else:
        time.sleep(interval_s)

    gu, gm = _nvidia_sample()
    tcp_n = _count_tcp_established_to_db(db_host, db_port)
    pg_tot = pg_act = pg_mc = None
    if db_stats:
        pg_tot, pg_act, pg_mc = _pg_stat_sample()
    return Sample(
        ts=time.time(),
        cpu_pct=cpu,
        mem_pct=mem,
        load_1=load_1,
        gpu_util=gu,
        gpu_mem_pct=gm,
        tcp_to_db=tcp_n,
        pg_sessions=pg_tot,
        pg_active=pg_act,
        pg_max_conn=pg_mc,
    )


def _recommendations(st: RunStats) -> list[str]:
    """Conservative text lines; operator edits .env manually."""
    out: list[str] = []
    cpu = st.cpu
    gpu_u = [x for x in st.gpu_util if x is not None]
    mem = st.mem
    tcp = [x for x in st.tcp_to_db if x is not None]
    pg_s = [x for x in st.pg_sessions if x is not None]

    ui_m, w_m, h_m, sa_budget = _pool_budget_hint()
    per_proc_cap = ui_m + w_m + h_m + sa_budget
    api_workers = max(1, int(os.getenv("API_WORKERS", "4")))
    rough_tcp_ceiling = api_workers * per_proc_cap

    if tcp:
        tavg = statistics.mean(tcp)
        tp95 = _percentile(sorted(tcp), 95)
        tmax = max(tcp)
        out.append(
            f"TCP established to DB (this host → DB_HOST:DB_PORT): "
            f"mean={tavg:.1f} max={tmax} p95={tp95:.1f} (ss)"
        )
        out.append(
            f"  → Per-process pool budget (env) ≈ {per_proc_cap} "
            f"(UI {ui_m} + worker {w_m} + health {h_m} + SA {sa_budget}); "
            f"~{api_workers} API worker(s) → rough upper bound ~{rough_tcp_ceiling} client sockets if "
            "every pool were full (unusual). PgBouncer: many clients → fewer server sessions."
        )
        if tavg >= max(rough_tcp_ceiling * 0.35, 40.0):
            out.append(
                "  → Elevated TCP use vs pool budget — if you see checkout timeouts, "
                "lower DB_POOL_* MAX or API_WORKERS before raising concurrency elsewhere."
            )

    if pg_s:
        savg = statistics.mean(pg_s)
        sp95 = _percentile(sorted(pg_s), 95)
        out.append(
            f"pg_stat_activity (this database): sessions mean={savg:.1f} p95={sp95:.1f}"
        )
        if st.pg_max_conn:
            out.append(
                f"  → Postgres max_connections={st.pg_max_conn}; "
                f"session count headroom depends on other DBs and roles."
            )
            if savg >= 0.85 * st.pg_max_conn:
                out.append(
                    "  → Approaching max_connections for the cluster — reduce per-process "
                    "pools, fewer worker processes, or raise Postgres/PgBouncer limits after "
                    "reviewing total footprint."
                )

    if cpu:
        avg = statistics.mean(cpu)
        p95 = _percentile(sorted(cpu), 95)
        out.append(
            f"CPU samples: mean={avg:.1f}% p95={p95:.1f}% (over {len(cpu)} intervals)"
        )
        if avg >= 88.0:
            out.append(
                "  → Hot CPU: consider raising AUTOMATION_SCHEDULER_TICK_SECONDS slightly, "
                "or lowering OLLAMA_CPU_CONCURRENCY / AUTOMATION_EXECUTOR_MAX_WORKERS / "
                "AUTOMATION_MAX_CONCURRENT_TASKS (one at a time; measure backlog after)."
            )
        elif avg <= 25.0 and p95 <= 55.0:
            out.append(
                "  → Cool CPU: if backlogs are still large, you may have headroom to "
                "raise CPU-lane concurrency or reduce scheduler tick (verify DB + Ollama first)."
            )

    if mem:
        mavg = statistics.mean(mem)
        if mavg >= 90.0:
            out.append(
                f"RAM mean {mavg:.1f}% — check for runaway processes; avoid raising "
                "in-memory queue sizes or unbounded caches."
            )

    if gpu_u:
        gavg = statistics.mean(gpu_u)
        gp95 = _percentile(sorted(gpu_u), 95)
        out.append(
            f"GPU util samples: mean={gavg:.1f}% p95={gp95:.1f}% (nvidia-smi)"
        )
        if gavg >= 92.0 or gp95 >= 98.0:
            out.append(
                "  → GPU saturated: reduce OLLAMA_GPU_CONCURRENCY or MAX_CONCURRENT_OLLAMA_TASKS "
                "slightly; ensure dual-host routing keeps heavy models on GPU lane only."
            )
        elif gavg <= 15.0 and gp95 <= 35.0:
            out.append(
                "  → GPU mostly idle: if narrative/LLM phases are behind, check GPU lane "
                "routing (OLLAMA_GPU_HOST) and phase backlog; GPU may be idle while CPU is busy."
            )

    if not out:
        out.append("Not enough data for recommendations (need psutil + samples).")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--minutes",
        type=float,
        default=30.0,
        help="Total wall time to sample (default: 30)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Seconds between samples; first CPU reading uses this interval (default: 5)",
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        help="Append one row per sample (creates parent dirs if needed)",
    )
    parser.add_argument(
        "--db-stats",
        action="store_true",
        help="Each interval: query pg_stat_activity + max_connections (needs DB_PASSWORD; adds one short DB round-trip per sample)",
    )
    parser.add_argument(
        "--no-tcp",
        action="store_true",
        help="Skip ss-based TCP counts toward DB_HOST:DB_PORT",
    )
    args = parser.parse_args()

    if not psutil:
        print("psutil is required: uv sync (or uv add psutil)", file=sys.stderr)
        return 1

    _load_dotenv_db_keys()
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))

    total = max(0.0, args.minutes * 60.0)
    interval = max(0.5, args.interval)
    deadline = time.time() + total

    st = RunStats()
    writer: Any = None
    csv_path = args.csv
    if csv_path:
        os.makedirs(os.path.dirname(os.path.abspath(csv_path)) or ".", exist_ok=True)
        new_file = not os.path.isfile(csv_path)
        fh = open(csv_path, "a", newline="", encoding="utf-8")
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(
                [
                    "iso_utc",
                    "cpu_pct",
                    "mem_pct",
                    "load_1",
                    "gpu_util",
                    "gpu_mem_pct",
                    "tcp_established_to_db",
                    "pg_sessions",
                    "pg_active",
                ]
            )

    print(
        f"host_resource_watch — interval={interval}s, until ~{args.minutes:.1f} min"
    )
    print(f"DB endpoint (from env): {db_host}:{db_port}")
    print(
        "TCP to DB: "
        + ("off" if args.no_tcp else "ss peer match")
        + "; pg_stat: "
        + ("on" if args.db_stats else "off")
    )
    print("Ctrl+C to stop early; partial stats will still print.")
    print()

    try:
        while time.time() < deadline:
            s = _collect_one(
                interval,
                db_host=db_host,
                db_port=db_port,
                db_stats=args.db_stats,
            )
            if args.no_tcp:
                s = Sample(
                    ts=s.ts,
                    cpu_pct=s.cpu_pct,
                    mem_pct=s.mem_pct,
                    load_1=s.load_1,
                    gpu_util=s.gpu_util,
                    gpu_mem_pct=s.gpu_mem_pct,
                    tcp_to_db=None,
                    pg_sessions=s.pg_sessions,
                    pg_active=s.pg_active,
                    pg_max_conn=s.pg_max_conn,
                )
            iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if s.cpu_pct is not None:
                st.cpu.append(s.cpu_pct)
            if s.mem_pct is not None:
                st.mem.append(s.mem_pct)
            if s.load_1 is not None:
                st.load_1.append(s.load_1)
            if s.gpu_util is not None:
                st.gpu_util.append(s.gpu_util)
            if s.gpu_mem_pct is not None:
                st.gpu_mem_pct.append(s.gpu_mem_pct)
            if s.tcp_to_db is not None:
                st.tcp_to_db.append(s.tcp_to_db)
            if s.pg_sessions is not None:
                st.pg_sessions.append(s.pg_sessions)
            if s.pg_active is not None:
                st.pg_active.append(s.pg_active)
            if s.pg_max_conn is not None and st.pg_max_conn is None:
                st.pg_max_conn = s.pg_max_conn

            if writer:
                writer.writerow(
                    [
                        iso,
                        f"{s.cpu_pct:.2f}" if s.cpu_pct is not None else "",
                        f"{s.mem_pct:.2f}" if s.mem_pct is not None else "",
                        f"{s.load_1:.3f}" if s.load_1 is not None else "",
                        f"{s.gpu_util:.1f}" if s.gpu_util is not None else "",
                        f"{s.gpu_mem_pct:.1f}" if s.gpu_mem_pct is not None else "",
                        str(s.tcp_to_db) if s.tcp_to_db is not None else "",
                        str(s.pg_sessions) if s.pg_sessions is not None else "",
                        str(s.pg_active) if s.pg_active is not None else "",
                    ]
                )
                fh.flush()
    except KeyboardInterrupt:
        print("\n(interrupted)")

    if writer:
        fh.close()
        print(f"Wrote CSV: {csv_path}")

    print()
    print("--- Processes (python / uvicorn / ollama / node / postgres — by CPU) ---")
    procs = _top_relevant_processes(12)
    if procs:
        for pid, name, cpu, rss in procs:
            short = (name or "?")[:40]
            print(f"  pid={pid:<6} {short:<40} cpu={cpu:5.1f}%  rss={rss:7.0f} MB")
    else:
        print("  (none matched or psutil unavailable)")

    print()
    print("--- Summary ---")
    for line in _recommendations(st):
        print(line)

    print()
    print("Next steps: edit .env on the API/automation host, restart workers, then")
    print("  PYTHONPATH=api uv run python scripts/automation_run_analysis.py --hours 24")
    print("  GET /api/system_monitoring/backlog_status")
    return 0


if __name__ == "__main__":
    sys.exit(main())
