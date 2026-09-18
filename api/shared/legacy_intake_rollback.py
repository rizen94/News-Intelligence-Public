"""Dynamic import of archived legacy intake modules when LEGACY_INTAKE_EXTRACTION_ENABLED=true."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

_ARCHIVED_INTAKE = Path(__file__).resolve().parents[1] / "_archived" / "intake"


def legacy_intake_rollback_active() -> bool:
    from config.settings import legacy_intake_extraction_enabled

    return legacy_intake_extraction_enabled()


def _load_archived_module(submodule: str) -> ModuleType:
    path = _ARCHIVED_INTAKE / f"{submodule}.py"
    if not path.is_file():
        raise ImportError(f"Archived intake module missing: {path}")
    name = f"_archived_intake_{submodule}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load archived module: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_entity_extraction_runner() -> ModuleType:
    return _load_archived_module("entity_extraction_runner")


def load_event_extraction_runner() -> ModuleType:
    return _load_archived_module("event_extraction_runner")


def load_metadata_enrichment_service() -> ModuleType:
    return _load_archived_module("metadata_enrichment_service")


def load_ml_processing_service() -> ModuleType:
    return _load_archived_module("ml_processing_service")
