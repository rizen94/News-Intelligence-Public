"""Unit tests for pulse scoring helpers."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

sys.modules.setdefault("services.automation_manager", MagicMock())
sys.modules.setdefault("services.advanced_monitoring_service", MagicMock())
sys.modules.setdefault("services.editorial_package_service", MagicMock())
sys.modules.setdefault("services.rag", MagicMock())
sys.modules.setdefault("services.rag.RAGService", MagicMock())

# Stub domain registry constants used at pulse import without hitting DB.
_reg = MagicMock()
_reg.get_pipeline_active_domain_keys = MagicMock(return_value=["politics", "finance"])
_reg.resolve_domain_schema = MagicMock(side_effect=lambda k: k.replace("-", "_"))
sys.modules["shared.domain_registry"] = _reg

from services.pulse_service import _score_item  # noqa: E402


def test_score_item_velocity_only():
    item = {"domain_key": "politics", "id": 1, "velocity": 4}
    score, bd = _score_item(item, lifecycle={}, new_episodes=set())
    assert score == 4.0
    assert bd["velocity"] == 4.0


def test_score_item_new_episode_bonus(monkeypatch):
    monkeypatch.setattr("services.pulse_service.pulse_bonus_new_episode", lambda: 2.0)
    item = {"domain_key": "politics", "id": 1, "velocity": 3}
    key = ("politics", 1)
    score, bd = _score_item(item, lifecycle={}, new_episodes={key})
    assert score == 5.0
    assert bd.get("new_episode") == 2.0


def test_score_item_lifecycle_active_bonus(monkeypatch):
    monkeypatch.setattr("services.pulse_service.pulse_bonus_lifecycle_active", lambda: 3.0)
    item = {"domain_key": "politics", "id": 2, "velocity": 1, "cross_domain_count": 1}
    score, bd = _score_item(item, lifecycle={("politics", 2): "activated"}, new_episodes=set())
    assert score == 4.0
    assert bd.get("lifecycle_active") == 3.0


def test_score_item_cross_domain_bonus(monkeypatch):
    monkeypatch.setattr("services.pulse_service.pulse_bonus_cross_domain", lambda: 1.5)
    item = {"domain_key": "finance", "id": 9, "velocity": 2, "cross_domain_count": 3}
    score, bd = _score_item(item, lifecycle={}, new_episodes=set())
    assert score == 3.5
    assert bd.get("cross_domain") == 1.5
