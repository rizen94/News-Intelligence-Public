"""Phase A: narrative chain-of-thought scaffold backed by typed causal edges."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "editorial_room"
    / "causal_narrative.md"
)


def load_causal_narrative_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "Reference the causal subgraph, list CoT steps, then write the narrative. "
            "Do not assert causation without an edge id."
        )


def build_narrative_scaffold(
    *,
    domain_key: str,
    storyline_id: int | None = None,
    tracked_event_id: int | None = None,
    max_edges: int = 8,
) -> dict[str, Any]:
    from services.causal_edges_service import edges_for_storyline, edges_for_tracked_event

    edges: list[dict[str, Any]] = []
    if storyline_id is not None:
        edges = edges_for_storyline(domain_key, int(storyline_id), limit=max_edges)
    elif tracked_event_id is not None:
        edges = edges_for_tracked_event(int(tracked_event_id), limit=max_edges)

    steps: list[dict[str, Any]] = [
        {
            "step": 1,
            "action": "load_causal_subgraph",
            "edge_ids": [int(e["id"]) for e in edges if e.get("id")],
        },
        {
            "step": 2,
            "action": "grade_evidence",
            "grades": [e.get("evidence_grade") for e in edges],
        },
        {
            "step": 3,
            "action": "draft_narrative_with_citations",
            "rule": "cite edge_id for every causal claim",
        },
    ]
    return {
        "prompt_preamble": load_causal_narrative_prompt(),
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "tracked_event_id": tracked_event_id,
        "causal_edges": edges,
        "reasoning_steps": steps,
        "has_typed_edges": bool(edges),
    }


def persist_reasoning_chain(
    *,
    domain_key: str,
    storyline_id: int | None = None,
    tracked_event_id: int | None = None,
    steps: list[dict[str, Any]] | list[str],
    narrative: str | None = None,
    edge_ids: list[int] | None = None,
) -> bool:
    """Store CoT on automation_run_history-style key or storyline metadata when available."""
    payload = {
        "domain_key": domain_key,
        "storyline_id": storyline_id,
        "tracked_event_id": tracked_event_id,
        "reasoning_steps": steps,
        "narrative": narrative,
        "edge_ids": edge_ids or [],
    }
    key = (
        f"narrative_reasoning:storyline:{domain_key}:{storyline_id}"
        if storyline_id is not None
        else f"narrative_reasoning:event:{tracked_event_id}"
    )
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (key, json.dumps(payload)),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.warning("persist_reasoning_chain failed: %s", e)
        return False


def get_reasoning_chain(
    *,
    domain_key: str | None = None,
    storyline_id: int | None = None,
    tracked_event_id: int | None = None,
) -> dict[str, Any] | None:
    if storyline_id is not None and domain_key:
        key = f"narrative_reasoning:storyline:{domain_key}:{storyline_id}"
    elif tracked_event_id is not None:
        key = f"narrative_reasoning:event:{tracked_event_id}"
    else:
        return None
    try:
        from shared.database.connection import get_ui_db_connection_context

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (key,),
                )
                row = cur.fetchone()
        if not row or not row[0]:
            # Fall back to edge-backed scaffold
            if storyline_id is not None and domain_key:
                return build_narrative_scaffold(
                    domain_key=domain_key, storyline_id=storyline_id
                )
            if tracked_event_id is not None:
                return build_narrative_scaffold(
                    domain_key=domain_key or "politics",
                    tracked_event_id=tracked_event_id,
                )
            return None
        raw = row[0]
        data = json.loads(raw) if isinstance(raw, str) else dict(raw)
        # Enrich with live edges
        scaffold = build_narrative_scaffold(
            domain_key=data.get("domain_key") or domain_key or "politics",
            storyline_id=storyline_id or data.get("storyline_id"),
            tracked_event_id=tracked_event_id or data.get("tracked_event_id"),
        )
        data["causal_edges"] = scaffold.get("causal_edges") or []
        data["has_typed_edges"] = scaffold.get("has_typed_edges")
        return data
    except Exception as e:
        logger.debug("get_reasoning_chain: %s", e)
        return None
