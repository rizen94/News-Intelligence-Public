"""Unit tests for Monitor recent-activity merge (newest-first SSOT)."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

_PATH = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "domains"
    / "system_monitoring"
    / "routes"
    / "system_monitoring.py"
)


def _load_sm():
    spec = importlib.util.spec_from_file_location("system_monitoring_recent_test", _PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing full module (heavy imports / DB). Load only helpers by exec of sliced source.
    # Instead: import via package with DB mocked.
    import sys
    from unittest.mock import MagicMock

    sys.modules.setdefault("shared.database.connection", MagicMock())
    sys.modules.setdefault(
        "shared.domain_registry",
        MagicMock(
            get_active_domain_keys=lambda: ["politics"],
            get_pipeline_schema_names_active=lambda: ["politics"],
            get_schema_names_active=lambda: ["politics"],
            iter_pipeline_url_schema_pairs=lambda: [("politics", "politics")],
            iter_url_schema_pairs=lambda: [("politics", "politics")],
        ),
    )
    sys.modules.setdefault("shared.services.automation_run_history_writer", MagicMock())
    sys.modules.setdefault("shared.services.domain_aware_service", MagicMock())
    sys.modules.setdefault("shared.services.pipeline_trace_writer", MagicMock())
    sys.modules.setdefault("shared.services.response_cache", MagicMock(cached_response=lambda **k: (lambda f: f), cached_response_sync=lambda **k: (lambda f: f)))
    sys.modules.setdefault("config.runtime", MagicMock())
    sys.modules.setdefault("psutil", MagicMock())
    # collectors optional
    sys.modules.setdefault("rss_collector", MagicMock())
    spec.loader.exec_module(mod)
    return mod


def test_merge_recent_activity_prefers_newest_completed_at():
    sm = _load_sm()
    old = {
        "id": "mem:1",
        "task_name": "entity_organizer",
        "message": "stale",
        "completed_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
        "success": True,
    }
    new = {
        "id": "run_history:99",
        "task_name": "collision_sampling",
        "message": "fresh",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "success": True,
        "source": "automation_run_history",
    }
    mid = {
        "id": "mem:2",
        "task_name": "storyline_automation",
        "message": "mid",
        "completed_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
        "success": True,
    }
    merged = sm._merge_recent_activity_lists([old, mid], [new], limit=10)
    assert merged[0]["id"] == "run_history:99"
    assert merged[0]["message"] == "fresh"


def test_finalize_drops_stale_memory_recent(monkeypatch):
    sm = _load_sm()
    stale = {
        "id": "mem:old",
        "task_name": "spine_sql_tail",
        "message": "day old",
        "completed_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
        "success": True,
    }
    fresh_db = [
        {
            "id": "run_history:1",
            "task_name": "claim_extraction",
            "message": "Claim extraction",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "success": True,
            "source": "automation_run_history",
        }
    ]
    monkeypatch.setattr(sm, "_cached_recent_activities_from_run_history", lambda: fresh_db)
    out = sm._finalize_monitoring_activities_recent({"current": [], "recent": [stale]})
    ids = [r["id"] for r in out["recent"]]
    assert "run_history:1" in ids
    assert "mem:old" not in ids
