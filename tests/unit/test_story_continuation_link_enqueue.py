"""Continuation link enqueues materiality-gated narrative finisher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def continuation_svc():
    from services.story_continuation_service import StoryContinuationService

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    svc = StoryContinuationService(conn, schema="politics")
    svc.domain_key = "politics"
    return svc, conn, cursor


def test_link_event_calls_maybe_enqueue_finisher(continuation_svc):
    svc, conn, cursor = continuation_svc
    event = {"id": 101, "source_article_id": 55}
    match = {"storyline_id": 7, "confidence": 0.91, "auto_linked": True}

    with (
        patch(
            "shared.episode_attach_gate.episode_container_assembly_enabled",
            return_value=False,
        ),
        patch(
            "shared.assembly_link_funnel.storyline_articles_dual_write_enabled",
            return_value=False,
        ),
        patch(
            "services.content_refinement_queue_service.maybe_enqueue_narrative_finisher_on_membership"
        ) as enq,
        patch.object(svc, "update_entity_index"),
    ):
        svc._link_event(event, match)

    enq.assert_called_once()
    args, kwargs = enq.call_args
    assert args[0] == "politics"
    assert args[1] == 7
    assert kwargs.get("source") == "story_continuation"
    assert kwargs.get("article_id") == 55
    conn.commit.assert_called()


def test_link_event_enqueue_failure_keeps_commit(continuation_svc):
    svc, conn, _cursor = continuation_svc
    event = {"id": 102, "source_article_id": 56}
    match = {"storyline_id": 8, "confidence": 0.88, "auto_linked": True}

    with (
        patch(
            "shared.episode_attach_gate.episode_container_assembly_enabled",
            return_value=False,
        ),
        patch(
            "shared.assembly_link_funnel.storyline_articles_dual_write_enabled",
            return_value=False,
        ),
        patch(
            "services.content_refinement_queue_service.maybe_enqueue_narrative_finisher_on_membership",
            side_effect=RuntimeError("ollama down"),
        ),
        patch.object(svc, "update_entity_index"),
    ):
        svc._link_event(event, match)

    conn.commit.assert_called()
    # Enqueue runs after commit; failure must not undo the link.
    conn.rollback.assert_not_called()
