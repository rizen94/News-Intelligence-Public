"""Dynamic import of archived service modules (relationship extraction, NRI shims)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ARCHIVED_SERVICES = Path(__file__).resolve().parents[1] / "_archived" / "services"


def _load_archived_service(submodule: str) -> ModuleType:
    path = _ARCHIVED_SERVICES / f"{submodule}.py"
    if not path.is_file():
        raise ImportError(f"Archived service missing: {path}")
    name = f"_archived_service_{submodule}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load archived service: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_relationship_extraction_service() -> ModuleType:
    return _load_archived_service("relationship_extraction_service")


def load_nri_integration_service() -> ModuleType:
    return _load_archived_service("nri_integration_service")


def load_nri_bridge_qa_service() -> ModuleType:
    return _load_archived_service("nri_bridge_qa_service")


def load_nri_entity_claims_service() -> ModuleType:
    return _load_archived_service("nri_entity_claims_service")
