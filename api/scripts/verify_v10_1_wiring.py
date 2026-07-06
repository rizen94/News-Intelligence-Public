#!/usr/bin/env python3
"""Post-prune wiring audit for v10.1 deploy (no API server required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_API = Path(__file__).resolve().parent.parent
_ROOT = _API.parent
sys.path.insert(0, str(_API))

ARCHIVED_SCRIPT_SHIMS = (
    "run_extraction_burn_down.py",
    "run_event_extraction_catchup.py",
    "run_entity_extraction_catchup.py",
    "report_metadata_enrichment_status.py",
)

ARCHIVED_MODULES = (
    "_archived/intake/entity_extraction_runner.py",
    "_archived/intake/event_extraction_runner.py",
    "_archived/automation/retired_phase_handlers.py",
    "_archived/services/relationship_extraction_service.py",
)


def main() -> int:
    issues: list[str] = []
    ok: list[str] = []

    for name in ARCHIVED_SCRIPT_SHIMS:
        shim = _API / "scripts" / name
        target = _API / "_archived" / "scripts" / name
        if not shim.is_file():
            issues.append(f"missing shim api/scripts/{name}")
        elif not target.is_file():
            issues.append(f"shim target missing api/_archived/scripts/{name}")
        else:
            ok.append(f"shim api/scripts/{name}")

    for rel in ARCHIVED_MODULES:
        if not (_API / rel).is_file():
            issues.append(f"missing archived module {rel}")
        else:
            ok.append(rel)

    for loader in (
        "shared/legacy_intake_rollback.py",
        "shared/retired_phase_dispatch.py",
        "shared/archived_services_loader.py",
    ):
        if not (_API / loader).is_file():
            issues.append(f"missing loader {loader}")
        else:
            ok.append(loader)

    if (_ROOT / "scripts" / "ni_review").is_dir():
        issues.append("scripts/ni_review/ still present (prune incomplete)")

    try:
        from shared.pipeline_resource_policy import configure_pipeline_resources

        configure_pipeline_resources()
    except Exception as e:
        issues.append(f"configure_pipeline_resources failed: {e}")

    try:
        from shared.assembly_phase_order import assembly_pipeline_mode
        from shared.spine_phase_order import spine_pipeline_mode

        spine = spine_pipeline_mode()
        assembly = assembly_pipeline_mode()
        if spine != "ordered" or assembly != "ordered":
            issues.append(
                f"conductor modes spine={spine} assembly={assembly} (v10.1 prod expects ordered/ordered)"
            )
        else:
            ok.append("conductor modes ordered")
    except Exception as e:
        issues.append(f"conductor mode check failed: {e}")

    report = {"ok": ok, "issues": issues, "passed": not issues}
    print(json.dumps(report, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
