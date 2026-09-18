"""Config loaders must not re-read the file or re-query the DB once per key."""

from __future__ import annotations

import importlib
import sys

import pytest


def _import(name: str):
    """Import with a real config.runtime (see tests/unit/conftest.py for why)."""
    sys.modules.pop(name, None)
    return importlib.import_module(name)


class TestOrchestratorGovernance:
    @pytest.fixture
    def og(self):
        mod = _import("config.orchestrator_governance")
        mod.invalidate_orchestrator_governance_cache()
        yield mod
        mod.invalidate_orchestrator_governance_cache()

    def test_repeated_reads_parse_the_yaml_once(self, og, monkeypatch):
        parses = {"n": 0}
        real = og._load_and_merge

        def _counted(path):
            parses["n"] += 1
            return real(path)

        monkeypatch.setattr(og, "_load_and_merge", _counted)

        first = og.get_orchestrator_governance_config()
        for _ in range(40):
            og.get_orchestrator_governance_config()

        assert parses["n"] == 1
        assert first == og.get_orchestrator_governance_config()

    def test_callers_cannot_mutate_each_others_config(self, og):
        a = og.get_orchestrator_governance_config()
        a.setdefault("pipeline_controller", {})["_sentinel"] = 1

        b = og.get_orchestrator_governance_config()
        assert "_sentinel" not in (b.get("pipeline_controller") or {})

    def test_a_yaml_edit_is_picked_up_without_an_explicit_invalidate(self, og, monkeypatch, tmp_path):
        yaml_file = tmp_path / "orchestrator_governance.yaml"
        yaml_file.write_text("resources:\n  daily_llm_tokens: 111\n", encoding="utf-8")

        fake_paths = type("_p", (), {"ORCHESTRATOR_GOVERNANCE_YAML": str(yaml_file)})
        monkeypatch.setitem(sys.modules, "config.paths", fake_paths)
        og.invalidate_orchestrator_governance_cache()

        assert og.get_orchestrator_governance_config()["resources"]["daily_llm_tokens"] == 111

        yaml_file.write_text("resources:\n  daily_llm_tokens: 222\n", encoding="utf-8")
        assert og.get_orchestrator_governance_config()["resources"]["daily_llm_tokens"] == 222

    def test_missing_file_still_returns_defaults(self, og, monkeypatch, tmp_path):
        fake_paths = type("_p", (), {"ORCHESTRATOR_GOVERNANCE_YAML": str(tmp_path / "nope.yaml")})
        monkeypatch.setitem(sys.modules, "config.paths", fake_paths)
        og.invalidate_orchestrator_governance_cache()

        cfg = og.get_orchestrator_governance_config()
        assert cfg["resources"]["daily_llm_tokens"] == 100000


class TestSchedulersManifest:
    @pytest.fixture
    def registry(self):
        mod = _import("services.automation.registry")
        mod.invalidate_schedulers_manifest_cache()
        yield mod
        mod.invalidate_schedulers_manifest_cache()

    def test_key_lookups_parse_the_manifest_once(self, registry, monkeypatch):
        parses = {"n": 0}
        real_load = registry.yaml.safe_load

        def _counted(stream):
            parses["n"] += 1
            return real_load(stream)

        monkeypatch.setattr(registry.yaml, "safe_load", _counted)

        owners = registry.list_scheduler_owners()
        assert owners
        for name in owners:
            registry.scheduler_entry(name)
            registry.is_scheduler_enabled(name)

        assert parses["n"] == 1

    def test_callers_cannot_mutate_each_others_manifest(self, registry):
        a = registry.load_schedulers_manifest()
        a.setdefault("schedulers", {})["_sentinel"] = 1

        b = registry.load_schedulers_manifest()
        assert "_sentinel" not in (b.get("schedulers") or {})

    def test_missing_manifest_returns_empty(self, registry, monkeypatch, tmp_path):
        monkeypatch.setattr(registry, "_SCHEDULERS_PATH", tmp_path / "nope.yaml")
        registry.invalidate_schedulers_manifest_cache()

        assert registry.load_schedulers_manifest() == {}


class TestFeatureRegistry:
    def test_db_overrides_are_read_once_for_the_whole_registry(self, monkeypatch):
        fr = _import("config.feature_registry")
        fr.get_feature_registry.cache_clear()

        calls = {"n": 0}

        def _overrides():
            calls["n"] += 1
            return {}

        monkeypatch.setattr(fr, "_db_overrides", _overrides)
        registry = fr.get_feature_registry()

        assert len(registry) > 50
        # Resolving overrides per feature meant one identical SELECT per feature key.
        assert calls["n"] == 1
        fr.get_feature_registry.cache_clear()

    def test_db_overrides_still_win_over_yaml(self, monkeypatch):
        fr = _import("config.feature_registry")
        fr.get_feature_registry.cache_clear()

        monkeypatch.setattr(
            fr,
            "_load_yaml_registry",
            lambda: {"demo_feature": {"enabled": True, "lifecycle": "staged"}},
        )
        monkeypatch.setattr(
            fr,
            "_db_overrides",
            lambda: {"demo_feature": {"enabled": False, "lifecycle": "deprecated", "notes": "off"}},
        )

        entry = fr.get_feature_registry()["demo_feature"]
        assert entry["enabled"] is False
        assert entry["lifecycle"] == "deprecated"
        assert entry["notes"] == "off"
        fr.get_feature_registry.cache_clear()
