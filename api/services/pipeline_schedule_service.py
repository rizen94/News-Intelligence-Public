"""
Three-window pipeline schedule (local timezone, default America/New_York).

Windows (half-open [start, end) on the hour):
  - **nightly_heavy**: daily backlog drain + GPU synthesis (default 00:00–07:00)
  - **weekday_daytime**: Mon–Fri full RSS + automation (default 07:00–16:00)
  - **quiet**: daily 16:00–00:00 and Sat/Sun 07:00–16:00 — pipeline paused, site stays up

PopOS GPU gate (``popos_gpu_work_allowed``):
  - Allowed in nightly_heavy / weekday_daytime wall-clock windows
  - Deferred in quiet (desk_light alias for PopOS workers)
  - Additionally deferred on PopOS when foreign CUDA co-tenants are active
    (ComfyUI, inspiration-extract, etc.) — see ``POPOS_GPU_COTENANT_DEFER``

Env:
  PIPELINE_SCHEDULE_TZ (or NIGHTLY_PIPELINE_TZ)
  PIPELINE_NIGHTLY_START_HOUR / PIPELINE_NIGHTLY_END_HOUR (fallback: NIGHTLY_PIPELINE_*)
  PIPELINE_DAYTIME_START_HOUR / PIPELINE_DAYTIME_END_HOUR (default 7 / 16)
  PIPELINE_QUIET_ALLOWED_PHASES (default health_check,pending_db_flush,vault_morning_prime)
  PIPELINE_QUIET_HOURS_DISABLED (true) — allow PopOS GPU at all hours (operator override)
  REFINEMENT_DESK_START_HOUR / REFINEMENT_DESK_END_HOUR (default 2 / 9) — ~70b
    content_refinement_queue desk window (aliases CONTENT_REFINEMENT_DESK_*)
  REFINEMENT_DESK_ANYTIME / PIPELINE_REFINEMENT_ANYTIME — operator override for desk window
  POPOS_GPU_COTENANT_DEFER (default true) — defer when non-NI CUDA processes hold VRAM
  POPOS_GPU_COTENANT_NEEDLES — comma substrings matched against nvidia-smi process names
  POPOS_GPU_GAME_DEFER (default true) — defer while local games are running (BG3, etc.)
  POPOS_GPU_GAME_NEEDLES — comma substrings matched against /proc cmdline (default bg3 / Baldur)
"""

from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

LOG = logging.getLogger(__name__)

# Daily reader slate must still fire on weekends / after 16:00 when due.
_DEFAULT_QUIET_ALLOWED = frozenset(
    {"health_check", "pending_db_flush", "vault_morning_prime"}
)


def pipeline_schedule_tz() -> ZoneInfo:
    tz_name = (
        os.environ.get("PIPELINE_SCHEDULE_TZ")
        or os.environ.get("NIGHTLY_PIPELINE_TZ")
        or "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def _hour_env(primary: str, fallback: str, default: int, *, max_hour: int = 23) -> int:
    """Parse an hour env. ``max_hour=24`` allows end-exclusive midnight-tomorrow (ALL_DAY catch-up)."""
    raw = os.environ.get(primary)
    if raw is None or not str(raw).strip():
        raw = os.environ.get(fallback)
    try:
        n = int(raw if raw is not None and str(raw).strip() else default)
    except (TypeError, ValueError):
        return default
    if n < 0:
        return 0
    if n > max_hour:
        return max_hour
    return n


def local_hour_boundary(now_local: datetime, hour: int) -> datetime:
    """
    Clock boundary at ``hour`` on ``now_local``'s calendar day.

    ``hour=24`` means end-of-day exclusive → midnight at the start of the next local day.
    Never calls ``datetime.replace(hour=24)`` (ValueError).
    """
    h = int(hour)
    if h >= 24:
        return now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    if h < 0:
        h = 0
    return now_local.replace(hour=h, minute=0, second=0, microsecond=0)


def nightly_start_hour() -> int:
    return _hour_env("PIPELINE_NIGHTLY_START_HOUR", "NIGHTLY_PIPELINE_START_HOUR", 0)


def nightly_end_hour() -> int:
    # Allow 24 for catch-up configs that mean "through end of calendar day".
    return _hour_env("PIPELINE_NIGHTLY_END_HOUR", "NIGHTLY_PIPELINE_END_HOUR", 7, max_hour=24)


def daytime_start_hour() -> int:
    return _hour_env("PIPELINE_DAYTIME_START_HOUR", "", 7)


def daytime_end_hour() -> int:
    return _hour_env("PIPELINE_DAYTIME_END_HOUR", "", 16, max_hour=24)


def refinement_desk_start_hour() -> int:
    """Local start for ~70b content_refinement_queue desk window (default 02:00)."""
    return _hour_env("REFINEMENT_DESK_START_HOUR", "CONTENT_REFINEMENT_DESK_START_HOUR", 2)


def refinement_desk_end_hour() -> int:
    """Local end (exclusive) for refinement desk window (default 09:00)."""
    return _hour_env(
        "REFINEMENT_DESK_END_HOUR", "CONTENT_REFINEMENT_DESK_END_HOUR", 9, max_hour=24
    )


def in_refinement_desk_window(now_local: datetime | None = None) -> bool:
    """
    Overnight/early-morning window for durable ~70b refinement queue drain.

    Default **02:00–09:00** local (``REFINEMENT_DESK_*_HOUR``). Independent of the
    general quiet/nightly labels so refinement does not compete with daytime intake.
    """
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return _in_hour_window(
        now_local, refinement_desk_start_hour(), refinement_desk_end_hour()
    )


def refinement_desk_anytime() -> bool:
    return (os.environ.get("REFINEMENT_DESK_ANYTIME") or os.environ.get("PIPELINE_REFINEMENT_ANYTIME") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def content_refinement_schedule_allowed(*, now_local: datetime | None = None) -> bool:
    """Whether content_refinement_queue may run under the desk window policy."""
    if refinement_desk_anytime():
        return True
    return in_refinement_desk_window(now_local)


def _in_hour_window(now_local: datetime, start_h: int, end_h: int) -> bool:
    start = local_hour_boundary(now_local, start_h)
    end = local_hour_boundary(now_local, end_h)
    if start_h < end_h or end_h >= 24:
        return start <= now_local < end
    # Wrap midnight (e.g. 22→06)
    return now_local >= start or now_local < end


def in_nightly_heavy_window(now_local: datetime | None = None) -> bool:
    """Daily heavy backlog + synthesis window (default 00:00–07:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return _in_hour_window(now_local, nightly_start_hour(), nightly_end_hour())


def in_weekday_daytime_window(now_local: datetime | None = None) -> bool:
    """Mon–Fri full ops window (default 07:00–16:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if now_local.weekday() >= 5:
        return False
    return _in_hour_window(now_local, daytime_start_hour(), daytime_end_hour())


def in_pipeline_quiet_window(now_local: datetime | None = None) -> bool:
    """
    Pipeline paused: daily 16:00–00:00 and weekend 07:00–16:00.
    Mutually exclusive with nightly_heavy and weekday_daytime when configured as 0–7 / 7–16.
    """
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    hour = now_local.hour
    if hour >= daytime_end_hour():
        return True
    if now_local.weekday() >= 5 and hour >= daytime_start_hour():
        return True
    return False


def active_pipeline_window(now_local: datetime | None = None) -> str:
    """One of nightly_heavy, weekday_daytime, quiet."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if in_nightly_heavy_window(now_local):
        return "nightly_heavy"
    if in_weekday_daytime_window(now_local):
        return "weekday_daytime"
    return "quiet"


def quiet_hours_disabled() -> bool:
    """Operator override: allow GPU phases even during the quiet window."""
    return (os.environ.get("PIPELINE_QUIET_HOURS_DISABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def wall_clock_popos_gpu_allowed(*, now_local: datetime | None = None) -> bool:
    """Clock-only PopOS GPU gate (no co-tenant check)."""
    if quiet_hours_disabled():
        return True
    return active_pipeline_window(now_local) in ("nightly_heavy", "weekday_daytime")


_DEFAULT_COTENANT_NEEDLES = (
    "comfy",
    "comfyui",
    "inspiration-extract",
    "inspiration-audiobook",
    "stable-diffusion",
    "fooocus",
    "invokeai",
    "whisper",
)


def _cotenant_needles() -> tuple[str, ...]:
    raw = (os.environ.get("POPOS_GPU_COTENANT_NEEDLES") or "").strip()
    if not raw:
        return _DEFAULT_COTENANT_NEEDLES
    parts = tuple(x.strip().lower() for x in raw.split(",") if x.strip())
    return parts or _DEFAULT_COTENANT_NEEDLES


def _cotenant_defer_enabled() -> bool:
    raw = (os.environ.get("POPOS_GPU_COTENANT_DEFER") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


_DEFAULT_GAME_NEEDLES = (
    "baldurs gate 3/bin/bg3",
    "/bin/bg3",
    "appid=1086940",
    "steamapps/common/baldurs gate 3",
)


def _game_defer_enabled() -> bool:
    raw = (os.environ.get("POPOS_GPU_GAME_DEFER") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _game_needles() -> tuple[str, ...]:
    raw = (os.environ.get("POPOS_GPU_GAME_NEEDLES") or "").strip()
    if not raw:
        return _DEFAULT_GAME_NEEDLES
    parts = tuple(x.strip().lower() for x in raw.split(",") if x.strip())
    return parts or _DEFAULT_GAME_NEEDLES


def _proc_cmdline(pid: str) -> str:
    """Resolve /proc/<pid>/cmdline for generic nvidia-smi names like python3.13."""
    try:
        raw = Path(f"/proc/{int(pid)}/cmdline").read_bytes()
    except (OSError, ValueError):
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()


def detect_popos_game_processes() -> dict[str, Any]:
    """
    Scan /proc for local games that should own the desk GPU (BG3 by default).

    Games often do not appear in nvidia-smi compute-apps (graphics/Vulkan), so
    this is separate from ``detect_popos_gpu_cotenants``.
    """
    out: dict[str, Any] = {"active": False, "processes": []}
    if not _game_defer_enabled():
        out["disabled"] = True
        return out
    needles = _game_needles()
    hits: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    try:
        proc_root = Path("/proc")
        for entry in proc_root.iterdir():
            if not entry.name.isdigit():
                continue
            pid_s = entry.name
            try:
                cmdline = _proc_cmdline(pid_s)
                if not cmdline:
                    continue
                # Prefer the real game binary over Steam launch wrappers.
                comm = ""
                try:
                    comm = (entry / "comm").read_text(encoding="utf-8", errors="ignore").strip()
                except OSError:
                    pass
                hay = f"{comm} {cmdline}".lower()
                if not any(n in hay for n in needles):
                    continue
                # Deduplicate: keep bg3 binary hits; skip pure wrapper noise when
                # the real binary is also present.
                if pid_s in seen_pids:
                    continue
                seen_pids.add(pid_s)
                hits.append(
                    {
                        "pid": pid_s,
                        "comm": comm,
                        "cmdline": cmdline[:220],
                    }
                )
            except (OSError, ValueError):
                continue
    except OSError as exc:
        out["error"] = str(exc)[:160]
        return out

    # Prefer reporting the actual bg3 binary if present.
    binary_hits = [h for h in hits if (h.get("comm") or "").lower() == "bg3" or "/bin/bg3" in (h.get("cmdline") or "").lower()]
    out["processes"] = binary_hits or hits[:8]
    out["active"] = bool(hits)
    return out


def detect_popos_gpu_cotenants() -> dict[str, Any]:
    """
    Best-effort nvidia-smi scan for non-Ollama CUDA consumers on this host.

    Returns ``{active: bool, processes: [...], error?: str}``. Safe no-op off-GPU hosts.
    ``nvidia-smi`` often reports only ``python3.x`` — we also match /proc cmdline.
    """
    out: dict[str, Any] = {"active": False, "processes": []}
    if not _cotenant_defer_enabled():
        out["disabled"] = True
        return out
    needles = _cotenant_needles()
    try:
        proc = subprocess.run(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,process_name,used_gpu_memory",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        out["error"] = str(exc)[:160]
        return out
    if proc.returncode != 0:
        out["error"] = (proc.stderr or "nvidia-smi failed")[:160]
        return out
    hits: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        pid_s, name = parts[0], parts[1]
        mem_s = parts[2] if len(parts) >= 3 else ""
        cmdline = _proc_cmdline(pid_s)
        hay = f"{name} {cmdline}".lower()
        # Ignore Ollama / NI workers themselves
        if "ollama" in hay or "llama-server" in hay:
            continue
        if "run_popos_phase_worker" in hay or "news-intelligence" in hay:
            continue
        try:
            mem_mb = int(float(mem_s)) if mem_s else 0
        except (TypeError, ValueError):
            mem_mb = 0
        needle_hit = any(n in hay for n in needles)
        # Non-needle CUDA apps still count when they hold meaningful VRAM.
        if not needle_hit and mem_mb < 512:
            continue
        hits.append(
            {
                "pid": pid_s,
                "process_name": name,
                "cmdline": cmdline[:200],
                "used_gpu_memory_mb": mem_mb,
                "matched_needle": needle_hit,
            }
        )
    out["active"] = bool(hits)
    out["processes"] = hits
    return out


def popos_gpu_work_allowed_detail(
    *,
    now_local: datetime | None = None,
) -> dict[str, Any]:
    """
    Decide PopOS GPU eligibility: games → wall-clock → CUDA co-tenant defer.

    Used by PopOS phase workers and refinement gates. Must never raise.
    """
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    clock_ok = wall_clock_popos_gpu_allowed(now_local=now_local)
    window = active_pipeline_window(now_local)
    detail: dict[str, Any] = {
        "allowed": clock_ok,
        "reason": "wall_clock" if clock_ok else "quiet_window",
        "wall_clock_allowed": clock_ok,
        "active_window": window,
        "cotenant": None,
        "game": None,
    }

    host = (os.environ.get("WORKER_EXECUTION_HOST") or "").strip().lower()
    force = (os.environ.get("POPOS_GPU_COTENANT_CHECK") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    on_popos = host in ("popos", "remote", "worker") or force

    # Games always win on the PopOS desk GPU — even during nightly/daytime windows.
    if on_popos:
        game = detect_popos_game_processes()
        detail["game"] = game
        if game.get("active"):
            detail["allowed"] = False
            detail["reason"] = "game_running"
            return detail

    if quiet_hours_disabled():
        detail["allowed"] = True
        detail["reason"] = "quiet_hours_disabled"
        # Still respect co-tenants unless explicitly disabled — desk safety first.
    if not detail["allowed"] and not quiet_hours_disabled():
        return detail

    # Co-tenant check only matters on the PopOS GPU host (or when forced).
    if on_popos:
        cotenant = detect_popos_gpu_cotenants()
        detail["cotenant"] = cotenant
        if cotenant.get("active"):
            detail["allowed"] = False
            detail["reason"] = "gpu_cotenant"
            return detail
    return detail


def popos_gpu_work_allowed(*, now_local: datetime | None = None) -> bool:
    """True when PopOS GPU / Ollama-heavy phases may run."""
    try:
        return bool(popos_gpu_work_allowed_detail(now_local=now_local)["allowed"])
    except Exception as exc:
        LOG.debug("popos_gpu_work_allowed failed open→deny: %s", exc)
        # Fail closed on PopOS workers so a busted gate cannot hard-crash the desk.
        host = (os.environ.get("WORKER_EXECUTION_HOST") or "").strip().lower()
        if host in ("popos", "remote", "worker"):
            return False
        return wall_clock_popos_gpu_allowed(now_local=now_local)


def _quiet_allowed_phases() -> frozenset[str]:
    raw = os.environ.get(
        "PIPELINE_QUIET_ALLOWED_PHASES",
        "health_check,pending_db_flush,vault_morning_prime",
    ).strip()
    if not raw:
        return _DEFAULT_QUIET_ALLOWED
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def _quiet_severe_backlog_phases() -> frozenset[str]:
    """
    Phases that may run in the quiet window when their pending backlog is severe.

    Default: story_enhancement only (fact_change_log catch-up). Override with
    PIPELINE_QUIET_SEVERE_BACKLOG_PHASES=comma,list (empty string disables).
    Threshold: PIPELINE_QUIET_SEVERE_BACKLOG_THRESHOLD (default 25000).
    """
    raw = os.environ.get("PIPELINE_QUIET_SEVERE_BACKLOG_PHASES")
    if raw is None:
        return frozenset({"story_enhancement"})
    raw = raw.strip()
    if not raw:
        return frozenset()
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def _quiet_severe_backlog_threshold() -> int:
    try:
        return int(os.environ.get("PIPELINE_QUIET_SEVERE_BACKLOG_THRESHOLD", "25000"))
    except (TypeError, ValueError):
        return 25000


def _phase_pending_for_quiet_gate(phase_name: str) -> int:
    """Best-effort pending count for quiet severe-backlog exception (0 on failure)."""
    try:
        from services.backlog_metrics import get_all_pending_counts

        return int((get_all_pending_counts() or {}).get(phase_name, 0) or 0)
    except Exception:
        return 0


def automation_phase_allowed(
    phase_name: str,
    *,
    now_local: datetime | None = None,
    pending_count: int | None = None,
) -> bool:
    """Whether AutomationManager may schedule this phase under the operating schedule.

    ``pending_count`` is accepted for PipelineController / admission callers; when
    omitted, quiet severe-backlog checks load counts themselves.
    """
    name = (phase_name or "").strip()
    if not name:
        return False
    # ~70b refinement: desk window only (default 02:00–09:00). Not bypassed by
    # PIPELINE_QUIET_HOURS_DISABLED — use REFINEMENT_DESK_ANYTIME for daytime drain.
    if name == "content_refinement_queue":
        return content_refinement_schedule_allowed(now_local=now_local)
    # Operator override (overnight catch-up): do not pause automation in quiet hours.
    if quiet_hours_disabled():
        return True
    if name in _quiet_allowed_phases():
        return True
    # Targeted entity_profile_build burns set ENTITY_PROFILE_BUILD_ANYTIME=true.
    if name == "entity_profile_build":
        try:
            from config.runtime import env_str

            if env_str("ENTITY_PROFILE_BUILD_ANYTIME", "").lower() in ("1", "true", "yes"):
                return True
        except Exception:
            pass
    # Targeted story_continuation burns set STORY_CONTINUATION_ANYTIME=true.
    if name == "story_continuation":
        try:
            from config.runtime import env_str

            if env_str("STORY_CONTINUATION_ANYTIME", "").lower() in ("1", "true", "yes"):
                return True
        except Exception:
            pass
    window = active_pipeline_window(now_local)
    if window == "quiet":
        # Catch-up exception: do not leave multi-day enhancement piles idle 16:00–00:00.
        if name in _quiet_severe_backlog_phases():
            pending = (
                int(pending_count)
                if pending_count is not None
                else _phase_pending_for_quiet_gate(name)
            )
            if pending >= _quiet_severe_backlog_threshold():
                return True
        return False
    return window in ("nightly_heavy", "weekday_daytime")


def rss_collection_allowed(*, now_local: datetime | None = None) -> bool:
    """Widow RSS + nightly kickoff: weekday daytime or nightly heavy, not quiet-only."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return in_nightly_heavy_window(now_local) or in_weekday_daytime_window(now_local)


def db_adjacent_sync_allowed(*, now_local: datetime | None = None) -> bool:
    """context_sync / entity_profile_sync on Widow — same gates as pipeline automation."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return not in_pipeline_quiet_window(now_local)


def pipeline_schedule_info(*, now_local: datetime | None = None) -> dict[str, Any]:
    """Snapshot for Monitor / validation scripts."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    zi = pipeline_schedule_tz()
    start_n = nightly_start_hour()
    end_n = nightly_end_hour()
    start_d = daytime_start_hour()
    end_d = daytime_end_hour()
    active = active_pipeline_window(now_local)

    next_transition: str | None = None
    next_window: str | None = None
    if active == "nightly_heavy":
        next_at = local_hour_boundary(now_local, end_n)
        next_window = "weekday_daytime" if now_local.weekday() < 5 else "quiet"
        next_transition = next_at.isoformat()
    elif active == "weekday_daytime":
        next_at = local_hour_boundary(now_local, end_d)
        next_window = "quiet"
        next_transition = next_at.isoformat()
    elif active == "quiet":
        # end_d=24 means end-of-day; hour>=24 is never true, so treat as past daytime.
        if end_d >= 24 or now_local.hour >= end_d:
            next_day = now_local + timedelta(days=1)
            next_at = local_hour_boundary(next_day, start_n)
            next_window = "nightly_heavy"
        elif now_local.weekday() >= 5:
            next_at = local_hour_boundary(now_local, end_d)
            next_window = "quiet"
        else:
            next_at = local_hour_boundary(now_local, start_d)
            next_window = "weekday_daytime"
        next_transition = next_at.isoformat()

    start_r = refinement_desk_start_hour()
    end_r = refinement_desk_end_hour()
    return {
        "timezone": str(zi),
        "active_window": active,
        "in_nightly_heavy": in_nightly_heavy_window(now_local),
        "in_weekday_daytime": in_weekday_daytime_window(now_local),
        "in_quiet": in_pipeline_quiet_window(now_local),
        "in_refinement_desk": in_refinement_desk_window(now_local),
        "content_refinement_schedule_allowed": content_refinement_schedule_allowed(
            now_local=now_local
        ),
        "nightly_window_local": f"{start_n:02d}:00–{end_n:02d}:00",
        "daytime_window_local": f"Mon–Fri {start_d:02d}:00–{end_d:02d}:00",
        "quiet_window_local": f"Daily {end_d:02d}:00–{start_n:02d}:00; Sat–Sun {start_d:02d}:00–{end_d:02d}:00",
        "refinement_desk_window_local": f"{start_r:02d}:00–{end_r:02d}:00",
        "rss_collection_allowed": rss_collection_allowed(now_local=now_local),
        "automation_allowed_except_essentials": active != "quiet",
        "quiet_allowed_phases": sorted(_quiet_allowed_phases()),
        "next_transition_local": next_transition,
        "next_window": next_window,
        "now_local": now_local.isoformat(),
    }
