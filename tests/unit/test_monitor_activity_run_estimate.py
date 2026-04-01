"""Typical phase duration resolution for Monitor current activity estimates."""

import pytest


@pytest.mark.parametrize(
    "hist,db,default,expected,source",
    [
        ([10.0, 20.0, 30.0], {}, {}, 20.0, "memory"),
        ([100.0], {}, {}, 100.0, "memory"),
        ([], {"claims_to_facts": 42.0}, {}, 42.0, "db_history"),
        ([], {}, {"claims_to_facts": 180}, 180.0, "schedule_default"),
        ([], {}, {}, None, "none"),
    ],
)
def test_typical_phase_duration_seconds_order(
    hist, db, default, expected, source
):
    from domains.system_monitoring.routes import system_monitoring as sm

    typical, src = sm._typical_phase_duration_seconds(
        "claims_to_facts",
        {"claims_to_facts": hist} if hist is not None else {},
        db,
        default,
    )
    if expected is None:
        assert typical is None
    else:
        assert typical == pytest.approx(expected)
    assert src == source
