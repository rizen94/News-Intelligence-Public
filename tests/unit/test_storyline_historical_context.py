"""Unit tests for storyline_historical_context_service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.storyline_historical_context_service import (
    build_storyline_historical_context,
    render_historical_context_for_llm,
)


def test_render_historical_context_includes_facts_and_events():
    ctx = {
        "success": True,
        "spine_summary": {
            "entity_count": 2,
            "fact_count": 1,
            "event_count": 1,
            "fact_date_min": "2024-01-01",
            "fact_date_max": "2025-06-01",
        },
        "versioned_facts": [
            {
                "valid_from": "2024-06-01",
                "entity_name": "Acme Corp",
                "fact_text": "Announced merger.",
                "superseded": False,
            }
        ],
        "chronological_spine": {
            "events": [
                {
                    "title": "Merger filed",
                    "event_date": "2024-06-02",
                    "event_type": "economic_event",
                    "importance": 0.8,
                }
            ],
            "gaps": [],
            "milestones": [],
        },
        "articles": [],
    }
    text = render_historical_context_for_llm(ctx, max_chars=8000)
    assert "Established facts" in text
    assert "Acme Corp" in text
    assert "Merger filed" in text
    assert "Chronological spine" in text


@patch("services.storyline_historical_context_service.get_db_connection")
@patch("services.storyline_historical_context_service.resolve_domain_schema", return_value="politics")
@patch("services.timeline_builder_service.build_storyline_spine")
def test_build_storyline_historical_context_success(mock_spine, _schema, mock_conn):
    mock_spine.return_value = {
        "events": [{"title": "E1", "event_date": None, "event_type": "other", "importance": 0.5}],
        "gaps": [],
        "milestones": [],
        "event_count": 1,
    }
    conn = MagicMock()
    mock_conn.return_value = conn
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    cur.fetchone.side_effect = [
        (42, "Test Story"),  # storyline
    ]
    cur.fetchall.side_effect = [
        [("Alice", "person", 3)],  # entities index
        [],  # article_entities supplement
        [],  # versioned_facts
        [],  # articles
    ]

    ctx = build_storyline_historical_context("politics", 42)
    assert ctx["success"] is True
    assert ctx["storyline_id"] == 42
    assert len(ctx["entities"]) == 1
    assert "rendered" in ctx
