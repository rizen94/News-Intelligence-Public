"""Unit tests for narrative magnet framing / signature / title-anchor gates."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock


_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"
_PRUNE = _API / "services" / "storyline_core_prune_service.py"


def _load_prune_helpers():
    """Load distinctive_title_anchors / member_matches_title_anchor without DB."""
    rt = ModuleType("config.runtime")
    rt.env_int = lambda _k, default=0: int(default)
    rt.env_float = lambda _k, default=0.0: float(default)
    rt.env_bool = lambda _k, default=False: bool(default)
    rt.env_str = lambda _k, default="": str(default)
    sys.modules["config.runtime"] = rt
    for name in (
        "shared.database.connection",
        "shared.domain_registry",
        "shared.storyline_article_counts",
        "shared.membership_ops_freeze",
        "shared.membership_store",
        "services.domain_synthesis_config",
    ):
        sys.modules.setdefault(name, MagicMock())

    name = "storyline_core_prune_framing_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _PRUNE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.path.insert(0, str(_API))
    spec.loader.exec_module(mod)
    return mod


def test_title_anchor_rejects_offtopic_member():
    prune = _load_prune_helpers()
    anchors = prune.distinctive_title_anchors("Ann Widdecombe murder charge in Devon")
    assert "widdecombe" in anchors or "murder" in anchors
    assert prune.member_matches_title_anchor(
        anchors, "Ann Widdecombe murder suspect charged in Devon", {"ann widdecombe"}
    )
    # Unrelated politics piece sharing no title anchors
    assert not prune.member_matches_title_anchor(
        anchors, "Nigel Farage Reform UK election rally in Clacton", {"nigel farage"}
    )


def test_metadata_prompt_has_role_neutrality():
    src = (_API / "services" / "storyline_coherence_guardrails.py").read_text(
        encoding="utf-8"
    )
    assert "Role neutrality" in src
    assert "over-electionize" in src


def test_signature_fallback_requires_two_hits():
    src = (_API / "services" / "storyline_automation_service.py").read_text(
        encoding="utf-8"
    )
    assert "hits >= 2" in src


def test_headline_refiner_forbids_role_inversion():
    src = (_API / "services" / "storyline_narrative_finisher_service.py").read_text(
        encoding="utf-8"
    )
    assert "Never invert victim and suspect" in src
