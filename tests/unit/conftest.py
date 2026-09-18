"""
Keep leaked module stubs from cascading across the unit suite.

A number of modules here install partial stand-ins for `config.runtime` and
`shared.services.llm_service` into `sys.modules` at import time (a `MagicMock` with a handful of
`env_*` attributes) and never restore them. Because collection imports every module into one
interpreter, the first module to do that poisons every later module that imports the real thing —
`ImportError: cannot import name 'env_bool' from 'config.runtime' (unknown location)`. That silently
took the alphabetical tail of `tests/unit` out of collection.

Dropping the stubs before each module is imported gives every module a clean start. Modules that
want a stub install their own at module scope, so they are unaffected.
"""

from __future__ import annotations

import sys

import pytest

_REAL_MODULE_SUFFIXES = {
    "config.runtime": ("api/config/runtime.py", "api\\config\\runtime.py"),
    "shared.services.llm_service": (
        "api/shared/services/llm_service.py",
        "api\\shared\\services\\llm_service.py",
    ),
}


def _is_stub(name: str) -> bool:
    mod = sys.modules.get(name)
    if mod is None:
        return False
    path = getattr(mod, "__file__", None)
    if not path:
        return True
    return not str(path).endswith(_REAL_MODULE_SUFFIXES[name])


def _drop_stubbed_modules() -> None:
    for name in _REAL_MODULE_SUFFIXES:
        if _is_stub(name):
            sys.modules.pop(name, None)
            parent = name.rsplit(".", 1)[0]
            if parent in sys.modules and not getattr(sys.modules[parent], "__file__", None):
                sys.modules.pop(parent, None)


def pytest_collectstart(collector: pytest.Collector) -> None:
    # Only at module-import boundaries. Modules that installed a stub keep it for the duration of
    # their own tests, since their subject under test already holds references into it.
    if isinstance(collector, pytest.Module):
        _drop_stubbed_modules()
