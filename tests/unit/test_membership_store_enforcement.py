"""CI guard: forbid direct INSERT INTO storyline_articles outside allowlist."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "api"

ALLOWLIST = {
    API_ROOT / "shared" / "membership_store.py",
    API_ROOT / "scripts" / "purge_merged_archived_storylines.py",
}

SKIP_DIR_PARTS = {"archive", "tmp_rsync_staging", "tests"}

INSERT_PATTERN = re.compile(
    r"INSERT\s+INTO\s+(\{?\w*\.?schema\}?|\w+)\.storyline_articles",
    re.IGNORECASE,
)


def _scan_file(path: Path) -> list[str]:
    if path in ALLOWLIST:
        return []
    if path.suffix != ".py" or any(part in SKIP_DIR_PARTS for part in path.parts):
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    hits: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "storyline_articles" not in line or "INSERT" not in line.upper():
            continue
        if INSERT_PATTERN.search(line):
            hits.append(f"{path.relative_to(REPO_ROOT)}:{i}: {line.strip()[:120]}")
    return hits


def test_no_direct_storyline_articles_insert_outside_allowlist():
    violations: list[str] = []
    for path in API_ROOT.rglob("*.py"):
        violations.extend(_scan_file(path))
    assert not violations, (
        "Direct INSERT INTO storyline_articles found outside allowlist "
        f"(use shared.membership_store.admit):\n" + "\n".join(violations)
    )
