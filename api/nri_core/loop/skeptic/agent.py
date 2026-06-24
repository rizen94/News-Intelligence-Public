"""Skeptic agent — separate role from reasoner."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from nri_core.llm.ollama_client import chat_json

SKEPTIC_PROMPT = """You are a skeptic reviewer. Attack the hypothesis for overreach, missing mundane alternatives,
and causal language without temporal order.

UNTRUSTED_NOTE_START
{note}
UNTRUSTED_NOTE_END

Return JSON: findings (list of strings), confidence_downgrade (float 0-1 or null),
refutation_recommended (bool), causal_language_flags (list).
"""


@dataclass
class SkepticFinding:
    findings: list[str]
    confidence_downgrade: float | None
    refutation_recommended: bool
    causal_language_flags: list[str]
    raw: dict[str, Any]


def review_note(note_content: str) -> SkepticFinding:
    prompt = SKEPTIC_PROMPT.format(note=note_content)
    raw = chat_json(prompt=prompt, role="skeptic")
    downgrade = raw.get("confidence_downgrade")
    return SkepticFinding(
        findings=list(raw.get("findings", [])),
        confidence_downgrade=float(downgrade) if downgrade is not None else None,
        refutation_recommended=bool(raw.get("refutation_recommended", False)),
        causal_language_flags=list(raw.get("causal_language_flags", [])),
        raw=raw,
    )


def apply_skeptic_corrections(path: str, finding: SkepticFinding) -> bool:
    """Step 6b: amend note with skeptic corrections."""
    from pathlib import Path

    import yaml

    note_path = Path(path)
    if not note_path.exists():
        return False
    text = note_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return False
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    changed = False
    if finding.confidence_downgrade is not None:
        current = float(meta.get("confidence", 0.5))
        meta["confidence"] = round(min(current, finding.confidence_downgrade), 4)
        changed = True
    if finding.refutation_recommended:
        meta["status"] = "refuted"
        meta["skeptic_review"] = finding.findings
        changed = True
    if finding.causal_language_flags:
        meta["causal_language_flags"] = finding.causal_language_flags
        changed = True
    if changed:
        header = yaml.dump(meta, default_flow_style=False, allow_unicode=True)
        note_path.write_text(f"---\n{header}---\n\n{body}", encoding="utf-8")
    return changed
