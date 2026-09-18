"""Unit tests for storyline assembly metrics honesty and residual scheduling."""

from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


def _import_sas():
    """Import assembly service with DB connection stubbed (no live Postgres)."""
    # Clear cached modules that pull domain_registry at import.
    for key in list(sys.modules):
        if key in (
            "services.storyline_assembly_service",
            "storyline_assembly_service_test",
        ) or key.endswith("storyline_assembly_service"):
            del sys.modules[key]

    with patch(
        "shared.database.connection.get_ui_db_connection",
        return_value=None,
    ), patch(
        "shared.database.connection.get_db_connection",
        return_value=None,
    ):
        # Ensure domain_registry uses YAML fallback (no DB).
        if "shared.domain_registry" in sys.modules:
            import shared.domain_registry as dr

            importlib.reload(dr)
        import services.storyline_assembly_service as sas

        return sas


def test_automation_counts_only_auto_approve_as_linked(monkeypatch):
    monkeypatch.setenv("STORYLINE_ASSEMBLY_FORCE_REFRESH", "true")
    monkeypatch.setenv("STORYLINE_ASSEMBLY_AUTOMATION_LIMIT", "10")
    sas = _import_sas()

    class _Svc:
        def __init__(self, domain: str) -> None:
            self.domain = domain

        async def discover_articles_for_storyline(self, sid, force_refresh=False):
            assert force_refresh is True
            if sid == 1:
                return {
                    "success": True,
                    "mode": "auto_approve",
                    "articles_found": 3,
                    "articles_added": 2,
                    "articles": [{"id": 1}, {"id": 2}, {"id": 3}],
                }
            return {
                "success": True,
                "mode": "suggest_only",
                "articles_found": 5,
                "articles_suggested": 5,
                "articles": [{"id": i} for i in range(5)],
            }

    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_cur.fetchall.return_value = [(1, "auto_approve"), (2, "suggest_only")]

    with (
        patch.object(sas, "count_unlinked_articles", side_effect=[10, 8]),
        patch.object(sas, "resolve_domain_schema", return_value="politics"),
        patch.object(sas, "get_db_connection_context") as mock_ctx,
        patch(
            "services.storyline_automation_service.StorylineAutomationService",
            _Svc,
        ),
        patch(
            "shared.services.phase_batch_run_history.record_phase_batch_completion_async",
            new_callable=AsyncMock,
        ),
    ):
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)
        out = asyncio.run(
            sas.run_storyline_assembly_for_domain(
                "politics",
                run_proactive=False,
                run_discovery=False,
                run_automation=True,
            )
        )

    auto = out["steps"]["storyline_automation"]
    assert auto["articles_linked"] == 2
    assert auto["articles_added"] == 2
    assert auto["articles_suggested"] == 5
    assert auto["articles_matched"] == 8
    assert out["articles_linked"] == 2


def test_residual_assembly_threshold_helper(monkeypatch):
    with patch("shared.database.connection.get_ui_db_connection", return_value=None):
        if "services.pipeline_controller" in sys.modules:
            import services.pipeline_controller as pc

            importlib.reload(pc)
        else:
            import services.pipeline_controller as pc
        assert pc.residual_assembly_pending_threshold() >= 25
