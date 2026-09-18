"""Pulse include allowlist helpers (fail-closed + domain filter)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_SVC = _API / "services" / "pulse_service.py"


def _load_pulse():
    # Lightweight stubs so pulse_service imports without DB.
    for name in (
        "shared.database.connection",
        "shared.domain_registry",
        "config.runtime",
        "services.editorial_package_service",
    ):
        if name not in sys.modules:
            sys.modules[name] = MagicMock()

    rt = sys.modules["config.runtime"]
    rt.pulse_bonus_cross_domain = lambda: 1.0
    rt.pulse_bonus_lifecycle_active = lambda: 1.0
    rt.pulse_bonus_new_episode = lambda: 1.0
    rt.pulse_bonus_reactivation = lambda: 1.0
    rt.pulse_default_limit = lambda: 20
    rt.pulse_default_window_hours = lambda: 48
    rt.pulse_stubs_enabled = lambda: False
    rt.pulse_stubs_top_n = lambda: 3

    reg = sys.modules["shared.domain_registry"]
    reg.get_pipeline_active_domain_keys = lambda: ["politics", "neurodiversity"]
    reg.resolve_domain_schema = lambda dk: dk.replace("-", "_")

    sys.path.insert(0, str(_API))
    name = "pulse_service_gate_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SVC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_filter_pulse_items_neurodiversity_allowlist():
    pulse = _load_pulse()
    items = [
        {
            "domain_key": "neurodiversity",
            "title": "ADHD medication trial",
            "movement_summary": [],
        },
        {
            "domain_key": "neurodiversity",
            "title": "Hippocampal theta oscillations",
            "movement_summary": [],
        },
        {
            "domain_key": "politics",
            "title": "Election update",
            "movement_summary": [],
        },
    ]
    filtered = pulse._filter_pulse_items(items, domain_filter="neurodiversity")
    titles = [i["title"] for i in filtered]
    assert "ADHD medication trial" in titles
    assert "Hippocampal theta oscillations" not in titles
    assert "Election update" not in titles


def test_passes_include_gate_fail_closed_on_error():
    pulse = _load_pulse()
    item = {"domain_key": "neurodiversity", "title": "ADHD", "movement_summary": []}
    fake = ModuleType("services.domain_synthesis_config")

    def boom(*_a, **_k):
        raise RuntimeError("cfg")

    fake.get_domain_synthesis_config = boom
    with patch.dict(sys.modules, {"services.domain_synthesis_config": fake}):
        assert pulse._passes_domain_include_gate(item, domain_key="neurodiversity") is False


def test_item_passes_gates_before_score_shape():
    pulse = _load_pulse()
    ok = {
        "domain_key": "neurodiversity",
        "title": "Autism cohort study",
        "movement_summary": [],
    }
    bad = {
        "domain_key": "neurodiversity",
        "title": "General neuroscience preprint",
        "movement_summary": [],
    }
    assert pulse._item_passes_pulse_domain_gates(ok, domain_filter="neurodiversity")
    assert not pulse._item_passes_pulse_domain_gates(bad, domain_filter="neurodiversity")
