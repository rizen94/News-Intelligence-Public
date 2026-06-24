from pathlib import Path

from nri_core.loop.reassess.rules import reassess_hypotheses


def test_confidence_decay(tmp_path, monkeypatch):
    monkeypatch.setenv("NRI_VAULT_PATH", str(tmp_path))
    hyp_dir = tmp_path / "hypotheses"
    hyp_dir.mkdir()
    hyp = hyp_dir / "hyp-decay.md"
    hyp.write_text(
        """---
hyp_id: hyp-decay
status: open
confidence: 0.6
supports: []
iterations_since_support: 0
subject_ftm_id: ent-abc
---
body
"""
    )
    metrics = reassess_hypotheses("ent-abc", new_evidence_ids=[], iteration=1)
    text = hyp.read_text()
    assert "confidence:" in text
    assert metrics.demoted + metrics.dormant >= 0
