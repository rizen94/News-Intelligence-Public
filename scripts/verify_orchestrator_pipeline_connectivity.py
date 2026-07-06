#!/usr/bin/env python3
"""
Audit orchestrator ↔ automation pipeline connectivity (no DB required).

  PYTHONPATH=api python3 scripts/verify_orchestrator_pipeline_connectivity.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "api" / ".env", override=False)
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

import importlib.util

_pcs_path = ROOT / "api" / "services" / "pipeline_conductor_service.py"
_spec = importlib.util.spec_from_file_location("pipeline_conductor_service", _pcs_path)
assert _spec and _spec.loader
pcs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcs)

get_conductor_config = pcs.get_conductor_config
get_effective_processing_phases = pcs.get_effective_processing_phases
get_post_collection_kickoff_phases = pcs.get_post_collection_kickoff_phases
orchestrator_post_collection_kickoff_enabled = pcs.orchestrator_post_collection_kickoff_enabled
conductor_pipeline_modes = pcs.conductor_pipeline_modes
phase_conductor_scheduling_suppressed = pcs.phase_conductor_scheduling_suppressed


def _schedule_keys() -> set[str]:
    text = (ROOT / "api" / "services" / "automation_manager.py").read_text()
    block = text.split("self.schedules = {", 1)[1].split("\n        }\n", 1)[0]
    keys: set[str] = set()
    for m in re.finditer(r'"([a-z][a-z0-9_]*)":\s*\{', block):
        keys.add(m.group(1))
    return keys


def _dispatch_keys() -> set[str]:
    text = (ROOT / "api" / "services" / "automation_manager.py").read_text()
    return set(re.findall(r'(?:if|elif) task\.name == "([a-z][a-z0-9_]*)"', text))


def main() -> int:
    schedules = _schedule_keys()
    dispatch = _dispatch_keys()
    governor = set(get_effective_processing_phases().keys())
    kickoff = get_post_collection_kickoff_phases()
    modes = conductor_pipeline_modes()

    conductor_suppressed_in_governor = sorted(
        p for p in governor if phase_conductor_scheduling_suppressed(p)
    )
    kickoff_suppressed = sorted(p for p in kickoff if phase_conductor_scheduling_suppressed(p))

    missing_dispatch = sorted(schedules - dispatch - {"processing_history"})
    governor_not_scheduled = sorted(governor - schedules)
    scheduled_not_governor = sorted(
        schedules
        - governor
        - {
            "collection_cycle",
            "health_check",
            "cache_cleanup",
            "data_cleanup",
            "pending_db_flush",
            "embeddings_worker",
            "macro_series_refresh",
            "external_events_sync",
            "sanctions_refresh",
            "arc_report_generation",
            "longitudinal_matview_refresh",
            "digest_generation",
        }
    )

    report = {
        "conductor": get_conductor_config(),
        "pipeline_modes": modes,
        "post_collection_kickoff": orchestrator_post_collection_kickoff_enabled(),
        "post_collection_phases": kickoff,
        "schedule_count": len(schedules),
        "dispatch_count": len(dispatch),
        "governor_phase_count": len(governor),
        "missing_dispatch_handlers": missing_dispatch,
        "governor_phases_not_in_schedules": governor_not_scheduled,
        "schedules_without_governor_entry": scheduled_not_governor,
        "conductor_suppressed_still_in_governor": conductor_suppressed_in_governor,
        "kickoff_phases_suppressed": kickoff_suppressed,
        "ok": not missing_dispatch
        and not conductor_suppressed_in_governor
        and not kickoff_suppressed,
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
