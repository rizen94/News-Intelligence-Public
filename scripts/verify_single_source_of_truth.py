#!/usr/bin/env python3
"""Fail if SSOT violations exist in unification-critical paths."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
WEB = ROOT / "web" / "src"

ALLOW_ENV = {
    API / "config" / "runtime.py",
    API / "config" / "settings.py",  # legacy; migrate incrementally
    API / "config" / "paths.py",
    API / "config" / "logging_config.py",
}

ALLOW_NRI_LITERAL = {
    API / "config" / "runtime.py",
    API / "config" / "investigation_tables.py",
    API / "database" / "migrations" / "237_investigation_schema_merge.sql",
    API / "services" / "nri_integration_service.py",
    API / "services" / "nri_bridge_qa_service.py",
    API / "services" / "nri_entity_claims_service.py",
}

# Paths that must be clean for unification cutover
CRITICAL_PATHS = (
    API / "nri_core",
    API / "config" / "runtime.py",
    API / "config" / "database_targets.py",
    API / "config" / "investigation_tables.py",
    API / "config" / "schedulers.yaml",
    API / "domains" / "intelligence_hub" / "routes" / "investigation.py",
    API / "services" / "automation",
    WEB / "config" / "apiRoutes.ts",
    WEB / "services" / "api" / "investigationApi.ts",
)

CRITICAL_VIOLATIONS: list[str] = []
LEGACY_WARNINGS: list[str] = []


def _is_critical(path: Path) -> bool:
    for crit in CRITICAL_PATHS:
        if path == crit or (crit.is_dir() and crit in path.parents):
            return True
    return False


def check_python_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    critical = _is_critical(path)
    bucket = CRITICAL_VIOLATIONS if critical else LEGACY_WARNINGS

    if path not in ALLOW_ENV and re.search(r"os\.environ\.get|os\.environ\[", text):
        if "config/runtime" not in str(path):
            bucket.append(f"os.environ in {path.relative_to(ROOT)}")
    if path not in ALLOW_NRI_LITERAL and re.search(r"\bnri\.", text):
        if "nri_core" not in str(path) and "migrations" not in str(path):
            bucket.append(f"nri. schema literal in {path.relative_to(ROOT)}")
    if "/opt/nri" in text and "UNIFICATION" not in text and "docs/" not in str(path):
        bucket.append(f"/opt/nri literal in {path.relative_to(ROOT)}")
    if re.search(r"127\.0\.0\.1:8010|localhost:8010", text):
        if path.name not in ("runtime.py", "settings.py"):
            bucket.append(f"NRI_API :8010 literal in {path.relative_to(ROOT)}")


def check_ts_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    if "apiRoutes.ts" in path.name:
        return
    critical = _is_critical(path)
    bucket = CRITICAL_VIOLATIONS if critical else LEGACY_WARNINGS
    if re.search(r"['\"]\/api\/nri\/", text) and "apiRoutes" not in text:
        bucket.append(f"hardcoded /api/nri in {path.relative_to(ROOT)}")


def main() -> int:
    for p in API.rglob("*.py"):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        check_python_file(p)
    for p in WEB.rglob("*.ts"):
        if "node_modules" in p.parts:
            continue
        check_ts_file(p)
    for p in WEB.rglob("*.tsx"):
        if "node_modules" in p.parts:
            continue
        check_ts_file(p)

    schedulers = API / "config" / "schedulers.yaml"
    if not schedulers.exists():
        CRITICAL_VIOLATIONS.append("missing api/config/schedulers.yaml")

    if LEGACY_WARNINGS:
        print(f"Legacy SSOT drift ({len(LEGACY_WARNINGS)} items, non-blocking):")
        for w in LEGACY_WARNINGS[:10]:
            print(f"  - {w}")
        if len(LEGACY_WARNINGS) > 10:
            print(f"  ... and {len(LEGACY_WARNINGS) - 10} more")

    if CRITICAL_VIOLATIONS:
        print("Critical SSOT violations:")
        for v in CRITICAL_VIOLATIONS:
            print(f"  - {v}")
        return 1

    print("SSOT check passed (critical paths clean)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
