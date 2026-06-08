"""
Reference events loader — idempotent seed from YAML into intelligence.reference_events.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from shared.database.connection import get_db_connection_context, get_ui_db_connection_context

logger = logging.getLogger(__name__)

_DEFAULT_SEED = Path(__file__).resolve().parent.parent / "config" / "reference_events_seed.yaml"


def _parse_event_date(raw: str, precision: str = "day") -> datetime:
    s = (raw or "").strip()
    if precision == "year" and len(s) == 4:
        return datetime(int(s), 1, 1, tzinfo=timezone.utc)
    if precision == "month" and len(s) >= 7:
        return datetime.strptime(s[:7], "%Y-%m").replace(tzinfo=timezone.utc)
    if "T" in s:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    if len(s) >= 10:
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    raise ValueError(f"Unparseable event_date: {raw!r}")


def load_reference_events_from_yaml(
    path: Path | str | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    seed_path = Path(path) if path else _DEFAULT_SEED
    if not seed_path.is_file():
        return {"success": False, "error": f"seed not found: {seed_path}", "inserted": 0, "skipped": 0}

    with open(seed_path) as f:
        data = yaml.safe_load(f) or {}
    events = data.get("events") or []
    inserted = 0
    skipped = 0

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for ev in events:
                if not isinstance(ev, dict):
                    skipped += 1
                    continue
                seed_id = (ev.get("id") or ev.get("seed_id") or "").strip()
                title = (ev.get("title") or "").strip()
                summary = (ev.get("summary") or "").strip()
                if not title or not summary:
                    skipped += 1
                    continue
                precision = (ev.get("date_precision") or "day").strip().lower()
                try:
                    event_dt = _parse_event_date(str(ev.get("event_date") or ""), precision)
                except ValueError:
                    skipped += 1
                    continue
                end_dt = None
                if ev.get("end_date"):
                    try:
                        end_dt = _parse_event_date(str(ev["end_date"]), precision)
                    except ValueError:
                        end_dt = None

                if seed_id:
                    cur.execute(
                        """
                        SELECT id FROM intelligence.reference_events
                        WHERE metadata->>'seed_id' = %s
                        LIMIT 1
                        """,
                        (seed_id,),
                    )
                    if cur.fetchone():
                        skipped += 1
                        continue

                if dry_run:
                    inserted += 1
                    continue

                sources = ev.get("sources") or []
                metadata = {"seed_id": seed_id} if seed_id else {}
                if ev.get("metadata"):
                    metadata.update(ev["metadata"])

                cur.execute(
                    """
                    INSERT INTO intelligence.reference_events (
                        event_date, end_date, date_precision, title, summary, category,
                        entity_qids, sources, confidence, curator, arc_ids, metadata,
                        ingestion_date, vintage_date
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s::text[], %s::jsonb, %s, %s, %s::text[], %s::jsonb,
                        NOW(), %s
                    )
                    """,
                    (
                        event_dt,
                        end_dt,
                        precision,
                        title,
                        summary[:2000],
                        ev.get("category"),
                        ev.get("entity_qids") or [],
                        json.dumps(sources),
                        ev.get("confidence") or "reference",
                        ev.get("curator") or "seed_loader",
                        ev.get("arc_ids") or [],
                        json.dumps(metadata),
                        event_dt,
                    ),
                )
                inserted += 1
        if not dry_run:
            conn.commit()

    return {"success": True, "inserted": inserted, "skipped": skipped, "path": str(seed_path)}


def list_reference_events(
    *,
    arc_id: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if arc_id:
                cur.execute(
                    """
                    SELECT id, event_date, end_date, date_precision, title, summary,
                           category, entity_qids, sources, confidence, arc_ids, metadata
                    FROM intelligence.reference_events
                    WHERE superseded_by_id IS NULL
                      AND %s = ANY(arc_ids)
                    ORDER BY event_date ASC
                    LIMIT %s OFFSET %s
                    """,
                    (arc_id, limit, offset),
                )
            else:
                cur.execute(
                    """
                    SELECT id, event_date, end_date, date_precision, title, summary,
                           category, entity_qids, sources, confidence, arc_ids, metadata
                    FROM intelligence.reference_events
                    WHERE superseded_by_id IS NULL
                    ORDER BY event_date ASC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
            cols = [d[0] for d in cur.description]
            rows = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if d.get("event_date"):
                    d["event_date"] = d["event_date"].isoformat()
                if d.get("end_date"):
                    d["end_date"] = d["end_date"].isoformat()
                rows.append(d)
            return rows
