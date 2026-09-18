#!/usr/bin/env python3
"""PopOS desk presence sensor for NI GPU gate.

Signals:
  1. Graphical session LockedHint (loginctl) — locked → GPU free for NI
  2. Homelab Ollama proxy HIGH activity — interactive (OWUI / Cursor / etc.)

Writes:
  - Local JSON: $XDG_RUNTIME_DIR/ni-desk-presence.json (fallback .local/)
  - public.automation_state key desk_presence (optional; uses NI DB when available)

Run on PopOS every 15–30s (see infrastructure/ni-desk-presence.user.timer).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG = logging.getLogger("popos_desk_presence")

STATE_KEY = "desk_presence"
DEFAULT_PROXY_STATS = "http://127.0.0.1:11434/api/proxy/stats"


def _env_int(name: str, default: int) -> int:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _runtime_presence_path() -> Path:
    xdg = (os.environ.get("XDG_RUNTIME_DIR") or "").strip()
    if xdg:
        return Path(xdg) / "ni-desk-presence.json"
    uid = os.getuid()
    run_user = Path(f"/run/user/{uid}")
    if run_user.is_dir():
        return run_user / "ni-desk-presence.json"
    local = Path(__file__).resolve().parents[1] / ".local"
    local.mkdir(parents=True, exist_ok=True)
    return local / "desk_presence.json"


def _loginctl(*args: str) -> str:
    try:
        out = subprocess.check_output(
            ["loginctl", *args],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out or ""
    except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
        LOG.debug("loginctl %s failed: %s", args, exc)
        return ""


def _session_lines() -> list[str]:
    """Return non-empty lines from `loginctl list-sessions --no-legend`."""
    raw = _loginctl("list-sessions", "--no-legend")
    return [ln.strip() for ln in raw.splitlines() if ln.strip()]


def _session_id_from_line(line: str) -> str | None:
    # Typical: "3 1000 pete seat0 ..." or "c2 1000 pete ..."
    parts = line.split()
    if not parts:
        return None
    return parts[0]


def _show_session(session_id: str) -> dict[str, str]:
    raw = _loginctl(
        "show-session",
        session_id,
        "-p",
        "Id",
        "-p",
        "Type",
        "-p",
        "Class",
        "-p",
        "State",
        "-p",
        "Active",
        "-p",
        "LockedHint",
        "-p",
        "IdleHint",
    )
    props: dict[str, str] = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        props[key.strip()] = val.strip()
    return props


def read_session_lock_state() -> dict[str, Any]:
    """Inspect graphical user sessions; LockedHint=yes → GPU free."""
    sessions: list[dict[str, str]] = []
    for line in _session_lines():
        sid = _session_id_from_line(line)
        if not sid:
            continue
        props = _show_session(sid)
        if not props:
            continue
        cls = (props.get("Class") or "").lower()
        typ = (props.get("Type") or "").lower()
        # Prefer seat / graphical sessions; skip managers / greeter noise.
        if cls and cls not in ("user", "user-early"):
            continue
        if typ and typ not in ("x11", "wayland", "mir"):
            continue
        sessions.append(props)

    if not sessions:
        return {
            "session_locked": None,
            "session_count": 0,
            "sessions": [],
            "reason_hint": "no_graphical_session",
        }

    locked_flags = []
    for s in sessions:
        hint = (s.get("LockedHint") or "").lower()
        if hint in ("yes", "true", "1"):
            locked_flags.append(True)
        elif hint in ("no", "false", "0"):
            locked_flags.append(False)

    if not locked_flags:
        return {
            "session_locked": None,
            "session_count": len(sessions),
            "sessions": sessions,
            "reason_hint": "locked_hint_unavailable",
        }

    # Any unlocked graphical session → not locked for presence purposes.
    session_locked = all(locked_flags)
    return {
        "session_locked": session_locked,
        "session_count": len(sessions),
        "sessions": [
            {
                "id": s.get("Id"),
                "type": s.get("Type"),
                "locked": (s.get("LockedHint") or "").lower() in ("yes", "true", "1"),
                "idle": (s.get("IdleHint") or "").lower() in ("yes", "true", "1"),
                "active": s.get("Active"),
            }
            for s in sessions
        ],
        "reason_hint": "session_locked" if session_locked else "session_unlocked",
    }


def fetch_proxy_stats(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        return data if isinstance(data, dict) else None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        LOG.warning("proxy stats fetch failed (%s): %s", url, exc)
        return None


def interactive_ollama_busy(
    stats: dict[str, Any] | None,
    *,
    idle_sec: float,
    now: datetime | None = None,
) -> tuple[bool, str]:
    """True when HIGH (non-NI interactive) work is in-flight, queued, or recent."""
    if not stats:
        return False, "proxy_stats_unavailable"
    if stats.get("in_flight") == "high":
        return True, "in_flight_high"
    try:
        queued_high = int(stats.get("queued_high") or 0)
    except (TypeError, ValueError):
        queued_high = 0
    if queued_high > 0:
        return True, "queued_high"
    last_high = _parse_iso(stats.get("last_high_at") if isinstance(stats.get("last_high_at"), str) else None)
    if last_high is not None:
        now = now or datetime.now(timezone.utc)
        if last_high.tzinfo is None:
            last_high = last_high.replace(tzinfo=timezone.utc)
        age = (now - last_high).total_seconds()
        if age >= 0 and age <= idle_sec:
            return True, f"last_high_within_{int(idle_sec)}s"
    return False, "interactive_idle"


def compute_gpu_override(
    *,
    session_locked: bool | None,
    interactive: bool,
    wall_clock_gpu_ok: bool | None = None,
) -> tuple[bool | None, str]:
    """Mirror schedule gate: locked allow; interactive defer; else wall-clock if known."""
    if session_locked is True:
        return True, "session_locked"
    if interactive:
        return False, "interactive_ollama"
    if wall_clock_gpu_ok is not None:
        return bool(wall_clock_gpu_ok), "wall_clock"
    if session_locked is False:
        return None, "unlocked_idle_clock_deferred_to_schedule"
    return None, "presence_incomplete"


def build_payload(
    *,
    session: dict[str, Any],
    stats: dict[str, Any] | None,
    idle_sec: float,
) -> dict[str, Any]:
    interactive, interactive_reason = interactive_ollama_busy(stats, idle_sec=idle_sec)
    session_locked = session.get("session_locked")
    override, reason = compute_gpu_override(
        session_locked=session_locked if isinstance(session_locked, bool) else None,
        interactive=interactive,
    )
    return {
        "ts": _now_iso(),
        "session_locked": session_locked,
        "interactive_ollama": interactive,
        "interactive_reason": interactive_reason,
        "popos_gpu_allowed_override": override,
        "reason": reason,
        "session": {
            "session_count": session.get("session_count"),
            "sessions": session.get("sessions") or [],
            "reason_hint": session.get("reason_hint"),
        },
        "proxy": {
            "in_flight": (stats or {}).get("in_flight"),
            "queued_high": (stats or {}).get("queued_high"),
            "queued_low": (stats or {}).get("queued_low"),
            "last_high_at": (stats or {}).get("last_high_at"),
            "last_low_at": (stats or {}).get("last_low_at"),
            "ni_cidrs": (stats or {}).get("ni_cidrs"),
        },
        "idle_sec": idle_sec,
        "ni_ollama_source_cidrs": [
            c.strip()
            for c in (os.environ.get("NI_OLLAMA_SOURCE_CIDRS") or "192.168.93.101/32").split(",")
            if c.strip()
        ],
    }


def write_local(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_automation_state(payload: dict[str, Any]) -> bool:
    """Upsert desk_presence into public.automation_state when DB is reachable."""
    skip = (os.environ.get("DESK_PRESENCE_SKIP_DB") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if skip:
        return False
    try:
        # Prefer project connection helpers when PYTHONPATH includes api/
        repo_root = Path(__file__).resolve().parents[1]
        api_root = repo_root / "api"
        if str(api_root) not in sys.path:
            sys.path.insert(0, str(api_root))
        from shared.database.connection import get_db_connection_context  # type: ignore

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE
                      SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (STATE_KEY, json.dumps(payload)),
                )
            conn.commit()
        return True
    except Exception as exc:
        LOG.debug("automation_state write skipped: %s", exc)
        return False


def run_once(*, proxy_url: str, idle_sec: float) -> dict[str, Any]:
    session = read_session_lock_state()
    stats = fetch_proxy_stats(proxy_url)
    payload = build_payload(session=session, stats=stats, idle_sec=idle_sec)
    path = _runtime_presence_path()
    write_local(path, payload)
    db_ok = write_automation_state(payload)
    payload["_wrote_local"] = str(path)
    payload["_wrote_db"] = db_ok
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PopOS desk presence sensor for NI GPU gate")
    parser.add_argument(
        "--proxy-stats-url",
        default=os.environ.get("DESK_PRESENCE_PROXY_STATS_URL", DEFAULT_PROXY_STATS),
        help="Ollama proxy /api/proxy/stats URL",
    )
    parser.add_argument(
        "--idle-sec",
        type=float,
        default=_env_float("DESK_INTERACTIVE_IDLE_SEC", 120.0),
        help="Seconds after last HIGH acquire still counted as interactive",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print payload JSON to stdout")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    payload = run_once(proxy_url=args.proxy_stats_url, idle_sec=float(args.idle_sec))
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        LOG.info(
            "desk_presence locked=%s interactive=%s override=%s reason=%s local=%s db=%s",
            payload.get("session_locked"),
            payload.get("interactive_ollama"),
            payload.get("popos_gpu_allowed_override"),
            payload.get("reason"),
            payload.get("_wrote_local"),
            payload.get("_wrote_db"),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
