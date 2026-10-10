"""Load archived POST_SPINE_RETIRED automation phase handlers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_HANDLERS_PATH = Path(__file__).resolve().parents[1] / "_archived" / "automation" / "retired_phase_handlers.py"


def _load_handlers_module() -> ModuleType:
    name = "_archived_retired_phase_handlers"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, _HANDLERS_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_HANDLERS_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


async def dispatch_retired_automation_phase(automation, phase_name: str, task) -> None:
    mod = _load_handlers_module()
    await mod.dispatch_retired_phase(automation, phase_name, task)
