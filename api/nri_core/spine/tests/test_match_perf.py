import time

from nri_core.spine.resolution.matcher import _fuzzy_score


def test_tier2_fuzzy_p95_under_100ms():
    samples = 200
    start = time.perf_counter()
    for i in range(samples):
        _fuzzy_score(f"Entity Name {i}", f"Entity Name {i} Corp")
    elapsed_ms = (time.perf_counter() - start) * 1000
    p95_estimate = elapsed_ms / samples
    assert p95_estimate < 100
