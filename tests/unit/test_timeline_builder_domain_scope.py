"""TimelineBuilder domain-scoped event load."""

from __future__ import annotations

from unittest.mock import MagicMock

from services.timeline_builder_service import TimelineBuilderService


def test_load_events_sql_includes_domain_storylines_exists():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value = cur
    cur.fetchone.return_value = (False,)  # no temporal_status column

    tbs = TimelineBuilderService(conn, schema_name="politics")
    tbs._load_events(99)

    sql = cur.execute.call_args_list[-1][0][0]
    assert "politics.storylines" in sql
    assert "EXISTS" in sql
    assert "storyline_id::int" in sql
