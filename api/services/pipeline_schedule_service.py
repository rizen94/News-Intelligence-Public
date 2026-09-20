"""
Three-band pipeline schedule (local timezone, default America/New_York).

Windows (half-open [start, end) on the hour; same every day including weekends):
  - **heavy** (alias nightly_heavy): PopOS GPU max catchup (default 01:00–06:00)
  - **morning_ingest**: RSS + GPU spine finish before desk (default 06:00–10:00)
  - **desk_light** (alias quiet): Widow full work; PopOS GPU / Ollama-heavy phases deferred
    (default 10:00–01:00, wraps midnight)

Desk hours are not idle — Widow RSS/enrich/SQL continue. Only GPU-heavy phases are gated
so the PopOS RTX 5090 stays free for interactive LLM / gaming.

Presence (optional, PopOS sensor → automation_state / local JSON):
  - session locked → allow PopOS GPU (override clock)
  - unlocked + HIGH/non-NI Ollama recent → defer GPU
  - else → wall-clock bands (heavy|morning allow, desk_light defer)
  - stale presence (>DESK_PRESENCE_STALE_SEC, default 90) → clock only

Env:
  PIPELINE_SCHEDULE_TZ (or NIGHTLY_PIPELINE_TZ)
  PIPELINE_HEAVY_START_HOUR / PIPELINE_HEAVY_END_HOUR
    (aliases: PIPELINE_NIGHTLY_* / NIGHTLY_PIPELINE_*; default 1 / 6)
  PIPELINE_MORNING_START_HOUR / PIPELINE_MORNING_END_HOUR (default 6 / 10)
  PIPELINE_DESK_START_HOUR / PIPELINE_DESK_END_HOUR (default 10 / 1)
  PIPELINE_GPU_HEAVY_PHASES — comma list blocked during desk_light
  PIPELINE_DESK_GPU_ESCAPE_PHASES — optional subset re-admitted at moderate backlog
  AUTOMATION_BACKLOG_MODERATE_THRESHOLD / AUTOMATION_BACKLOG_SEVERE_THRESHOLD
  PIPELINE_QUIET_HOURS_DISABLED (true) — allow GPU phases at all hours (operator override)
  DESK_PRESENCE_STALE_SEC (default 90)
  DESK_PRESENCE_DISABLED (true) — ignore presence; clock only
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from config.runtime import env_bool, env_int, env_str

LOG = logging.getLogger(__name__)

DESK_PRESENCE_STATE_KEY = "desk_presence"

# PopOS / Ollama consumers deferred during desk_light (Widow-safe phases are always allowed).
# PopOS / true GPU (or GPU-bound refinement) only. Widow DB/CPU/fetch phases must NOT
# sit here — desk_light would starve actionable drains (event_tracking, MR, EPB, RAG).
_DEFAULT_GPU_HEAVY_PHASES = frozenset(
    {
        "unified_intake_extraction",
        "claim_extraction",
        "entity_extraction",
        "event_extraction",
        "entity_dossier_compile",
        "entity_enrichment",
        "storyline_assembly",
        "storyline_automation",
        "storyline_review_agent",
        "topic_clustering",
        "graph_connection_distillation",
        "content_refinement",
        "cross_domain_synthesis",
        "fact_verification",
        "ml_processing",
        "quality_scoring",
        "sentiment_analysis",
        "metadata_enrichment",
        "entity_organizer",
        "story_continuation",
        "extracted_claims_dedupe",
        "claim_subject_gap_refresh",
        "event_deduplication",
        "legislative_references",
        "nightly_enrichment_context",
    }
)

# Escape hatch: re-admit these GPU phases in desk when pending ≥ moderate (severe admits any).
_DEFAULT_DESK_GPU_ESCAPE = frozenset(
    {
        "unified_intake_extraction",
        "content_enrichment",  # not GPU-heavy but listed for escape consistency
        "claim_extraction",
        "storyline_review_agent",
    }
)


def pipeline_schedule_tz() -> ZoneInfo:
    tz_name = (
        env_str("PIPELINE_SCHEDULE_TZ")
        or env_str("NIGHTLY_PIPELINE_TZ")
        or "America/New_York"
    ).strip() or "America/New_York"
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("America/New_York")


def _hour_env_chain(*names: str, default: int) -> int:
    for name in names:
        if not name:
            continue
        raw = env_str(name)
        if raw is None or not str(raw).strip():
            continue
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            continue
    return default


def heavy_start_hour() -> int:
    return _hour_env_chain(
        "PIPELINE_HEAVY_START_HOUR",
        "PIPELINE_NIGHTLY_START_HOUR",
        "NIGHTLY_PIPELINE_START_HOUR",
        default=1,
    )


def heavy_end_hour() -> int:
    return _hour_env_chain(
        "PIPELINE_HEAVY_END_HOUR",
        "PIPELINE_NIGHTLY_END_HOUR",
        "NIGHTLY_PIPELINE_END_HOUR",
        default=6,
    )


def morning_start_hour() -> int:
    return _hour_env_chain("PIPELINE_MORNING_START_HOUR", default=6)


def morning_end_hour() -> int:
    return _hour_env_chain("PIPELINE_MORNING_END_HOUR", default=10)


def desk_start_hour() -> int:
    return _hour_env_chain(
        "PIPELINE_DESK_START_HOUR",
        default=10,
    )


def desk_end_hour() -> int:
    return _hour_env_chain(
        "PIPELINE_DESK_END_HOUR",
        default=1,
    )


# --- Legacy hour helpers (nightly aliases) ---------------------------------


def nightly_start_hour() -> int:
    return heavy_start_hour()


def nightly_end_hour() -> int:
    return heavy_end_hour()


def daytime_start_hour() -> int:
    """Legacy: morning ingest start."""
    return morning_start_hour()


def daytime_end_hour() -> int:
    """Legacy: morning ingest end / desk start."""
    return morning_end_hour()


def quiet_hours_disabled() -> bool:
    """Operator override: allow PopOS GPU phases at all local hours."""
    return env_bool("PIPELINE_QUIET_HOURS_DISABLED", False)


def _in_hour_window(now_local: datetime, start_h: int, end_h: int) -> bool:
    start = now_local.replace(hour=start_h % 24, minute=0, second=0, microsecond=0)
    end = now_local.replace(hour=end_h % 24, minute=0, second=0, microsecond=0)
    if start_h == end_h:
        return True
    if start_h < end_h:
        return start <= now_local < end
    # Wrap midnight (desk 10:00–01:00)
    return now_local >= start or now_local < end


def in_heavy_window(now_local: datetime | None = None) -> bool:
    """Daily PopOS GPU max catchup (default 01:00–06:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return _in_hour_window(now_local, heavy_start_hour(), heavy_end_hour())


def in_morning_ingest_window(now_local: datetime | None = None) -> bool:
    """Morning RSS + GPU finish band (default 06:00–10:00 local)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    return _in_hour_window(now_local, morning_start_hour(), morning_end_hour())


def in_desk_light_window(now_local: datetime | None = None) -> bool:
    """Desk hours: Widow full, PopOS GPU deferred (default 10:00–01:00 local)."""
    if quiet_hours_disabled():
        return False
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if in_heavy_window(now_local) or in_morning_ingest_window(now_local):
        return False
    return _in_hour_window(now_local, desk_start_hour(), desk_end_hour())


def in_nightly_heavy_window(now_local: datetime | None = None) -> bool:
    """Alias for in_heavy_window (legacy name)."""
    return in_heavy_window(now_local)


def in_weekday_daytime_window(now_local: datetime | None = None) -> bool:
    """Alias for morning_ingest (legacy name; no longer Mon–Fri-only)."""
    return in_morning_ingest_window(now_local)


def in_pipeline_quiet_window(now_local: datetime | None = None) -> bool:
    """Alias for desk_light (legacy name: GPU deferred, not Widow idle)."""
    return in_desk_light_window(now_local)


def active_pipeline_window(now_local: datetime | None = None) -> str:
    """One of heavy, morning_ingest, desk_light (canonical)."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    if quiet_hours_disabled():
        if in_heavy_window(now_local):
            return "heavy"
        return "morning_ingest"
    if in_heavy_window(now_local):
        return "heavy"
    if in_morning_ingest_window(now_local):
        return "morning_ingest"
    return "desk_light"


def _parse_presence_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def desk_presence_stale_sec() -> int:
    return max(15, env_int("DESK_PRESENCE_STALE_SEC", 90))


def desk_presence_disabled() -> bool:
    return env_bool("DESK_PRESENCE_DISABLED", False)


def _local_presence_paths() -> list[Path]:
    paths: list[Path] = []
    override = (env_str("DESK_PRESENCE_FILE") or "").strip()
    if override:
        paths.append(Path(override))
    xdg = (os.environ.get("XDG_RUNTIME_DIR") or "").strip()
    if xdg:
        paths.append(Path(xdg) / "ni-desk-presence.json")
    try:
        paths.append(Path(f"/run/user/{os.getuid()}") / "ni-desk-presence.json")
    except Exception:
        pass
    # Repo-relative fallback (dev)
    try:
        root = Path(__file__).resolve().parents[2]
        paths.append(root / ".local" / "desk_presence.json")
    except Exception:
        pass
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _load_presence_dict_from_file() -> dict[str, Any] | None:
    for path in _local_presence_paths():
        try:
            if not path.is_file():
                continue
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                data = dict(data)
                data["_source"] = f"file:{path}"
                return data
        except (OSError, json.JSONDecodeError) as exc:
            LOG.debug("desk_presence file %s unreadable: %s", path, exc)
    return None


def _load_presence_dict_from_db() -> dict[str, Any] | None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value, updated_at FROM public.automation_state WHERE key = %s",
                    (DESK_PRESENCE_STATE_KEY,),
                )
                row = cur.fetchone()
        if not row:
            return None
        payload, updated_at = row[0], row[1] if len(row) > 1 else None
        if isinstance(payload, str):
            payload = json.loads(payload)
        if not isinstance(payload, dict):
            return None
        data = dict(payload)
        data["_source"] = "automation_state"
        if updated_at is not None and data.get("ts") is None:
            data["ts"] = (
                updated_at.isoformat()
                if isinstance(updated_at, datetime)
                else str(updated_at)
            )
        return data
    except Exception as exc:
        LOG.debug("desk_presence DB read skipped: %s", exc)
        return None


def read_desk_presence(*, now_utc: datetime | None = None) -> dict[str, Any] | None:
    """
    Fresh desk presence payload, or None when missing/stale/disabled.

    Prefers local JSON (PopOS worker) then public.automation_state (Widow).
    """
    if desk_presence_disabled():
        return None
    data = _load_presence_dict_from_file() or _load_presence_dict_from_db()
    if not data:
        return None
    ts = _parse_presence_ts(data.get("ts"))
    if ts is None:
        return None
    now = now_utc or datetime.now(timezone.utc)
    age = (now - ts).total_seconds()
    if age < 0 or age > float(desk_presence_stale_sec()):
        return None
    out = dict(data)
    out["_age_sec"] = round(age, 1)
    out["_fresh"] = True
    return out


def wall_clock_popos_gpu_allowed(*, now_local: datetime | None = None) -> bool:
    """Clock-only GPU gate (no presence)."""
    if quiet_hours_disabled():
        return True
    return active_pipeline_window(now_local) in ("heavy", "morning_ingest")


def popos_gpu_work_allowed_detail(
    *,
    now_local: datetime | None = None,
    presence: dict[str, Any] | None = ...,  # type: ignore[assignment]
) -> dict[str, Any]:
    """
    Decide PopOS GPU eligibility with presence override + wall-clock baseline.

    Rules (when presence fresh):
      session_locked → allow
      interactive_ollama → defer
      else → wall-clock (heavy|morning allow, desk_light defer)
    Stale/missing presence → wall-clock only.
    """
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    clock_ok = wall_clock_popos_gpu_allowed(now_local=now_local)
    if presence is ...:
        presence = read_desk_presence()
    detail: dict[str, Any] = {
        "allowed": clock_ok,
        "reason": "wall_clock",
        "wall_clock_allowed": clock_ok,
        "active_window": active_pipeline_window(now_local),
        "desk_presence": presence,
    }
    if quiet_hours_disabled():
        detail["allowed"] = True
        detail["reason"] = "quiet_hours_disabled"
        return detail
    if not presence:
        detail["reason"] = "wall_clock_no_presence"
        return detail

    locked = presence.get("session_locked")
    interactive = bool(presence.get("interactive_ollama"))
    if locked is True:
        detail["allowed"] = True
        detail["reason"] = "session_locked"
        return detail
    if interactive:
        detail["allowed"] = False
        detail["reason"] = "interactive_ollama"
        return detail
    detail["allowed"] = clock_ok
    detail["reason"] = "wall_clock"
    return detail


def popos_gpu_work_allowed(*, now_local: datetime | None = None) -> bool:
    """True when PopOS GPU phases may run (presence + wall-clock)."""
    return bool(popos_gpu_work_allowed_detail(now_local=now_local)["allowed"])


def widow_work_allowed(*, now_local: datetime | None = None) -> bool:
    """Widow CPU/DB/HTTP work is always allowed under the desk schedule."""
    return True


def _parse_phase_set(raw: str, default: frozenset[str]) -> frozenset[str]:
    text = (raw or "").strip()
    if not text:
        return default
    return frozenset(x.strip() for x in text.split(",") if x.strip())


def gpu_heavy_phases() -> frozenset[str]:
    return _parse_phase_set(env_str("PIPELINE_GPU_HEAVY_PHASES", ""), _DEFAULT_GPU_HEAVY_PHASES)


def desk_gpu_escape_phases() -> frozenset[str]:
    """GPU phases that may run in desk_light when pending ≥ moderate threshold."""
    raw = env_str("PIPELINE_DESK_GPU_ESCAPE_PHASES", "").strip()
    if not raw:
        # Legacy quiet drain allowlist if set
        legacy = env_str("PIPELINE_QUIET_DRAIN_PHASES", "").strip()
        if legacy:
            return _parse_phase_set(legacy, _DEFAULT_DESK_GPU_ESCAPE)
        return _DEFAULT_DESK_GPU_ESCAPE
    return _parse_phase_set(raw, _DEFAULT_DESK_GPU_ESCAPE)


def is_gpu_heavy_phase(phase_name: str) -> bool:
    return (phase_name or "").strip() in gpu_heavy_phases()


def _backlog_severe_threshold() -> int:
    try:
        return max(1, int(env_str("AUTOMATION_BACKLOG_SEVERE_THRESHOLD", "10000")))
    except (TypeError, ValueError):
        return 10000


def _backlog_moderate_threshold() -> int:
    try:
        raw = env_str("AUTOMATION_BACKLOG_MODERATE_THRESHOLD", "").strip()
        if raw:
            return max(1, int(raw))
    except (TypeError, ValueError):
        pass
    return max(500, _backlog_severe_threshold() // 4)


def automation_phase_allowed(
    phase_name: str,
    *,
    now_local: datetime | None = None,
    pending_count: int | None = None,
) -> bool:
    """
    Whether AutomationManager / PopOS workers may run this phase under the schedule.

    Non-GPU (Widow-safe) phases: always allowed.
    GPU-heavy phases: allowed in heavy/morning; in desk_light only via backlog escape.
    """
    name = (phase_name or "").strip()
    if not name:
        return False
    if quiet_hours_disabled():
        return True
    if not is_gpu_heavy_phase(name):
        return True
    if popos_gpu_work_allowed(now_local=now_local):
        return True
    # desk_light: escape hatches
    pending = max(0, int(pending_count or 0))
    if pending >= _backlog_severe_threshold():
        return True
    if name in desk_gpu_escape_phases() and pending >= _backlog_moderate_threshold():
        return True
    # Suggestion burn-down: allow at residual-scale pending during desk_light.
    if name == "storyline_review_agent":
        try:
            review_min = max(1, int(env_str("STORYLINE_REVIEW_QUIET_MIN_PENDING", "100") or "100"))
        except ValueError:
            review_min = 100
        if pending >= review_min:
            return True
    # Durable content-refinement jobs (auto-enqueue / UI) — don't stall all weekend.
    if name == "content_refinement_queue":
        try:
            crq_min = max(1, int(env_str("CONTENT_REFINEMENT_QUIET_MIN_PENDING", "5") or "5"))
        except ValueError:
            crq_min = 5
        if pending >= crq_min:
            return True
    return False


def rss_collection_allowed(*, now_local: datetime | None = None) -> bool:
    """Widow RSS is allowed in all schedule bands (desk schedule)."""
    return True


def db_adjacent_sync_allowed(*, now_local: datetime | None = None) -> bool:
    """context_sync / entity_profile_sync on Widow — always allowed (non-GPU)."""
    return True


def _next_boundary(
    now_local: datetime,
    *,
    active: str,
) -> tuple[str | None, str | None]:
    """Return (next_transition_iso, next_window)."""
    h0, h1 = heavy_start_hour(), heavy_end_hour()
    m0, m1 = morning_start_hour(), morning_end_hour()
    d0, d1 = desk_start_hour(), desk_end_hour()

    def at_hour(day: datetime, hour: int) -> datetime:
        return day.replace(hour=hour % 24, minute=0, second=0, microsecond=0)

    if active == "heavy":
        return at_hour(now_local, h1).isoformat(), "morning_ingest"
    if active == "morning_ingest":
        return at_hour(now_local, m1).isoformat(), "desk_light"
    # desk_light → next heavy (may be tomorrow if past midnight before heavy start)
    if now_local.hour >= d0 or now_local.hour < d1:
        # In evening part of desk (e.g. 10–24) → heavy tomorrow at h0
        # Or early morning desk wrap (0–1) → heavy today at h0 if still before h0
        if now_local.hour < h0:
            return at_hour(now_local, h0).isoformat(), "heavy"
        next_day = now_local + timedelta(days=1)
        return at_hour(next_day, h0).isoformat(), "heavy"
    return at_hour(now_local, h0).isoformat(), "heavy"


def pipeline_schedule_info(*, now_local: datetime | None = None) -> dict[str, Any]:
    """Snapshot for Monitor / validation scripts."""
    if now_local is None:
        now_local = datetime.now(pipeline_schedule_tz())
    zi = pipeline_schedule_tz()
    start_h, end_h = heavy_start_hour(), heavy_end_hour()
    start_m, end_m = morning_start_hour(), morning_end_hour()
    start_d, end_d = desk_start_hour(), desk_end_hour()
    active = active_pipeline_window(now_local)
    next_transition, next_window = _next_boundary(now_local, active=active)
    gpu_detail = popos_gpu_work_allowed_detail(now_local=now_local)
    gpu_ok = bool(gpu_detail["allowed"])
    presence = gpu_detail.get("desk_presence")

    return {
        "timezone": str(zi),
        "active_window": active,
        # Canonical flags
        "in_heavy": in_heavy_window(now_local),
        "in_morning_ingest": in_morning_ingest_window(now_local),
        "in_desk_light": in_desk_light_window(now_local),
        # Legacy aliases (Monitor / older docs)
        "in_nightly_heavy": in_heavy_window(now_local),
        "in_weekday_daytime": in_morning_ingest_window(now_local),
        "in_quiet": in_desk_light_window(now_local),
        "heavy_window_local": f"{start_h:02d}:00–{end_h:02d}:00",
        "morning_window_local": f"{start_m:02d}:00–{end_m:02d}:00",
        "desk_window_local": f"{start_d:02d}:00–{end_d:02d}:00 (wraps)",
        "nightly_window_local": f"{start_h:02d}:00–{end_h:02d}:00",
        "daytime_window_local": f"daily {start_m:02d}:00–{end_m:02d}:00 (morning_ingest)",
        "quiet_window_local": f"daily {start_d:02d}:00–{end_d:02d}:00 desk_light (GPU deferred)",
        "rss_collection_allowed": rss_collection_allowed(now_local=now_local),
        "widow_work_allowed": widow_work_allowed(now_local=now_local),
        "popos_gpu_work_allowed": gpu_ok,
        "popos_gpu_work_reason": gpu_detail.get("reason"),
        "wall_clock_popos_gpu_allowed": gpu_detail.get("wall_clock_allowed"),
        "desk_presence": (
            {
                "fresh": True,
                "age_sec": presence.get("_age_sec"),
                "source": presence.get("_source"),
                "session_locked": presence.get("session_locked"),
                "interactive_ollama": presence.get("interactive_ollama"),
                "interactive_reason": presence.get("interactive_reason"),
                "reason": presence.get("reason"),
                "ts": presence.get("ts"),
            }
            if isinstance(presence, dict)
            else None
        ),
        "automation_allowed_except_essentials": True,
        "gpu_heavy_phases": sorted(gpu_heavy_phases()),
        "desk_gpu_escape_phases": sorted(desk_gpu_escape_phases()),
        "quiet_allowed_phases": ["(widow-safe always; see gpu_heavy_phases for desk blocks)"],
        "quiet_drain_phases": sorted(desk_gpu_escape_phases()),
        "backlog_moderate_threshold": _backlog_moderate_threshold(),
        "backlog_severe_threshold": _backlog_severe_threshold(),
        "quiet_hours_disabled": quiet_hours_disabled(),
        "next_transition_local": next_transition,
        "next_window": next_window,
        "now_local": now_local.isoformat(),
        "schedule_model": "desk_three_band_v1",
        "presence_model": "desk_presence_v1",
    }
