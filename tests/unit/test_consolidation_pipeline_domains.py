"""Consolidation uses the same domain scope as discovery/proactive."""

from unittest.mock import patch

from services.storyline_consolidation_service import StorylineConsolidationService


def test_run_all_domains_uses_pipeline_keys():
    svc = StorylineConsolidationService(db_config={})
    with patch(
        "services.storyline_consolidation_service.get_pipeline_active_domain_keys",
        return_value=("medicine", "legal"),
    ), patch.object(svc, "run_consolidation", return_value={"merges_performed": 0}) as run:
        out = svc.run_all_domains()
    assert set(out["domains"].keys()) == {"medicine", "legal"}
    assert run.call_count == 2
