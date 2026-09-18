#!/usr/bin/env python3
"""
CI: importing a module must not open a database connection.

``shared/domain_registry`` used to compute ``ACTIVE_DOMAIN_KEYS`` at module scope, so every process
that imported anything reaching it — the API, PopOS phase workers, every CLI script, the ``*/15``
cron, pytest collection — initialised the reserved UI pool and ran a query just to finish an import,
and could not import at all without DB credentials. Nothing in the source text makes that obvious,
so this checks it the only reliable way: patch ``psycopg2.connect`` to record its caller, then import
every module and see who tried.

    PYTHONPATH=api python3 scripts/verify_no_import_time_db.py [--verbose]

Exit 0 when no module connects at import; 1 otherwise. Modules that fail to import for unrelated
reasons are reported but do not fail the check — use pytest for that.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
sys.path.insert(0, str(API))

# (directory under api/, import package prefix)
SCAN_ROOTS: tuple[tuple[str, str], ...] = (
    ("services", "services"),
    ("shared", "shared"),
    ("config", "config"),
    ("domains", "domains"),
)

SKIP_PARTS = frozenset({"__pycache__", "_archived", "tests"})
# Editor/agent debris such as api/services/<name>.py.tmp/ is gitignored but still on disk, and its
# directory name is not a valid module path.
SKIP_SUFFIXES = (".tmp", ".bak", ".orig", ".temp")


def _module_names() -> list[str]:
    names: list[str] = []
    for subdir, package in SCAN_ROOTS:
        base = API / subdir
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_PARTS & set(path.parts) or path.name == "__init__.py":
                continue
            if any(part.endswith(SKIP_SUFFIXES) for part in path.parts):
                continue
            rel = path.relative_to(base).with_suffix("")
            names.append(package + "." + ".".join(rel.parts))
    return names


def main_cli() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="list modules that failed to import")
    args = parser.parse_args()

    logging.disable(logging.CRITICAL)
    import psycopg2

    offenders: dict[str, int] = {}
    current = {"module": "<none>"}

    def _spy(*_a, **_kw):
        offenders[current["module"]] = offenders.get(current["module"], 0) + 1
        raise psycopg2.OperationalError("blocked by verify_no_import_time_db")

    psycopg2.connect = _spy

    modules = _module_names()
    import_failures: list[tuple[str, str]] = []
    for name in modules:
        current["module"] = name
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 — a failing import is not this check's concern
            if name not in offenders:
                import_failures.append((name, f"{type(exc).__name__}: {exc}"))

    print(f"modules scanned: {len(modules)}")
    print(f"import failed for unrelated reasons: {len(import_failures)}")
    if args.verbose:
        for name, err in import_failures:
            print(f"    {name}: {err[:140]}")

    if offenders:
        print(f"\nModules opening a DB connection at import: {len(offenders)}")
        for name, count in sorted(offenders.items()):
            print(f"  - {name} ({count} connect call{'s' if count > 1 else ''})")
        print(
            "\nMove the work into a function (and cache it if it is hot). See "
            "shared/domain_registry.py for the lazy PEP 562 pattern."
        )
        return 1

    print("No import-time DB connections")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
