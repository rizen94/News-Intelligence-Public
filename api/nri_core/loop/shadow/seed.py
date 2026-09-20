"""Seed falsifiable hypotheses for net-negative integration tests."""

from __future__ import annotations

from pathlib import Path

from nri_core.config import get_config


def seed_falsifiable_hypotheses(count: int = 20) -> int:
    cfg = get_config()
    vault_root = Path(cfg.vault_path)
    hyp_dir = vault_root / "hypotheses"
    hyp_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for i in range(count):
        hyp_id = f"hyp-seed-{i:03d}"
        path = hyp_dir / f"{hyp_id}.md"
        if path.exists():
            continue
        path.write_text(
            f"""---
hyp_id: {hyp_id}
claim: Seeded falsifiable claim {i}
status: open
confidence: 0.7
supports: []
disconfirming_test: Check SEC filing dates
test_status: pending
disconfirming_result: failed
subject_ftm_id: seed-entity-{i % 5}
iteration_introduced: 0
---
Seeded for net-negative test.
""",
            encoding="utf-8",
        )
        written += 1
    return written
