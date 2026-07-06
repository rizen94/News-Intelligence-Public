#!/usr/bin/env python3
"""CI: validate feature registry consistency with schedulers and replacement graph."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "api"
sys.path.insert(0, str(API))

ERRORS: list[str] = []


def _error(msg: str) -> None:
    ERRORS.append(msg)


def _check_replacement_graph() -> None:
    from config.feature_registry import get_feature_registry

    reg = get_feature_registry()
    for key, entry in reg.items():
        replaced_by = entry.get("replaced_by")
        if not replaced_by:
            continue
        successor = reg.get(str(replaced_by))
        if not successor:
            _error(f"{key}: replaced_by={replaced_by} not in registry")
            continue
        if successor.get("lifecycle") not in ("incorporated", "staged"):
            _error(
                f"{key}: successor {replaced_by} lifecycle={successor.get('lifecycle')} "
                "(expected incorporated or staged)"
            )
        for rep in entry.get("replaces") or []:
            if rep not in reg:
                _error(f"{key}: replaces unknown feature {rep}")


def _check_incorporated_enabled() -> None:
    from config.feature_registry import get_feature_registry, is_feature_enabled

    for key, entry in get_feature_registry().items():
        if entry.get("lifecycle") != "incorporated":
            continue
        if not is_feature_enabled(key) and not entry.get("env_override"):
            flags = entry.get("flags") or {}
            if flags.get("env") or flags.get("yaml"):
                continue
            _error(f"{key}: incorporated but runtime disabled without env override")


def _check_scheduler_phases() -> None:
    import yaml
    from config.feature_registry import get_feature_registry
    from config.paths import CONFIG_DIR

    reg = get_feature_registry()
    phase_names = {v.get("phase_name") for v in reg.values() if v.get("phase_name")}
    path = CONFIG_DIR / "schedulers.yaml"
    manifest = {}
    if path.is_file():
        manifest = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schedulers = manifest.get("schedulers") or {}
    for name, entry in schedulers.items():
        if not isinstance(entry, dict) or not entry.get("enabled", True):
            continue
        if name in (
            "health_check",
            "collection_cycle",
            "rss_feed_health",
            "automation_manager",
            "orchestrator_coordinator",
            "newsplatform_secondary",
            "widow_db_adjacent_cron",
            "widow_tracking_discovery_cron",
            "nri_mention_resolver_timer",
            "nri_loop_timer",
            "nri_api",
        ):
            continue
        if name not in reg and name not in phase_names:
            _error(f"schedulers.yaml key {name!r} has no features.yaml entry")


def _check_acyclic_replaces() -> None:
    from config.feature_registry import get_feature_registry

    reg = get_feature_registry()

    def visit(key: str, trail: set[str]) -> None:
        if key in trail:
            _error(f"replacement cycle detected: {' -> '.join(trail)} -> {key}")
            return
        entry = reg.get(key) or {}
        nxt = entry.get("replaced_by")
        if nxt:
            visit(str(nxt), trail | {key})

    for key in reg:
        visit(key, set())


def main() -> int:
    _check_replacement_graph()
    _check_incorporated_enabled()
    _check_scheduler_phases()
    _check_acyclic_replaces()
    if ERRORS:
        print("verify_feature_registry FAILED:")
        for e in ERRORS:
            print(f"  - {e}")
        return 1
    print("verify_feature_registry OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
