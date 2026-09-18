#!/usr/bin/env python3
"""Probe automation status → print scheduler wiring evidence."""
from __future__ import annotations

import json
import sys
import urllib.request

DEFAULT_URL = "http://192.168.93.101:8000/api/system_monitoring/automation/status"


def main() -> int:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL
    if url.startswith("file:"):
        raw = open(url[5:], encoding="utf-8").read()
    else:
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            cached = "/tmp/am_status.json"
            try:
                raw = open(cached, encoding="utf-8").read()
                print(f"url_failed_used_cache: {e}", file=sys.stderr)
            except Exception:
                print(f"fetch failed: {e}", file=sys.stderr)
                return 2

    payload = json.loads(raw)
    data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload
    pc = data.get("pipeline_controller") or {}
    actions = pc.get("queue_actions_last_replan") or []
    enqueues = [a for a in actions if str(a).startswith("enqueue:")]

    ok = bool(data.get("is_running")) and int(data.get("active_workers") or 0) > 0
    print(
        json.dumps(
            {
                "ok": ok,
                "is_running": data.get("is_running"),
                "workers": data.get("active_workers"),
                "plan_generation": pc.get("plan_generation"),
                "branch": pc.get("last_tree_branch"),
                "queue_actions": actions,
                "enqueues": enqueues,
                "remote_owned": data.get("remote_owned_phases"),
                "popos_alive": (data.get("popos_phase_worker") or {}).get("alive"),
            },
            indent=2,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
