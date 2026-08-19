"""Unit tests for UIE fulltext chunking helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from shared.uie_fulltext_chunks import (  # noqa: E402
    merge_uie_payloads,
    split_article_body_for_uie,
    uie_per_article_char_budget,
)


def test_budget_shrinks_with_batch_size():
    solo = uie_per_article_char_budget(batch_size=1)
    batched = uie_per_article_char_budget(batch_size=4)
    assert solo > batched
    assert batched >= 1500


def test_split_covers_tail_beyond_budget():
    title = "Long piece"
    # Plant a unique marker only in the far tail.
    lead = ("Lead paragraph about politics. " * 40) + "\n\n"
    mid = ("Middle section continues. " * 40) + "\n\n"
    tail = "TAIL_ONLY_ENTITY_ZorgCorp invented the flux capacitor.\n\n" + ("More tail. " * 20)
    body = (lead + mid) * 8 + tail
    pieces = split_article_body_for_uie(title, body, max_chars=2500)
    assert len(pieces) >= 2
    assert any("TAIL_ONLY_ENTITY_ZorgCorp" in p for p in pieces)
    # First piece should not be the whole body.
    assert sum(len(p) for p in pieces) >= len(body) * 0.5


def test_short_body_single_chunk():
    pieces = split_article_body_for_uie("T", "x" * 500, max_chars=4000)
    assert pieces == ["x" * 500]


def test_merge_uie_payloads_keeps_tail_entities_and_events():
    head = {
        "entities": {"organizations": [{"name": "Acme"}], "people": []},
        "events": [{"event_title": "Summit opens", "event_type": "meeting"}],
        "claims": [{"subject": "Acme", "predicate": "announced", "object": "deal"}],
        "scoring": {"sentiment_score": 0.4, "quality_score": 0.5, "sentiment_label": "neutral"},
        "topic_tags": ["trade"],
    }
    tail = {
        "entities": {"organizations": [{"name": "ZorgCorp"}], "people": [{"name": "Ada"}]},
        "events": [{"event_title": "ZorgCorp launches", "event_type": "product"}],
        "claims": [{"subject": "Ada", "predicate": "joined", "object": "ZorgCorp"}],
        "scoring": {"sentiment_score": 0.8, "quality_score": 0.9, "sentiment_label": "positive"},
        "topic_tags": ["ai"],
    }
    merged = merge_uie_payloads([head, tail])
    orgs = [e.get("name") for e in merged["entities"]["organizations"]]
    assert "Acme" in orgs and "ZorgCorp" in orgs
    titles = [e.get("event_title") for e in merged["events"]]
    assert "Summit opens" in titles and "ZorgCorp launches" in titles
    assert merged["scoring"]["quality_score"] == 0.9
    assert abs(merged["scoring"]["sentiment_score"] - 0.6) < 1e-6
    assert set(merged["topic_tags"]) >= {"trade", "ai"}
