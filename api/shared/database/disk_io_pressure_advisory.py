"""
Cross-process disk IO pressure advisory (single-row table + /run JSON).

Widow root is a USB HDD; concurrent apt + Postgres writes can abort ext4 journal.
This module samples the root block device, writes a tmpfs snapshot for apt (before API),
and upserts ``public.disk_io_pressure_advisory`` for AutomationManager / remote readers.

Fail-open when samples are missing or stale.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_LAST_PUBLISH_MONO = 0.0
_LAST_PUBLISH_SIGNATURE: Optional[tuple] = None

_RUN_DIR = Path(os.getenv("DISK_IO_PRESSURE_RUN_DIR", "/run/news-intelligence"))
_RUN_JSON = Path(
    os.getenv(
        "DISK_IO_PRESSURE_RUN_PATH",
        str(_RUN_DIR / "disk_io_pressure.json"),
    )
)
_STATE_JSON = Path(
    os.getenv(
        "DISK_IO_PRESSURE_STATE_PATH",
        str(_RUN_DIR / "disk_io_sample_state.json"),
    )
)


def _util_threshold() -> float:
    try:
        return float(os.getenv("DISK_IO_UTIL_DEFER_THRESHOLD", "85"))
    except ValueError:
        return 85.0


def _write_kb_s_threshold() -> float:
    """Default 8 MB/s = 8192 KB/s — apt / heavy maintenance gate."""
    try:
        return float(os.getenv("DISK_IO_WRITE_KB_S_DEFER_THRESHOLD", "8192"))
    except ValueError:
        return 8192.0


def _automation_write_floor_kb_s() -> float:
    """
    Automation defer needs util-hot *and* at least this write rate
    (unless saturation util is hit — see ``_saturation_util_threshold``).

    Mild USB util spikes with low throughput should not freeze the scheduler.
    Apt still uses the util/heavy-write gate (``defer_heavy_writes``).
    """
    try:
        return float(os.getenv("DISK_IO_AUTOMATION_WRITE_FLOOR_KB_S", "2048"))
    except ValueError:
        return 2048.0


def _saturation_util_threshold() -> float:
    """
    Sustained util at/above this pegs USB even at low KB/s — defer automation.

    Default 95%: distinguishes "busy disk" from "saturated disk".
    """
    try:
        return float(os.getenv("DISK_IO_SATURATION_UTIL_THRESHOLD", "95"))
    except ValueError:
        return 95.0


def _hot_window_sec() -> float:
    # Default 45s so the 15s governor timer keeps 2–3 samples for averaging.
    try:
        return max(5.0, float(os.getenv("DISK_IO_HOT_WINDOW_SEC", "45")))
    except ValueError:
        return 45.0


def _stale_sec() -> float:
    try:
        return max(15.0, float(os.getenv("DISK_IO_PRESSURE_ADVISORY_STALE_SEC", "120")))
    except ValueError:
        return 120.0


def _min_publish_interval_sec() -> float:
    try:
        return max(0.5, float(os.getenv("DISK_IO_PRESSURE_ADVISORY_PUBLISH_INTERVAL_SEC", "5")))
    except ValueError:
        return 5.0


def _sample_interval_sec() -> float:
    try:
        return max(0.5, float(os.getenv("DISK_IO_SAMPLE_INTERVAL_SEC", "2")))
    except ValueError:
        return 2.0


def resolve_root_block_device() -> str:
    """Return kernel disk name for ``/`` (e.g. ``sdc``), overridable via env."""
    override = (os.getenv("DISK_IO_GOVERNOR_DEVICE") or "").strip()
    if override:
        return override.removeprefix("/dev/")
    try:
        with open("/proc/self/mountinfo", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 5:
                    continue
                mount_point = parts[4]
                if mount_point != "/":
                    continue
                # mountinfo: ... major:minor ...
                majmin = parts[2]
                break
            else:
                return "sdc"
        with open("/proc/partitions", "r", encoding="utf-8") as fh:
            next(fh, None)
            next(fh, None)
            for line in fh:
                cols = line.split()
                if len(cols) < 4:
                    continue
                major, minor, _blocks, name = cols[0], cols[1], cols[2], cols[3]
                if f"{major}:{minor}" == majmin:
                    # Prefer whole disk (sdc) over partition (sdc1)
                    base = name.rstrip("0123456789")
                    return base or name
    except Exception as e:
        logger.debug("resolve_root_block_device failed: %s", e)
    return "sdc"


def _read_diskstats(device: str) -> Optional[dict[str, int]]:
    """Parse one /proc/diskstats row for ``device``."""
    try:
        with open("/proc/diskstats", "r", encoding="utf-8") as fh:
            for line in fh:
                cols = line.split()
                if len(cols) < 14:
                    continue
                if cols[2] != device:
                    continue
                # https://www.kernel.org/doc/Documentation/ABI/testing/procfs-diskstats
                return {
                    "reads_completed": int(cols[3]),
                    "sectors_read": int(cols[5]),
                    "writes_completed": int(cols[7]),
                    "sectors_written": int(cols[9]),
                    "io_ticks": int(cols[12]),  # ms spent doing IO
                    "time_in_queue": int(cols[13]),
                }
    except Exception as e:
        logger.debug("read_diskstats failed: %s", e)
    return None


def _load_state() -> dict[str, Any]:
    try:
        if _STATE_JSON.is_file():
            return json.loads(_STATE_JSON.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        _RUN_DIR.mkdir(parents=True, exist_ok=True)
        _STATE_JSON.write_text(json.dumps(state), encoding="utf-8")
    except Exception as e:
        logger.debug("save disk io state failed: %s", e)


def sample_disk_io(
    *,
    device: Optional[str] = None,
    interval_sec: Optional[float] = None,
) -> dict[str, Any]:
    """
    Two-point sample of disk util %% and write KB/s.

    Uses a short sleep between /proc/diskstats reads (default 2s).
    """
    dev = (device or resolve_root_block_device()).strip()
    wait = _sample_interval_sec() if interval_sec is None else max(0.2, float(interval_sec))
    a = _read_diskstats(dev)
    t0 = time.monotonic()
    time.sleep(wait)
    b = _read_diskstats(dev)
    t1 = time.monotonic()
    elapsed_ms = max(1.0, (t1 - t0) * 1000.0)
    elapsed_s = elapsed_ms / 1000.0
    util_pct = 0.0
    write_kb_s = 0.0
    read_kb_s = 0.0
    if a and b:
        io_ticks = max(0, b["io_ticks"] - a["io_ticks"])
        util_pct = min(100.0, (io_ticks / elapsed_ms) * 100.0)
        sectors_w = max(0, b["sectors_written"] - a["sectors_written"])
        sectors_r = max(0, b["sectors_read"] - a["sectors_read"])
        # 512-byte sectors → KB
        write_kb_s = (sectors_w * 512.0 / 1024.0) / elapsed_s
        read_kb_s = (sectors_r * 512.0 / 1024.0) / elapsed_s
    now = time.time()
    return {
        "device": dev,
        "util_pct": round(util_pct, 2),
        "write_kb_s": round(write_kb_s, 1),
        "read_kb_s": round(read_kb_s, 1),
        "sampled_at": now,
        "interval_sec": round(elapsed_s, 3),
    }


def _update_hot_history(sample: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep recent util samples for the hot-window check."""
    state = _load_state()
    hist = list(state.get("history") or [])
    hist.append(
        {
            "t": float(sample.get("sampled_at") or time.time()),
            "util_pct": float(sample.get("util_pct") or 0.0),
            "write_kb_s": float(sample.get("write_kb_s") or 0.0),
        }
    )
    window = _hot_window_sec()
    cutoff = time.time() - max(window * 2, 30.0)
    hist = [h for h in hist if float(h.get("t") or 0) >= cutoff][-40:]
    state["history"] = hist
    state["last_sample"] = sample
    _save_state(state)
    return hist


def _defer_from_history(
    sample: dict[str, Any],
    hist: list[dict[str, Any]],
) -> tuple[bool, bool, dict[str, Any]]:
    """Return (defer_heavy_writes, defer_new_work, detail)."""
    util_thr = _util_threshold()
    write_thr = _write_kb_s_threshold()
    auto_floor = _automation_write_floor_kb_s()
    sat_thr = _saturation_util_threshold()
    window = _hot_window_sec()
    now = float(sample.get("sampled_at") or time.time())
    recent = [h for h in hist if now - float(h.get("t") or 0) <= window]
    if not recent:
        recent = [
            {
                "t": now,
                "util_pct": float(sample.get("util_pct") or 0.0),
                "write_kb_s": float(sample.get("write_kb_s") or 0.0),
            }
        ]
    avg_util = sum(float(h.get("util_pct") or 0) for h in recent) / max(1, len(recent))
    avg_write = sum(float(h.get("write_kb_s") or 0) for h in recent) / max(1, len(recent))
    cur_write = float(sample.get("write_kb_s") or 0.0)
    # Single sample is enough (15s timer vs old 15s window left hot_util stuck false).
    hot_util = avg_util >= util_thr
    hot_write = avg_write >= write_thr or cur_write >= write_thr
    saturated = avg_util >= sat_thr
    # Apt / package installs: util storm OR big write burst
    defer_heavy = bool(hot_util or hot_write)
    # Automation: big write burst, util-hot with write floor, or USB saturation
    defer_new = bool(
        hot_write
        or (hot_util and (avg_write >= auto_floor or cur_write >= auto_floor))
        or saturated
    )
    detail = {
        "util_threshold": util_thr,
        "write_kb_s_threshold": write_thr,
        "automation_write_floor_kb_s": auto_floor,
        "saturation_util_threshold": sat_thr,
        "hot_window_sec": window,
        "avg_util_pct": round(avg_util, 2),
        "avg_write_kb_s": round(avg_write, 1),
        "samples_in_window": len(recent),
        "hot_util": hot_util,
        "hot_write": hot_write,
        "saturated": saturated,
    }
    return defer_heavy, defer_new, detail


def build_disk_io_pressure_signal(
    sample: Optional[dict[str, Any]] = None,
    *,
    source: str = "api",
    do_sample: bool = True,
) -> dict[str, Any]:
    """Build advisory payload from a live sample (or provided sample)."""
    if sample is None and do_sample:
        sample = sample_disk_io()
    elif sample is None:
        sample = {
            "device": resolve_root_block_device(),
            "util_pct": 0.0,
            "write_kb_s": 0.0,
            "read_kb_s": 0.0,
            "sampled_at": time.time(),
        }
    hist = _update_hot_history(sample)
    defer_heavy, defer_new, detail = _defer_from_history(sample, hist)
    return {
        "source": source,
        "device": sample.get("device") or resolve_root_block_device(),
        "util_pct": float(sample.get("util_pct") or 0.0),
        "write_kb_s": float(sample.get("write_kb_s") or 0.0),
        "read_kb_s": float(sample.get("read_kb_s") or 0.0),
        "defer_heavy_writes": defer_heavy,
        "defer_new_work": defer_new,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    }


def write_run_file(signal: dict[str, Any]) -> Optional[Path]:
    """Write pressure snapshot to tmpfs for apt / host scripts."""
    try:
        _RUN_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            **signal,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        _RUN_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return _RUN_JSON
    except Exception as e:
        logger.debug("write_run_file failed: %s", e)
        return None


def read_run_file(*, max_age_sec: Optional[float] = None) -> dict[str, Any]:
    """Read /run snapshot; fail-open (defer false) if missing/stale."""
    stale_after = _stale_sec() if max_age_sec is None else max(1.0, float(max_age_sec))
    out: dict[str, Any] = {
        "available": False,
        "stale": True,
        "defer_heavy_writes": False,
        "defer_new_work": False,
    }
    try:
        if not _RUN_JSON.is_file():
            return out
        data = json.loads(_RUN_JSON.read_text(encoding="utf-8"))
        # Prefer sampled_at / written_at for age
        age = None
        for key in ("sampled_at",):
            if key in (data.get("detail") or {}):
                pass
        written = data.get("written_at") or data.get("updated_at")
        if written:
            try:
                # ISO from us
                ts = datetime.fromisoformat(str(written).replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
            except Exception:
                age = None
        stale = age is None or age > stale_after
        # Preserve distinct gates; fail-open both when stale.
        heavy = bool(data.get("defer_heavy_writes")) and not stale
        new_work = bool(data.get("defer_new_work")) and not stale
        out.update(
            {
                "available": True,
                "stale": stale,
                "age_sec": round(age, 1) if age is not None else None,
                "device": data.get("device"),
                "util_pct": float(data.get("util_pct") or 0.0),
                "write_kb_s": float(data.get("write_kb_s") or 0.0),
                "defer_heavy_writes": heavy,
                "defer_new_work": new_work,
                "source": data.get("source"),
                "detail": data.get("detail") if isinstance(data.get("detail"), dict) else {},
                "updated_at": data.get("updated_at") or data.get("written_at"),
            }
        )
        return out
    except Exception as e:
        out["error"] = str(e)[:160]
        return out


def publish_disk_io_pressure_advisory(
    sample: Optional[dict[str, Any]] = None,
    *,
    source: str = "api",
    force: bool = False,
    do_sample: bool = True,
) -> Optional[dict[str, Any]]:
    """Sample (optional), write /run JSON, upsert DB row. Throttled unless force/state change."""
    global _LAST_PUBLISH_MONO, _LAST_PUBLISH_SIGNATURE
    signal = build_disk_io_pressure_signal(sample, source=source, do_sample=do_sample)
    write_run_file(signal)
    signature = (
        signal["defer_new_work"],
        round(float(signal["util_pct"]), 0),
        round(float(signal["write_kb_s"]), -1),
        signal.get("device"),
    )
    now = time.monotonic()
    if (
        not force
        and signature == _LAST_PUBLISH_SIGNATURE
        and (now - _LAST_PUBLISH_MONO) < _min_publish_interval_sec()
    ):
        return signal

    try:
        from shared.database.connection import get_ephemeral_db_connection_context

        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.disk_io_pressure_advisory AS t (
                        id, source, device, util_pct, write_kb_s,
                        defer_heavy_writes, defer_new_work, updated_at, detail
                    ) VALUES (
                        1, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        source = EXCLUDED.source,
                        device = EXCLUDED.device,
                        util_pct = EXCLUDED.util_pct,
                        write_kb_s = EXCLUDED.write_kb_s,
                        defer_heavy_writes = EXCLUDED.defer_heavy_writes,
                        defer_new_work = EXCLUDED.defer_new_work,
                        updated_at = NOW(),
                        detail = EXCLUDED.detail
                    """,
                    (
                        source,
                        signal["device"],
                        signal["util_pct"],
                        signal["write_kb_s"],
                        signal["defer_heavy_writes"],
                        signal["defer_new_work"],
                        json.dumps(signal.get("detail") or {}),
                    ),
                )
            conn.commit()
        _LAST_PUBLISH_MONO = now
        _LAST_PUBLISH_SIGNATURE = signature
        return signal
    except Exception as e:
        logger.debug("publish_disk_io_pressure_advisory failed: %s", e)
        return signal


def read_disk_io_pressure_advisory(
    *,
    max_age_sec: Optional[float] = None,
) -> dict[str, Any]:
    """Read DB advisory; fail-open if missing/stale. Falls back to /run file."""
    stale_after = _stale_sec() if max_age_sec is None else max(1.0, float(max_age_sec))
    out: dict[str, Any] = {
        "available": False,
        "stale": True,
        "defer_heavy_writes": False,
        "defer_new_work": False,
        "age_sec": None,
    }
    try:
        from shared.database.connection import get_ephemeral_db_connection_context

        with get_ephemeral_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source, device, util_pct, write_kb_s,
                           defer_heavy_writes, defer_new_work,
                           updated_at, detail,
                           EXTRACT(EPOCH FROM (NOW() - updated_at)) AS age_sec
                    FROM public.disk_io_pressure_advisory
                    WHERE id = 1
                    """
                )
                row = cur.fetchone()
        if row:
            (
                source,
                device,
                util_pct,
                write_kb_s,
                defer_heavy,
                defer_new,
                updated_at,
                detail,
                age_sec,
            ) = row
            age = float(age_sec) if age_sec is not None else None
            stale = age is None or age > stale_after
            heavy = bool(defer_heavy) and not stale
            new_work = bool(defer_new) and not stale
            out.update(
                {
                    "available": True,
                    "stale": stale,
                    "source": source,
                    "device": device,
                    "util_pct": float(util_pct or 0.0),
                    "write_kb_s": float(write_kb_s or 0.0),
                    "defer_heavy_writes": heavy,
                    "defer_new_work": new_work,
                    "updated_at": updated_at.isoformat()
                    if hasattr(updated_at, "isoformat")
                    else str(updated_at),
                    "age_sec": round(age, 1) if age is not None else None,
                    "detail": detail if isinstance(detail, dict) else {},
                }
            )
            return out
    except Exception as e:
        logger.debug("read_disk_io_pressure_advisory failed: %s", e)
        out["error"] = str(e)[:160]

    run = read_run_file(max_age_sec=stale_after)
    if run.get("available"):
        return run
    return out


def _disk_gate_enabled() -> bool:
    return (os.getenv("AUTOMATION_DISK_IO_PRESSURE_GATE_ENABLED", "true") or "true").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _disk_gate_exempt_phases() -> set[str]:
    base = {"health_check", "pending_db_flush"}
    raw = (os.getenv("AUTOMATION_DISK_IO_GATE_EXEMPT_PHASES", "") or "").strip()
    if not raw:
        return set(base)
    return set(base) | {x.strip() for x in raw.split(",") if x.strip()}


def disk_io_should_defer_phase(phase_name: str) -> tuple[bool, dict[str, Any]]:
    """
    True if new scheduled work for this phase should wait (disk hot).

    Prefer /run file (fresh host sample) then DB advisory. Fail-open.
    """
    if not _disk_gate_enabled():
        return False, {"enabled": False}
    if phase_name in _disk_gate_exempt_phases():
        return False, {"exempt": True, "phase": phase_name}
    # Automation uses defer_new_work only — defer_heavy_writes is the apt gate.
    # ORing heavy would freeze the scheduler on mild util-hot / low-write spikes.
    run = read_run_file()
    if run.get("available") and not run.get("stale"):
        defer = bool(run.get("defer_new_work"))
        return defer, run
    adv = read_disk_io_pressure_advisory()
    defer = bool(adv.get("defer_new_work"))
    return defer, adv


def sample_and_publish_run_file(*, source: str = "governor") -> dict[str, Any]:
    """Host governor entry: sample, write /run only (no DB required)."""
    signal = build_disk_io_pressure_signal(source=source, do_sample=True)
    write_run_file(signal)
    return signal
