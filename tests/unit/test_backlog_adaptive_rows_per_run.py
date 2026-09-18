"""Monitor configured_rows_per_run must track persisted adaptive batch sizes."""

from __future__ import annotations

from unittest.mock import patch

from services.backlog_metrics import get_per_run_batch_size_for_phase


def test_graph_connection_rows_per_run_uses_persisted_adaptive_batch():
    with patch(
        "shared.adaptive_batch_policy.get_persisted_adaptive_batch",
        return_value=200,
    ):
        assert get_per_run_batch_size_for_phase("graph_connection_distillation") == 200


def test_entity_profile_rows_per_run_uses_persisted_adaptive_batch():
    with patch(
        "shared.adaptive_batch_policy.get_persisted_adaptive_batch",
        return_value=90,
    ):
        assert get_per_run_batch_size_for_phase("entity_profile_build") == 90
