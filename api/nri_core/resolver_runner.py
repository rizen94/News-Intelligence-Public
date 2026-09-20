"""Automation entrypoint for mention resolution drain."""

from __future__ import annotations

from typing import Any

from config.runtime import mention_resolve_batch_limit, mention_resolve_budget_seconds


def run_mention_resolution_drain(
    *,
    budget_seconds: float | None = None,
    batch_limit: int | None = None,
) -> dict[str, Any]:
    from nri_core.evidence.mention_resolver import resolve_drain

    return resolve_drain(
        limit=batch_limit or mention_resolve_batch_limit(),
        budget_seconds=(
            budget_seconds
            if budget_seconds is not None
            else mention_resolve_budget_seconds()
        ),
    )
