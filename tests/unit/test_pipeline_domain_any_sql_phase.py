"""
``pipeline_domain_any_sql(column, phase=...)`` — the kwarg five committed callers already pass.

The helper update was lost in the v12 commits (c33bc1f, c86b3c7) that introduced the callers, so
every one of them raised ``TypeError: pipeline_domain_any_sql() got an unexpected keyword argument
'phase'``. On the live PopOS refine worker that meant ``entity_profile_build`` failed on every cycle.
"""

from __future__ import annotations

import importlib
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _import(name: str):
    for mod in ("config.runtime", "config"):
        cached = sys.modules.get(mod)
        if cached is not None and not getattr(cached, "__file__", None):
            sys.modules.pop(mod, None)
    return importlib.import_module(name)


@pytest.fixture
def pds(monkeypatch):
    mod = _import("shared.pipeline_domain_sql")
    monkeypatch.setattr(
        mod,
        "pipeline_domain_keys",
        lambda: ("politics", "medicine", "neurodiversity"),
    )
    return mod


def test_phase_kwarg_is_accepted(pds):
    sql, keys = pds.pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_profile_build"
    )
    assert sql == "ep.domain_key = ANY(%s)"
    assert keys


def test_without_phase_every_pipeline_domain_is_kept(pds):
    sql, keys = pds.pipeline_domain_any_sql("ep.domain_key")
    assert sql == "ep.domain_key = ANY(%s)"
    assert keys == ["politics", "medicine", "neurodiversity"]


def test_phase_narrows_to_domains_whose_band_runs_it(pds, monkeypatch):
    monkeypatch.setattr(
        "shared.domain_registry.pipeline_url_schema_pairs",
        lambda: (
            ("politics", "politics"),
            ("medicine", "medicine"),
            ("neurodiversity", "nd"),
        ),
    )
    monkeypatch.setattr(
        "shared.domain_processing_mode.domain_runs_phase",
        lambda dk, phase: dk != "neurodiversity",
    )

    _sql, keys = pds.pipeline_domain_any_sql(
        "ep.domain_key", phase="entity_profile_build"
    )
    assert keys == ["politics", "medicine"]


def test_no_eligible_domain_yields_false_and_no_params(pds, monkeypatch):
    monkeypatch.setattr(
        "shared.domain_registry.pipeline_url_schema_pairs",
        lambda: (("politics", "politics"),),
    )
    monkeypatch.setattr(
        "shared.domain_processing_mode.domain_runs_phase",
        lambda dk, phase: False,
    )

    sql, keys = pds.pipeline_domain_any_sql("ep.domain_key", phase="corpus_only_phase")
    assert sql == "FALSE"
    assert keys == []


def test_phase_filtered_helpers_exist_and_agree(pds, monkeypatch):
    """
    `pipeline_domain_keys_for_phase`, `pipeline_schema_names_for_phase`, and
    `pipeline_url_schema_pairs_for_phase` were lost in the same v12 commits as the `phase` kwarg.
    """
    monkeypatch.setattr(
        "shared.domain_registry.pipeline_url_schema_pairs",
        lambda: (("politics", "politics"), ("neurodiversity", "neurodiversity")),
    )
    monkeypatch.setattr(
        "shared.domain_processing_mode.domain_runs_phase",
        lambda dk, phase: dk != "neurodiversity",
    )

    pairs = pds.pipeline_url_schema_pairs_for_phase("entity_profile_build")
    assert pairs == [("politics", "politics")]
    assert pds.pipeline_domain_keys_for_phase("entity_profile_build") == ["politics"]
    assert pds.pipeline_schema_names_for_phase("entity_profile_build") == ["politics"]
    # Callers annotate list[...]; returning tuples would still work but drifts from the contract.
    assert isinstance(pairs, list)


def test_no_phase_keeps_every_pipeline_domain(pds, monkeypatch):
    monkeypatch.setattr(
        "shared.domain_registry.pipeline_url_schema_pairs",
        lambda: (("politics", "politics"), ("neurodiversity", "neurodiversity")),
    )

    assert pds.pipeline_domain_keys_for_phase() == ["politics", "neurodiversity"]


def test_processing_mode_failure_fails_open(pds, monkeypatch):
    monkeypatch.setattr(
        "shared.domain_registry.pipeline_url_schema_pairs",
        lambda: (("politics", "politics"), ("neurodiversity", "neurodiversity")),
    )

    def _boom(*_a, **_kw):
        raise RuntimeError("processing_mode unavailable")

    monkeypatch.setattr("shared.domain_processing_mode.domain_runs_phase", _boom)

    # An efficiency filter must never narrow the pipeline to nothing when it cannot decide.
    assert pds.pipeline_domain_keys_for_phase("entity_profile_build") == [
        "politics",
        "neurodiversity",
    ]


def test_committed_callers_of_the_for_phase_helpers_resolve():
    """Exercise the real call sites that were raising ImportError on the live refine worker."""
    from services.backlog_metrics import _pairs_for_phase, _schemas_for_phase
    from services.entity_profile_builder_service import (
        sql_entity_profile_upstream_cleared_exists,
    )

    assert isinstance(_pairs_for_phase("entity_profile_build"), list)
    assert isinstance(_schemas_for_phase("entity_profile_build"), list)
    assert "EXISTS" in sql_entity_profile_upstream_cleared_exists().upper()


def test_every_committed_caller_signature_still_resolves():
    """Guard against the regression recurring: call each site's shape for real."""
    pds = _import("shared.pipeline_domain_sql")
    tracked = (
        subprocess.check_output(["git", "ls-files", "api"], cwd=str(ROOT))
        .decode()
        .split()
    )
    phases: set[str] = set()
    for rel in tracked:
        if not rel.endswith(".py") or "_archived" in rel:
            continue
        src = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"pipeline_domain_any_sql\(([^)]*)\)", src, re.S):
            found = re.search(r"""phase\s*=\s*["']([^"']+)["']""", match.group(1))
            if found:
                phases.add(found.group(1))

    assert phases, "expected committed callers passing phase="
    for phase in sorted(phases):
        sql, keys = pds.pipeline_domain_any_sql("ep.domain_key", phase=phase)
        assert isinstance(keys, list)
        assert sql == "FALSE" or sql.endswith("= ANY(%s)")
