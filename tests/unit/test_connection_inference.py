"""Unit tests for chemistry connection inference stages."""

from shared.connection_inference import (
    INFERENCE_CANDIDATE,
    INFERENCE_ESTABLISHED,
    INFERENCE_HYPOTHESIZED,
    INFERENCE_QUARANTINED,
    normalize_inference_stage,
    promote_stage,
    stage_for_embedding_source,
)


def test_normalize_inference_stage_defaults():
    assert normalize_inference_stage(None) == INFERENCE_CANDIDATE
    assert normalize_inference_stage("bogus") == INFERENCE_CANDIDATE
    assert normalize_inference_stage("Established") == INFERENCE_ESTABLISHED


def test_stage_for_embedding_source():
    assert stage_for_embedding_source(exploratory=True) == INFERENCE_HYPOTHESIZED
    assert stage_for_embedding_source(exploratory=False) == INFERENCE_CANDIDATE


def test_promote_stage_survivors():
    assert promote_stage(INFERENCE_HYPOTHESIZED, survived_stimulus=True) == INFERENCE_CANDIDATE
    assert promote_stage(INFERENCE_CANDIDATE, survived_stimulus=True) == INFERENCE_ESTABLISHED
    assert promote_stage(INFERENCE_ESTABLISHED, survived_stimulus=True) == INFERENCE_ESTABLISHED


def test_promote_stage_failure_quarantines():
    assert promote_stage(INFERENCE_CANDIDATE, survived_stimulus=False) == INFERENCE_QUARANTINED
    assert promote_stage(INFERENCE_HYPOTHESIZED, survived_stimulus=False) == INFERENCE_QUARANTINED
