"""
Smoke test for context-centric pipeline (Phase 1–3).
Run from project root: PYTHONPATH=api python api/tests/test_context_centric_imports.py
No database required.
"""

import sys


def test_imports():
    """All context-centric modules and routes load without error."""
    from config.context_centric_config import (
        get_context_centric_config,
        is_context_centric_task_enabled,
    )

    cfg = get_context_centric_config()
    assert "tasks" in cfg
    for task in ("context_sync", "claim_extraction", "pattern_recognition"):
        assert is_context_centric_task_enabled(task) in (True, False)
    return True


def test_routes_register():
    """Context-centric router and endpoints exist."""
    from domains.intelligence_hub.routes.context_centric import router

    routes = [r.path for r in router.routes if hasattr(r, "path")]
    assert "/entity_profiles" in str(routes) or any("entity_profiles" in r for r in routes)
    assert "context_centric" in str(routes) or any("context_centric" in r for r in routes)
    return True


if __name__ == "__main__":
    ok = True
    try:
        test_imports()
        print("PASS: context-centric imports")
    except Exception as e:
        print(f"FAIL: imports — {e}")
        ok = False
    try:
        test_routes_register()
        print("PASS: context-centric routes registered")
    except Exception as e:
        print(f"FAIL: routes — {e}")
        ok = False
    sys.exit(0 if ok else 1)
