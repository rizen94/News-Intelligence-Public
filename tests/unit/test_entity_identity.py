"""Unit tests for entity identity grain helpers."""

import importlib.util
import sys
from pathlib import Path

_API = Path(__file__).resolve().parents[2] / "api"
_PATH = _API / "shared" / "entity_identity.py"
_spec = importlib.util.spec_from_file_location("entity_identity", _PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
canonical_entity_id_to_profile_id = _mod.canonical_entity_id_to_profile_id


def test_canonical_to_profile_docstring_grain():
    """entity_positions.entity_id is canonical_entity_id — not profile id."""
    assert canonical_entity_id_to_profile_id.__doc__ is not None
    assert "entity_positions.entity_id" in canonical_entity_id_to_profile_id.__doc__
