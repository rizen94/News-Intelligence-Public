"""Content refinement auto-enqueue gates (isolated import)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

_API = (
    Path(__file__).resolve().parents[2]
    / "api"
    / "services"
    / "content_refinement_queue_service.py"
)

# Avoid services/__init__ and live DB on import.
sys.modules.setdefault("shared.database.connection", MagicMock())
sys.modules.setdefault("shared.domain_registry", MagicMock())
_rt = MagicMock()
_rt.env_str = lambda k, d="": d
_rt.env_bool = MagicMock(return_value=False)
_rt.env_int = MagicMock(return_value=0)
_rt.env_float = MagicMock(return_value=0.0)
_rt.env_pop = MagicMock()
_rt.env_set = MagicMock()
_rt.env_setdefault = MagicMock()
sys.modules["config.runtime"] = _rt

_spec = importlib.util.spec_from_file_location("content_refinement_auto_enqueue", _API)
assert _spec and _spec.loader
crq = importlib.util.module_from_spec(_spec)
sys.modules["content_refinement_auto_enqueue"] = crq
_spec.loader.exec_module(crq)


def test_auto_enqueue_disabled_by_default():
    with patch.object(
        crq,
        "env_str",
        side_effect=lambda k, d="": {
            "CONTENT_REFINEMENT_AUTO_ENQUEUE": "false",
            "CONTENT_REFINEMENT_API_ENQUEUE_ONLY": "true",
            "AUTO_ENQUEUE_COMPREHENSIVE_RAG": "1",
        }.get(k, d),
    ):
        assert crq.content_refinement_auto_enqueue_enabled() is False


def test_auto_enqueue_enabled_by_new_flag():
    with patch.object(
        crq,
        "env_str",
        side_effect=lambda k, d="": {
            "CONTENT_REFINEMENT_AUTO_ENQUEUE": "true",
            "CONTENT_REFINEMENT_API_ENQUEUE_ONLY": "true",
            "AUTO_ENQUEUE_COMPREHENSIVE_RAG": "0",
        }.get(k, d),
    ):
        assert crq.content_refinement_auto_enqueue_enabled() is True


def test_auto_enqueue_legacy_path_when_api_only_off():
    with patch.object(
        crq,
        "env_str",
        side_effect=lambda k, d="": {
            "CONTENT_REFINEMENT_AUTO_ENQUEUE": "false",
            "CONTENT_REFINEMENT_API_ENQUEUE_ONLY": "false",
            "AUTO_ENQUEUE_COMPREHENSIVE_RAG": "1",
        }.get(k, d),
    ):
        assert crq.content_refinement_auto_enqueue_enabled() is True


def test_min_articles_default():
    with patch.object(crq, "env_str", side_effect=lambda k, d="": d):
        assert crq.auto_enqueue_comprehensive_rag_min_articles() == 3
