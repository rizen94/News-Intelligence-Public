"""
Smoke test for context-centric pipeline (Phase 1–3).
Run from project root: PYTHONPATH=api python api/tests/test_context_centric_imports.py
No database required.
"""

import sys


def test_imports():
    """All context-centric modules and routes load without error."""
    from services.context_processor_service import (
        ensure_context_for_article,
        sync_domain_articles_to_contexts,
        link_context_to_article_entities,
        backfill_context_entity_mentions_for_domain,
    )
    from services.entity_profile_sync_service import sync_domain_entity_profiles
    from services.claim_extraction_service import (
        extract_claims_for_context,
        run_claim_extraction_batch,
        get_context_ids_without_claims,
    )
    from services.event_tracking_service import (
        ensure_tracked_event,
        add_chronicle_entry,
        run_event_tracking_batch,
    )
    from services.entity_profile_builder_service import (
        build_profile_sections,
        run_profile_builder_batch,
    )
    from services.pattern_recognition_service import (
        run_pattern_discovery,
        run_pattern_discovery_batch,
    )
    from config.context_centric_config import get_context_centric_config, is_context_centric_task_enabled

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
