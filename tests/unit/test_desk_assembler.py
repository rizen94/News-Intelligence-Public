"""Unit tests for continuous desk assembler (promote gate, editorial merge, vault investigation)."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

_ROOT = Path(__file__).resolve().parents[2]
_DESK = _ROOT / "api" / "services" / "desk_promotion_service.py"
_VAULT = _ROOT / "api" / "services" / "vault_bridge_service.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        del sys.modules[name]
    sys.modules.setdefault("shared.database.connection", MagicMock())
    sys.modules.setdefault(
        "shared.domain_registry",
        MagicMock(resolve_domain_schema=lambda k: k.replace("-", "_")),
    )
    _rt = MagicMock()
    _rt.env_str = lambda k, d="": os.environ.get(k, d)
    _rt.env_bool = lambda k, d=False: (
        os.environ.get(k, str(d)).lower() in ("1", "true", "yes")
        if k in os.environ
        else d
    )
    sys.modules["config.runtime"] = _rt
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_merge_editorial_document_preserves_keys():
    desk = _load("desk_promo_merge", _DESK)
    existing = {"lede": "old", "who": ["A"], "analysis": "keep"}
    patch = {"lede": "new", "why": "because"}
    merged = desk.merge_editorial_document(
        existing,
        patch,
        provenance={"source": "desk_agent", "vault_path": "20_Investigations/inv-x.md"},
    )
    assert merged["lede"] == "new"
    assert merged["who"] == ["A"]
    assert merged["analysis"] == "keep"
    assert merged["why"] == "because"
    assert merged["desk_provenance"]["source"] == "desk_agent"
    assert "inv-x" in merged["desk_provenance"]["vault_path"]


def test_validate_promote_gate_rejects_wrong_status():
    desk = _load("desk_promo_gate", _DESK)
    errors = desk.validate_promote_gate(
        frontmatter={"status": "open", "tracked_event_id": 1},
        body="x" * 80,
        editor_approved=False,
        editor_rationale="Looks solid after skeptic review",
    )
    assert "status_must_be_ready_to_promote_or_editor_approved" in errors


def test_validate_promote_gate_accepts_editor_approved():
    desk = _load("desk_promo_gate2", _DESK)
    errors = desk.validate_promote_gate(
        frontmatter={"status": "open", "tracked_event_id": 55, "domain_key": "finance"},
        body="x" * 80,
        editor_approved=True,
        editor_rationale="Operator asked to publish after review",
    )
    assert errors == []


def test_validate_promote_gate_needs_anchors():
    desk = _load("desk_promo_gate3", _DESK)
    errors = desk.validate_promote_gate(
        frontmatter={"status": "ready_to_promote"},
        body="x" * 80,
        editor_approved=False,
        editor_rationale="Enough rationale here",
    )
    assert "need_tracked_event_id_or_storyline_id_plus_domain_key" in errors


def test_validate_promote_gate_storyline_needs_domain():
    desk = _load("desk_promo_gate4", _DESK)
    errors = desk.validate_promote_gate(
        frontmatter={"status": "ready_to_promote", "storyline_id": 9},
        body="x" * 80,
        editor_approved=False,
        editor_rationale="Enough rationale here",
    )
    assert "need_tracked_event_id_or_storyline_id_plus_domain_key" in errors
    assert "domain_key_required_with_storyline_id" in errors


def test_write_investigation_note_tmpdir(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_INTEL_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("NEWS_INTEL_VAULT_WRITE", "true")
    vault = _load("vault_inv_write", _VAULT)
    result = vault.write_investigation_note(
        {
            "title": "payment-rail-inquiry",
            "tracked_event_id": 55,
            "domain_key": "finance",
            "hypotheses": [
                {"id": "H1", "statement": "State actor", "support": ["c1"], "contradict": []},
                {"id": "H2", "statement": "Fraud ring", "support": [], "contradict": ["c2"]},
            ],
            "confidence": 0.6,
            "rationale": "Contested claims around payment rails",
        }
    )
    assert result.get("ok") is True
    assert result["path"].startswith("20_Investigations/inv-")
    note = vault.read_vault_note(result["path"])
    assert note.get("ok") is True
    fm = note["frontmatter"]
    assert str(fm.get("tracked_event_id")) in ("55", 55)
    assert fm.get("domain_key") == "finance"
    assert fm.get("status") == "open"
    assert "H1" in note["body"]
    assert "Competing hypotheses" in note["body"]


def test_write_investigation_note_rejects_missing_anchor(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_INTEL_VAULT_PATH", str(tmp_path))
    monkeypatch.setenv("NEWS_INTEL_VAULT_WRITE", "true")
    vault = _load("vault_inv_miss", _VAULT)
    result = vault.write_investigation_note({"title": "orphan", "rationale": "no anchors"})
    assert result.get("ok") is False
    assert result.get("error") == "missing_anchor"
