"""
Congress.gov bill status / actions → chronological_events (politics / legal).

Uses CONGRESS_GOV_API_KEY via shared congress_gov_client. Emits timeline events
for recent actions on tracked legislative_references (does not reimplement the
full legislative scan service).

Feature: congress_status_collector (default off)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from collectors.public_event_upsert import (
    collector_enabled,
    stable_event_id,
    upsert_chronological_event,
)
from config.runtime import env_float, env_int, env_str
from shared.database.connection import get_db_connection_context
from shared.services.congress_gov_client import (
    congress_gov_request,
    is_congress_gov_configured,
)

logger = logging.getLogger(__name__)

FEATURE_KEY = "congress_status_collector"


def fetch_bill_actions(
    congress: int,
    bill_type: str,
    bill_number: int,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    bt = (bill_type or "").strip().lower()
    resp = congress_gov_request(
        f"bill/{congress}/{bt}/{bill_number}/actions",
        params={"limit": max(1, min(250, limit))},
    )
    if not resp.get("success"):
        logger.debug(
            "Congress actions fetch failed %s-%s-%s: %s",
            congress,
            bt,
            bill_number,
            resp.get("error"),
        )
        return []
    data = resp.get("data") or {}
    actions = data.get("actions") or data.get("action") or []
    return list(actions) if isinstance(actions, list) else []


def emit_bill_action_events(
    *,
    congress: int,
    bill_type: str,
    bill_number: int,
    actions: list[dict[str, Any]],
    domain_key: str = "politics",
    bill_title: str | None = None,
) -> int:
    """
    Upsert chronological_events for bill actions.
    Shared helper — also callable from legislative_reference_service.
    """
    bt = (bill_type or "").strip().lower()
    label = bill_title or f"{bt.upper()} {bill_number} ({congress}th)"
    inserted = 0
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        action_date = action.get("actionDate") or action.get("date")
        text = (
            action.get("text")
            or action.get("description")
            or action.get("type")
            or "Congressional action"
        )
        action_code = action.get("actionCode") or action.get("type") or i
        external = f"{congress}-{bt}-{bill_number}-{action_date}-{action_code}"
        event_id = stable_event_id("congress_action", external)
        title = f"{label}: {str(text)[:180]}"
        if upsert_chronological_event(
            event_id=event_id,
            title=title[:500],
            domain_key=domain_key,
            extraction_method="congress_status",
            event_type="legislation",
            description=str(text)[:4000],
            actual_event_date=action_date,
            importance_score=0.55,
            extraction_confidence=0.85,
            location="United States Congress",
            verification_source="congress.gov",
            tags=["congress_gov", "bill_action", bt, str(congress)],
            key_actors=[{"name": label, "role": "bill"}],
            metadata_extra={"congress": congress, "bill_type": bt, "bill_number": bill_number},
        ):
            inserted += 1
    return inserted


def _select_recent_bills(limit: int) -> list[dict[str, Any]]:
    """Distinct bills from legislative_references, newest first."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT congress, bill_type, bill_number, domain_key, bill_title
                FROM (
                    SELECT DISTINCT ON (congress, bill_type, bill_number)
                        congress, bill_type, bill_number, domain_key,
                        COALESCE(
                            bill_metadata->'bill'->>'title',
                            bill_metadata->>'title'
                        ) AS bill_title,
                        updated_at
                    FROM intelligence.legislative_references
                    WHERE fetch_status IN ('ok', 'partial')
                    ORDER BY congress, bill_type, bill_number, updated_at DESC NULLS LAST
                ) t
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def collect_congress_status(
    *,
    bill_limit: int | None = None,
    actions_per_bill: int | None = None,
) -> dict[str, Any]:
    if not collector_enabled(FEATURE_KEY, env_flag="CONGRESS_STATUS_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}
    if not is_congress_gov_configured():
        return {"skipped": True, "reason": "CONGRESS_GOV_API_KEY not set", "inserted": 0}

    limit = bill_limit if bill_limit is not None else env_int("CONGRESS_STATUS_BILL_LIMIT", 15)
    n_actions = (
        actions_per_bill
        if actions_per_bill is not None
        else env_int("CONGRESS_STATUS_ACTIONS_PER_BILL", 10)
    )
    sleep_s = env_float("LEGISLATIVE_FETCH_SLEEP_SECONDS", 0.35)

    # Prefer existing legislative_references; fall back to recent session list.
    bills = _select_recent_bills(limit)
    if not bills:
        congress = env_int("LEGISLATIVE_DEFAULT_CONGRESS", 118)
        from shared.services.congress_gov_client import search_bills

        time.sleep(sleep_s)
        listing = search_bills(congress, limit=limit)
        if listing.get("success"):
            for item in (listing.get("data") or {}).get("bills") or []:
                if not isinstance(item, dict):
                    continue
                bills.append(
                    {
                        "congress": item.get("congress") or congress,
                        "bill_type": (item.get("type") or item.get("billType") or "hr").lower(),
                        "bill_number": item.get("number") or item.get("billNumber"),
                        "domain_key": "politics",
                        "bill_title": (item.get("title") or "")[:300],
                    }
                )

    inserted = 0
    bills_processed = 0
    for bill in bills:
        congress = int(bill.get("congress") or 0)
        btype = str(bill.get("bill_type") or "").strip().lower()
        bnum = bill.get("bill_number")
        if not congress or not btype or not bnum:
            continue
        try:
            bnum_i = int(bnum)
        except (TypeError, ValueError):
            continue
        time.sleep(sleep_s)
        actions = fetch_bill_actions(congress, btype, bnum_i, limit=n_actions)
        bills_processed += 1
        inserted += emit_bill_action_events(
            congress=congress,
            bill_type=btype,
            bill_number=bnum_i,
            actions=actions,
            domain_key=str(bill.get("domain_key") or "politics"),
            bill_title=bill.get("bill_title"),
        )

    logger.info(
        "Congress status collector: bills=%s inserted=%s",
        bills_processed,
        inserted,
    )
    return {
        "skipped": False,
        "bills_processed": bills_processed,
        "inserted": inserted,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_congress_status(), indent=2, default=str))
