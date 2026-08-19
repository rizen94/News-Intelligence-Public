"""EventExtractionService JSON parse: single object vs nested arrays."""

from services.event_extraction_service import EventExtractionService


def test_parse_single_event_object_with_nested_actors():
    raw = """
    {
        "event_title": "Christopher Street Day parade cancelled due to crash",
        "event_type": "conflict",
        "event_date": "2026-07-22",
        "date_precision": "exact",
        "location": "Tiergarten park, Berlin",
        "key_actors": [
            {"name": "City of Berlin", "role": "Organizer"}
        ],
        "outcome": "Parade cancelled after a car crashed into the crowd.",
        "is_ongoing": false,
        "continuation_signals": []
    }
    """
    svc = EventExtractionService.__new__(EventExtractionService)
    parsed = svc._parse_json_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["event_title"].startswith("Christopher Street Day")


def test_parse_event_array():
    raw = """[
      {"event_title": "A", "event_type": "other", "key_actors": []},
      {"event_title": "B", "event_type": "other", "key_actors": [{"name": "X"}]}
    ]"""
    svc = EventExtractionService.__new__(EventExtractionService)
    parsed = svc._parse_json_response(raw)
    assert [p["event_title"] for p in parsed] == ["A", "B"]


def test_parse_wrapped_events_key():
    raw = '{"events": [{"event_title": "Wrapped", "event_type": "other"}]}'
    svc = EventExtractionService.__new__(EventExtractionService)
    parsed = svc._parse_json_response(raw)
    assert len(parsed) == 1
    assert parsed[0]["event_title"] == "Wrapped"


def test_empty_json_object_parses_ok_so_no_retry():
    """`{}` under format=json means 'no events', not a broken response."""
    svc = EventExtractionService.__new__(EventExtractionService)
    for raw in ("{}", "[]"):
        events, parsed_ok = svc._parse_json_response_detailed(raw)
        assert events == []
        assert parsed_ok is True


def test_malformed_response_reports_parse_failure():
    svc = EventExtractionService.__new__(EventExtractionService)
    events, parsed_ok = svc._parse_json_response_detailed("Sorry, I cannot help with that.")
    assert events == []
    assert parsed_ok is False
