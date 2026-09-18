"""Kit bootstrap: set env flags before NI main loads."""

from __future__ import annotations

import os


def apply_kit_bootstrap() -> None:
    os.environ.setdefault("NEWS_INTEL_KIT_MODE", "true")
    os.environ.setdefault("NEWS_INTEL_SKIP_FINANCE_ORCHESTRATOR", "true")
    os.environ.setdefault("NEWS_INTEL_SKIP_ML_PROCESSING", "true")
