"""Restart metrics reader — reads per-restart timing data from the watchdog JSON file.

Path: /run/news-intelligence/api_restart_metrics.json
Format: [{restart_start, restart_ready, duration_sec, attempts, status, reason, timestamp}]
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METRICS_PATH = "/run/news-intelligence/api_restart_metrics.json"

def _read_metrics_file(path: str | None = None) -> list[dict[str, Any]]:
    """Read and parse the restart metrics JSON file."""
    if path is None:
        path = METRICS_PATH
    try:
        p = Path(path)
        if not p.exists():
            return []
        content = p.read_text()
        if not content.strip():
            return []
        return json.loads(content)
    except (json.JSONDecodeError, OSError, PermissionError):
        return []


def get_restart_metrics(count: int = 20) -> list[dict[str, Any]]:
    """Get recent restart metrics entries.
    
    Args:
        count: Number of recent entries to return (default 20)
    
    Returns:
        List of restart metric dicts sorted by timestamp desc
    """
    metrics = _read_metrics_file()
    if not metrics:
        return []
    
    # Sort by timestamp descending, take last N
    sorted_metrics = sorted(metrics, key=lambda x: x.get("timestamp", ""), reverse=True)
    return sorted_metrics[:count]


def get_restart_summary() -> dict[str, Any]:
    """Get summary statistics of recent restart metrics.
    
    Returns:
        Dict with total_restarts, avg_duration, max_duration, min_duration,
        last_status, uptime_pct (estimated), and recent_history
    """
    all_metrics = _read_metrics_file()
    if not all_metrics:
        return {
            "total_restarts": 0,
            "avg_duration_sec": 0,
            "max_duration_sec": 0,
            "min_duration_sec": 999,
            "last_status": None,
            "uptime_percent": None,
            "recent_history": [],
        }
    
    # Filter out entries with zero or null duration
    valid = [m for m in all_metrics if m.get("duration_sec", 0) > 0]
    
    if not valid:
        return {
            "total_restarts": len(all_metrics),
            "avg_duration_sec": 0,
            "max_duration_sec": 0,
            "min_duration_sec": 999,
            "last_status": None,
            "uptime_percent": None,
            "recent_history": [],
        }
    
    durations = [m["duration_sec"] for m in valid]
    total_restarts = len(all_metrics)
    avg_dur = sum(durations) / len(durations)
    last_entry = sorted(all_metrics, key=lambda x: x.get("timestamp", ""), reverse=True)[0]
    
    # Calculate uptime percentage (last 24h window)
    now = datetime.now(timezone.utc)
    window_start = now.timestamp() - 86400
    recent_starts = []
    for m in all_metrics:
        try:
            raw_ts = m["restart_start"]
            if raw_ts is None:
                continue
            ts = datetime.fromisoformat(raw_ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts.timestamp() >= window_start:
                recent_starts.append(m)
        except (ValueError, KeyError):
            pass
    
    # Sum downtime seconds in last 24h from all restart events
    total_downtime = sum(m["duration_sec"] for m in recent_starts)
    uptime_pct = max(0, ((86400 - total_downtime) / 86400) * 100)
    
    return {
        "total_restarts": total_restarts,
        "avg_duration_sec": round(avg_dur, 2),
        "max_duration_sec": max(durations),
        "min_duration_sec": min(durations),
        "last_status": last_entry.get("status"),
        "last_ready": last_entry.get("restart_ready"),
        "uptime_percent": round(uptime_pct, 2),
        "recent_24h_restarts": len(recent_starts),
        "total_24h_downtime_sec": total_downtime,
        "recent_history": [
            {
                "start": m.get("restart_start"),
                "ready": m.get("restart_ready"),
                "duration_sec": m.get("duration_sec"),
                "status": m.get("status"),
                "attempts": m.get("readiness_attempts"),
            }
            for m in sorted(all_metrics, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
        ],
    }
