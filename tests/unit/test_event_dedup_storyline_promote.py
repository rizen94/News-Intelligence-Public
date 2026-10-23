"""Dedup merge promotes storyline_id from linked duplicate onto empty canonical."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock


def test_merge_promotes_storyline_id_onto_empty_canonical():
    from services.event_deduplication_service import EventDeduplicationService

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    cursor.fetchone.side_effect = [
        (None, "42"),
        ('[{"name": "A"}]',),
        ("[]",),
    ]

    svc = EventDeduplicationService(conn)
    asyncio.run(svc._merge(duplicate_id=200, canonical_id=100))

    promote_calls = [
        c
        for c in cursor.execute.call_args_list
        if "SET storyline_id" in str(c.args[0])
    ]
    assert promote_calls
    assert promote_calls[0].args[1] == ("42", 100)
    conn.commit.assert_called()


def test_merge_keeps_canonical_storyline_on_conflict():
    from services.event_deduplication_service import EventDeduplicationService

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor

    cursor.fetchone.side_effect = [
        ("10", "99"),
        ("[]",),
        ("[]",),
    ]

    svc = EventDeduplicationService(conn)
    asyncio.run(svc._merge(duplicate_id=201, canonical_id=101))

    promote_calls = [
        c
        for c in cursor.execute.call_args_list
        if "SET storyline_id" in str(c.args[0])
    ]
    assert promote_calls == []
    conn.commit.assert_called()
