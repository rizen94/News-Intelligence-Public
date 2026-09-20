#!/usr/bin/env python3
"""Compatibility shim — implementation archived under api/_archived/scripts/."""

from __future__ import annotations

import runpy
from pathlib import Path

_TARGET = Path(__file__).resolve().parents[1] / "_archived" / "scripts" / "run_extraction_burn_down.py"
runpy.run_path(str(_TARGET), run_name="__main__")
