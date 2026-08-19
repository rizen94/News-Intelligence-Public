"""Unit tests for SEI entity_type mapping helper."""

from __future__ import annotations

from shared.story_entity_index import SEI_ENTITY_TYPES, map_entity_type_for_sei


def test_map_subject_and_recurring_event():
    assert map_entity_type_for_sei("subject") == "other"
    assert map_entity_type_for_sei("recurring_event") == "event"


def test_map_unknown_and_empty():
    assert map_entity_type_for_sei("unknown") == "other"
    assert map_entity_type_for_sei("") == "other"
    assert map_entity_type_for_sei(None) == "other"
    assert map_entity_type_for_sei("widget") == "other"


def test_map_passthrough_and_family():
    assert map_entity_type_for_sei("person") == "person"
    assert map_entity_type_for_sei("organization") == "organization"
    assert map_entity_type_for_sei("family") == "family"
    assert map_entity_type_for_sei("family", family_allowed=False) == "other"


def test_mapped_values_are_in_closed_set():
    for raw in ("subject", "recurring_event", "PERSON", " Family ", "bogus"):
        assert map_entity_type_for_sei(raw) in SEI_ENTITY_TYPES
