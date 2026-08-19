"""
GDELT 2.0 Events → chronological_events as coreference AID only.

extraction_method = ``gdelt_aid``. These rows carry GlobalEventID / Actor IDs for
event-coreference assist — they do **not** replace NI LLM/unified intake extraction.

Feature: gdelt_events_aid_collector (default off)
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen

import requests

from collectors.public_event_upsert import (
    collector_enabled,
    rate_limit_sleep,
    stable_event_id,
    upsert_chronological_event,
)
from config.runtime import env_int, env_str

logger = logging.getLogger(__name__)

FEATURE_KEY = "gdelt_events_aid_collector"
LASTUPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
USER_AGENT = "NewsIntelligence/1.0 (gdelt-aid-coreference; research)"

# GDELT 2.0 Events export column indexes (fixed-width CSV, no header)
# https://blog.gdeltproject.org/gdelt-2-0-our-global-world-in-realtime/
COL_GLOBAL_EVENT_ID = 0
COL_SQLDATE = 1
COL_ACTOR1_CODE = 5
COL_ACTOR1_NAME = 6
COL_ACTOR1_COUNTRY = 7
COL_ACTOR2_CODE = 15
COL_ACTOR2_NAME = 16
COL_ACTOR2_COUNTRY = 17
COL_EVENT_CODE = 26
COL_EVENT_BASE = 27
COL_GOLDSTEIN = 30
COL_NUM_MENTIONS = 31
COL_AVG_TONE = 34
COL_ACTION_GEO_COUNTRY = 51
COL_ACTION_GEO_FULLNAME = 52
COL_SOURCE_URL = 60


def _latest_export_url() -> str | None:
    rate_limit_sleep()
    try:
        r = requests.get(LASTUPDATE, headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        # Format: size hash url (events, mentions, gkg lines)
        for line in (r.text or "").splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[-1].endswith(".export.CSV.zip"):
                return parts[-1]
    except Exception as e:
        logger.warning("GDELT lastupdate failed: %s", e)
    return None


def _download_events_csv(url: str, *, max_rows: int) -> list[list[str]]:
    rate_limit_sleep(0.5)
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=90) as resp:  # noqa: S310 — fixed GDELT host
            raw = resp.read()
    except Exception as e:
        logger.warning("GDELT export download failed: %s", e)
        return []

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not names:
                return []
            with zf.open(names[0]) as fh:
                text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
                reader = csv.reader(text, delimiter="\t")
                rows: list[list[str]] = []
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    rows.append(row)
                return rows
    except Exception as e:
        logger.warning("GDELT zip parse failed: %s", e)
        return []


def _row_to_event(cols: list[str]) -> dict[str, Any] | None:
    if len(cols) <= COL_GLOBAL_EVENT_ID:
        return None
    geid = cols[COL_GLOBAL_EVENT_ID].strip()
    if not geid:
        return None
    sqldate = cols[COL_SQLDATE] if len(cols) > COL_SQLDATE else ""
    event_date = None
    if len(sqldate) == 8 and sqldate.isdigit():
        event_date = f"{sqldate[:4]}-{sqldate[4:6]}-{sqldate[6:8]}"

    a1 = cols[COL_ACTOR1_NAME] if len(cols) > COL_ACTOR1_NAME else ""
    a2 = cols[COL_ACTOR2_NAME] if len(cols) > COL_ACTOR2_NAME else ""
    code = cols[COL_EVENT_CODE] if len(cols) > COL_EVENT_CODE else ""
    geo = cols[COL_ACTION_GEO_FULLNAME] if len(cols) > COL_ACTION_GEO_FULLNAME else ""
    country = cols[COL_ACTION_GEO_COUNTRY] if len(cols) > COL_ACTION_GEO_COUNTRY else ""
    url = cols[COL_SOURCE_URL] if len(cols) > COL_SOURCE_URL else ""
    a1_code = cols[COL_ACTOR1_CODE] if len(cols) > COL_ACTOR1_CODE else ""
    a2_code = cols[COL_ACTOR2_CODE] if len(cols) > COL_ACTOR2_CODE else ""

    actors = " / ".join(x for x in (a1, a2) if x) or "GDELT actors"
    title = f"GDELT AID {geid}: {actors} ({code or 'event'})"
    goldstein = None
    try:
        if len(cols) > COL_GOLDSTEIN and cols[COL_GOLDSTEIN]:
            goldstein = float(cols[COL_GOLDSTEIN])
    except ValueError:
        pass

    return {
        "event_id": stable_event_id("gdelt_aid", geid),
        "title": title[:500],
        "domain_key": "politics",
        "extraction_method": "gdelt_aid",
        "event_type": "conflict" if (goldstein is not None and goldstein < -5) else "other",
        "description": (
            f"GDELT GlobalEventID={geid}; Actor1Code={a1_code}; Actor2Code={a2_code}; "
            f"EventCode={code}; AID-only coreference assist (not NI extraction). {url}"
        )[:4000],
        "actual_event_date": event_date,
        "importance_score": 0.25,
        "extraction_confidence": 0.4,
        "location": (geo or country or None),
        "verification_source": url or "gdeltproject.org",
        "source_text": url or None,
        "tags": ["gdelt_aid", "coreference_assist", code[:20] if code else "gdelt"],
        "key_actors": [
            *( [{"name": a1, "role": "actor1", "code": a1_code}] if a1 else [] ),
            *( [{"name": a2, "role": "actor2", "code": a2_code}] if a2 else [] ),
        ],
        "entities": [
            {"type": "gdelt_global_event_id", "id": geid},
            *([{"type": "gdelt_actor_code", "id": a1_code}] if a1_code else []),
            *([{"type": "gdelt_actor_code", "id": a2_code}] if a2_code else []),
        ],
        "metadata_extra": {"global_event_id": geid},
    }


def collect_gdelt_events_aid(*, max_rows: int | None = None) -> dict[str, Any]:
    """
    Pull latest GDELT 2.0 export slice and upsert AID-bearing chronological rows.

    Explicitly bounded; does not claim to be NI event extraction.
    """
    if not collector_enabled(FEATURE_KEY, env_flag="GDELT_EVENTS_AID_COLLECTOR_ENABLED"):
        return {"skipped": True, "reason": "feature disabled", "inserted": 0}

    limit = max_rows if max_rows is not None else env_int("GDELT_AID_MAX_ROWS", 200)
    url = (env_str("GDELT_EVENTS_EXPORT_URL") or "").strip() or _latest_export_url()
    if not url:
        return {"skipped": True, "reason": "no GDELT export URL", "inserted": 0}

    rows = _download_events_csv(url, max_rows=limit)
    inserted = 0
    for cols in rows:
        ev = _row_to_event(cols)
        if not ev:
            continue
        if upsert_chronological_event(**ev):
            inserted += 1

    logger.info(
        "GDELT AID collector: rows=%s inserted=%s (coreference assist only; not NI extraction)",
        len(rows),
        inserted,
    )
    return {
        "skipped": False,
        "fetched": len(rows),
        "inserted": inserted,
        "export_url": url,
        "note": "gdelt_aid rows are coreference AIDs only — do not replace NI extraction",
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import json

    print(json.dumps(collect_gdelt_events_aid(), indent=2, default=str))
