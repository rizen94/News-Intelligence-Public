"""Unit tests for narrative finisher ---JSON--- marker parsing."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_API = _ROOT / "api"

sys.path.insert(0, str(_API))

sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
sys.modules.setdefault("shared.services.ollama_model_caller", MagicMock())
sys.modules.setdefault("shared.services.ollama_model_policy", MagicMock())
_ollama_pol = sys.modules["shared.services.ollama_model_policy"]
_ollama_pol.InvocationKind = MagicMock()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_finisher = _load(
    "storyline_narrative_finisher_service",
    _API / "services" / "storyline_narrative_finisher_service.py",
)
parse_finisher_response = _finisher.parse_finisher_response
parse_headline_refiner_response = _finisher.parse_headline_refiner_response


_SAMPLE_JSON = (
    '{\n'
    '  "lede": "Nepal protests escalate.",\n'
    '  "narrative": "Good Nepal body text.",\n'
    '  "key_developments": ["Event A"]\n'
    "}"
)


def test_parse_finisher_exact_marker():
    raw = f"Prose above.\n---JSON---\n{_SAMPLE_JSON}"
    data, err = parse_finisher_response(raw)
    assert err is None
    assert data is not None
    assert data["lede"] == "Nepal protests escalate."
    assert "Nepal" in data["narrative"]


def test_parse_finisher_newline_inside_marker():
    """Regression: model emitted ---\\nJSON--- instead of ---JSON---."""
    raw = f"Prose above.\n---\nJSON---\n{_SAMPLE_JSON}"
    data, err = parse_finisher_response(raw)
    assert err is None, f"expected success, got {err}"
    assert data is not None
    assert data["narrative"] == "Good Nepal body text."


def test_parse_finisher_spaced_and_case_variants():
    raw = f"Intro\n--- json ---\n{_SAMPLE_JSON}"
    data, err = parse_finisher_response(raw)
    assert err is None
    assert data is not None
    assert data["key_developments"] == ["Event A"]


def test_parse_finisher_missing_marker():
    data, err = parse_finisher_response('{"lede": "x"}')
    assert data is None
    assert err == "no_json_marker"


def test_parse_headline_refiner_newline_marker():
    raw = 'Draft\n---\nJSON---\n{"title": "Polished", "description": "One line"}'
    data, err = parse_headline_refiner_response(raw)
    assert err is None
    assert data == {"title": "Polished", "description": "One line"}
