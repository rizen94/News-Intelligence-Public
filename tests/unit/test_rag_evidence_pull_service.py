"""Unit tests for selective RAG evidence pull helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_rag_module():
    path = (
        Path(__file__).resolve().parents[2]
        / "api"
        / "services"
        / "rag_evidence_pull_service.py"
    )
    spec = importlib.util.spec_from_file_location("rag_evidence_pull_service", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_parse_arxiv_id_from_abs_url():
    m = _load_rag_module()
    assert m.parse_arxiv_id("https://arxiv.org/abs/2401.12345") == "2401.12345"
    assert m.parse_arxiv_id("https://arxiv.org/pdf/2401.12345.pdf") == "2401.12345"
    assert m.parse_arxiv_id("arxiv:2401.12345v2") == "2401.12345"


def test_parse_arxiv_id_none():
    m = _load_rag_module()
    assert m.parse_arxiv_id(None) is None
    assert m.parse_arxiv_id("https://example.com/paper") is None
