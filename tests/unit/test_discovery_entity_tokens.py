"""Unit tests for discovery entity token coercion."""

from services.ai_storyline_discovery import coerce_entity_tokens


def test_coerce_pg_array_literal_text():
    raw = '{running,"operation new york","kalshi inc",trump}'
    got = coerce_entity_tokens(raw)
    assert "kalshi inc" in got
    assert "trump" in got
    assert "t" not in got


def test_coerce_rejects_char_split_noise():
    assert coerce_entity_tokens(["t", "e", "r", '"', ","]) == []


def test_coerce_json_list_string():
    assert "kalshi" in coerce_entity_tokens('["Kalshi", "NY"]')


def test_coerce_list_passthrough():
    assert coerce_entity_tokens(["Kalshi", "x", "Apnimed"]) == ["kalshi", "apnimed"]
