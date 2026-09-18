"""Attach caps + membership_min_shared_non_hub per domain (chemistry vs narrative)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock


_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"


def _load_dsc():
    path = _API / "services" / "domain_synthesis_config.py"
    spec = importlib.util.spec_from_file_location("dsc_caps_under_test", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.reload_config()
    return mod


def _load_attach_caps(dsc_mod):
    sys.modules["services.domain_synthesis_config"] = dsc_mod
    # storyline_attach_caps imports config.runtime
    rt = ModuleType("config.runtime")
    rt.env_int = lambda _k, default=0: int(default)
    sys.modules["config.runtime"] = rt
    path = _API / "shared" / "storyline_attach_caps.py"
    name = "storyline_attach_caps_under_test"
    if name in sys.modules:
        del sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # Ensure package path resolution works when imported as shared.*
    sys.path.insert(0, str(_API))
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_membership_min_shared_chemistry_vs_narrative():
    dsc = _load_dsc()
    # Narrative magnets and chemistry both require ≥2 non-hub durable overlap.
    assert dsc.get_domain_synthesis_config("politics").membership_min_shared_non_hub() == 2
    assert dsc.get_domain_synthesis_config("finance").membership_min_shared_non_hub() == 2
    assert dsc.get_domain_synthesis_config("legal").membership_min_shared_non_hub() == 2
    assert dsc.get_domain_synthesis_config("medicine").membership_min_shared_non_hub() == 2
    assert (
        dsc.get_domain_synthesis_config("artificial-intelligence").membership_min_shared_non_hub()
        == 2
    )
    assert dsc.get_domain_synthesis_config("neurodiversity").membership_min_shared_non_hub() == 2


def test_narrative_oversize_needs_prune():
    dsc = _load_dsc()
    caps = _load_attach_caps(dsc)
    assert caps.narrative_oversize_needs_prune("politics", 81) is True
    assert caps.narrative_oversize_needs_prune("politics", 40) is False
    assert caps.narrative_oversize_needs_prune("medicine", 200) is False



def test_attach_hard_cap_per_domain():
    dsc = _load_dsc()
    caps = _load_attach_caps(dsc)
    assert caps.attach_hard_cap("legal") == 48
    assert caps.attach_hard_cap("medicine") == 48
    assert caps.attach_hard_cap("artificial-intelligence") == 48
    assert caps.attach_hard_cap("neurodiversity") == 32
    # Narrative domains use HITL default (~150), not chemistry 48
    assert caps.attach_hard_cap("politics") >= 100
    assert caps.attach_hard_cap("finance") >= 100


def test_storyline_at_or_over_attach_cap():
    dsc = _load_dsc()
    caps = _load_attach_caps(dsc)
    assert caps.storyline_at_or_over_attach_cap("medicine", 48) is True
    assert caps.storyline_at_or_over_attach_cap("medicine", 47) is False
    assert caps.storyline_at_or_over_attach_cap("neurodiversity", 32) is True
