"""Unit tests for chronological-event identify quality helpers."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from services.event_extraction_service import (  # noqa: E402
    EventExtractionService,
    assess_chrono_event_quality,
    compute_event_fingerprint,
    is_analysis_or_profile_source,
    normalize_title_stem,
)


def test_analysis_profile_detects_warsh_style_title():
    assert is_analysis_or_profile_source(
        "Kevin Warsh may be the adult in the room at the Fed"
    )
    assert not is_analysis_or_profile_source(
        "Federal Reserve raises interest rates by 25 basis points"
    )


def test_hallucinated_fed_hike_blocked_on_analysis_source():
    decision = assess_chrono_event_quality(
        event_title="Federal Reserve Raises Interest Rates",
        event_type="economic_event",
        temporal_status="occurred",
        article_title="Kevin Warsh may be the adult in the room",
        article_content="Warsh could bring credibility if nominated. Markets may react.",
    )
    assert decision == "block"


def test_real_rate_decision_ok_on_hard_news():
    decision = assess_chrono_event_quality(
        event_title="Federal Reserve Raises Interest Rates",
        event_type="economic_event",
        temporal_status="occurred",
        article_title="Federal Reserve raises interest rates by 25 basis points",
        article_content=(
            "The Federal Reserve raises interest rates today, citing inflation. "
            "Chair Powell said the committee voted to hike rates."
        ),
    )
    assert decision == "ok"


def test_title_stem_fingerprint_stable_across_actor_variance():
    actors_a = [{"name": "Federal Reserve", "role": "institution"}]
    actors_b = [{"name": "Fed", "role": "central bank"}, {"name": "Kevin Warsh", "role": "nominee"}]
    title = "Federal Reserve Raises Interest Rates"
    fp_a = compute_event_fingerprint(
        "economic_event", actors_a, "Washington", "2026-09-18", title=title
    )
    fp_b = compute_event_fingerprint(
        "economic_event", actors_b, "USA", "2026-09-18", title=title
    )
    assert fp_a == fp_b
    # Distinct events stay distinct
    fp_c = compute_event_fingerprint(
        "arrest",
        [{"name": "Christian Castro", "role": "agent"}],
        "Minneapolis",
        "2026-09-18",
        title="Arrest of ICE Agent Christian Castro",
    )
    assert fp_c != fp_a


def test_normalise_event_clears_storyline_and_blocks_hallucination():
    svc = EventExtractionService.__new__(EventExtractionService)
    raw = {
        "event_title": "Federal Reserve Raises Interest Rates",
        "event_type": "economic_event",
        "event_date": "2026-09-18",
        "date_precision": "exact",
        "location": "Washington",
        "key_actors": [{"name": "Kevin Warsh", "role": "Fed Chair"}],
        "outcome": "Rates increased.",
        "is_ongoing": False,
        "continuation_signals": [],
    }
    blocked = svc._normalise_event(
        raw,
        42,
        datetime(2026, 9, 19, tzinfo=timezone.utc),
        "5631",  # would-be magnet attach
        0,
        extraction_model="test",
        article_title="Kevin Warsh may be the adult in the room",
        article_content="Profile of a possible nominee. No rate decision occurred.",
    )
    assert blocked is None

    ok = svc._normalise_event(
        {
            **raw,
            "event_title": "Senator Cassidy criticizes Trump admin on measles outbreak",
            "event_type": "public_statement",
        },
        43,
        datetime(2026, 9, 19, tzinfo=timezone.utc),
        "5631",
        0,
        extraction_model="test",
        article_title="Cassidy blames Trump admin for measles outbreak in PA",
        article_content="Senator Cassidy criticizes Trump admin on measles outbreak response.",
    )
    assert ok is not None
    assert ok["storyline_id"] == ""
    assert normalize_title_stem(ok["title"])
