from nri_core.loop.detect.cooccurrence import (
    DetectionCandidate,
    detect_velocity_spike,
    reject_missing_base_rate,
)


def test_candidate_has_base_rate():
    cand = DetectionCandidate(
        pattern_type="cooccurrence",
        entities=["a", "b"],
        observed_count=5,
        expected_count=1.0,
        base_rate=0.02,
        window="30d",
    )
    assert reject_missing_base_rate(cand.to_dict())


def test_missing_base_rate_rejected():
    assert not reject_missing_base_rate({"observed_count": 3})


def test_velocity_spike_detection():
    result = detect_velocity_spike("ent-1", recent_count=10, baseline_count=2)
    assert result is not None
    assert result.base_rate > 0
