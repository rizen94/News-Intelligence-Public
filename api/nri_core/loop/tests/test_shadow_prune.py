from dataclasses import replace

from nri_core.config import get_config
from nri_core.loop.reassess.rules import reassess_hypotheses
from nri_core.loop.shadow.seed import seed_falsifiable_hypotheses


def test_net_negative_after_seed(tmp_path, monkeypatch):
    monkeypatch.setenv("NRI_VAULT_PATH", str(tmp_path))

    def _vault_config():
        return replace(get_config(), vault_path=str(tmp_path))

    monkeypatch.setattr("nri_core.loop.shadow.seed.get_config", _vault_config)
    monkeypatch.setattr("nri_core.loop.reassess.rules.get_config", _vault_config)

    (tmp_path / "hypotheses").mkdir(parents=True)
    seed_falsifiable_hypotheses(20)
    total_killed = 0
    for i in range(1, 4):
        metrics = reassess_hypotheses("seed-entity-0", iteration=i)
        total_killed += metrics.killed + metrics.demoted + metrics.dormant
    assert total_killed > 0
