#!/usr/bin/env python3
"""Ensure live api/services does not contain retired editorial writer bodies.

Shims at editorial_document_service / editorial_room_loop_service are allowed;
full implementations must live under api/_archived/editorial/.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "api" / "services"
ARCHIVED = ROOT / "api" / "_archived" / "editorial"

# Live service files that must remain thin shims (not full writers).
SHIM_MAX_LINES = 80
SHIM_FILES = (
    "editorial_document_service.py",
    "editorial_room_loop_service.py",
)

FORBIDDEN_IMPORT_RE = re.compile(
    r"from\s+api\._archived\.editorial|import\s+api\._archived\.editorial"
)


def main() -> int:
    errors: list[str] = []
    for name in SHIM_FILES:
        archived = ARCHIVED / name
        if not archived.is_file():
            errors.append(f"missing archived module: {archived}")
        live = SERVICES / name
        if not live.is_file():
            errors.append(f"missing live shim: {live}")
            continue
        text = live.read_text(encoding="utf-8")
        lines = text.splitlines()
        if len(lines) > SHIM_MAX_LINES:
            errors.append(
                f"{live.name} looks too large ({len(lines)} lines) — expected thin shim"
            )
        if "legacy_editorial_rollback" not in text and "_archived" not in text:
            errors.append(f"{live.name} does not reference legacy_editorial_rollback")
        # Must not embed LLM editorial writer prompts inline
        if "generate_editorial_document" in text and "load_editorial" not in text:
            errors.append(f"{live.name} appears to contain writer body")

    # Scan live services for direct archived package imports (should use rollback loader)
    for path in SERVICES.rglob("*.py"):
        if path.name in SHIM_FILES:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if FORBIDDEN_IMPORT_RE.search(body):
            errors.append(f"direct archived import in {path.relative_to(ROOT)}")
        if "_archived/editorial" in body.replace("\\", "/"):
            errors.append(f"hardcoded archived path in {path.relative_to(ROOT)}")

    if errors:
        print("FAIL verify_editorial_archive:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("OK: editorial archive isolation checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
