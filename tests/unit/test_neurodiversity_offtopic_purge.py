"""Unit tests for neurodiversity offtopic purge listing (no DB)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_API = Path(__file__).resolve().parents[2] / "api"
_MOD = _API / "services" / "neurodiversity_offtopic_purge_service.py"


def _load():
    spec = importlib.util.spec_from_file_location("nd_purge_under_test", _MOD)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gate_text_prefers_title_and_abstract():
    mod = _load()
    text = mod._gate_text("ADHD trial", "long body " * 100, "abstract autism")
    assert "ADHD trial" in text
    assert "abstract autism" in text
