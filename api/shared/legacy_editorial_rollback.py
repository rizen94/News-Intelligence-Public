"""Dynamic import of archived legacy editorial writers when enabled.

Default: disabled for v11 local (set LEGACY_EDITORIAL_WRITERS_ENABLED=1 to rollback).
Widow prod may keep EDITORIAL_ROOM_LOOP_ENABLED=true until cutover; the loop shim
still loads archived code when that flag (or LEGACY_EDITORIAL_WRITERS_ENABLED) is on.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

from config.runtime import env_str

logger = logging.getLogger(__name__)

_ARCHIVED_EDITORIAL = Path(__file__).resolve().parents[1] / "_archived" / "editorial"


def legacy_editorial_writers_enabled() -> bool:
    """True when archived desk/doc writers may load."""
    raw = env_str("LEGACY_EDITORIAL_WRITERS_ENABLED", "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    # Soft default: allow when editorial room loop is explicitly on (Widow until cutover).
    loop = env_str("EDITORIAL_ROOM_LOOP_ENABLED", "true").strip().lower()
    return loop not in ("0", "false", "no", "off")


def _load_archived_module(submodule: str) -> ModuleType:
    path = _ARCHIVED_EDITORIAL / f"{submodule}.py"
    if not path.is_file():
        raise ImportError(f"Archived editorial module missing: {path}")
    name = f"_archived_editorial_{submodule}"
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


def load_editorial_document_service() -> ModuleType:
    if not legacy_editorial_writers_enabled():
        raise RuntimeError(
            "editorial_document_service archived; set LEGACY_EDITORIAL_WRITERS_ENABLED=1 to rollback"
        )
    return _load_archived_module("editorial_document_service")


def load_editorial_room_loop_service() -> ModuleType:
    if not legacy_editorial_writers_enabled():
        raise RuntimeError(
            "editorial_room_loop_service archived; set LEGACY_EDITORIAL_WRITERS_ENABLED=1 "
            "or EDITORIAL_ROOM_LOOP_ENABLED=true to rollback"
        )
    return _load_archived_module("editorial_room_loop_service")
