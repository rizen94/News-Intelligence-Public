from nri_core.spine.resolution.matcher import _fuzzy_score


def test_low_score_implies_parked_threshold():
    score = _fuzzy_score("Totally Different Corp", "Another Unrelated Entity LLC")
    assert score < 0.85
