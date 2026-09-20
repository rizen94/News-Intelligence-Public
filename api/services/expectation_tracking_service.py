"""
Expectation tracking (Phase 6 C3) — forward-looking claims with due dates.

Extracts due dates from claim text, stores in intelligence.narrative_expectations,
and resolves overdue items against chronological outcome events.
"""

from __future__ import annotations

import logging
import re
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)

_MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_FORWARD_MARKERS = re.compile(
    r"\b(will|expect(?:ed|s)?|by|before|until|scheduled|slated|due|deadline|"
    r"anticipate(?:d|s)?|plans? to|set to|poised to)\b",
    re.I,
)

_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_MONTH_YEAR = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(20\d{2})\b",
    re.I,
)
_MONTH_ONLY = re.compile(
    r"\b(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(20\d{2})\b",
    re.I,
)
_RELATIVE = re.compile(
    r"\b(?:within|in|next)\s+(\d+)\s+(day|days|week|weeks|month|months)\b",
    re.I,
)
_END_OF_QUARTER = re.compile(r"\bend of\s+(Q[1-4])\s*(20\d{2})?\b", re.I)


def expectation_tracking_enabled() -> bool:
    try:
        from config.feature_registry import is_feature_enabled

        if is_feature_enabled("expectation_tracking", default=True):
            return True
    except Exception:
        pass
    return env_bool("EXPECTATION_TRACKING_ENABLED", True)


def parse_due_date(
    text: str,
    *,
    as_of: date | None = None,
) -> tuple[date | None, str]:
    """
    Parse a due date from free text.

    Returns (due_date, precision) where precision is day|week|month|quarter|year|unknown.
    """
    blob = text or ""
    today = as_of or datetime.now(timezone.utc).date()

    m = _ISO_DATE.search(blob)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), "day"
        except ValueError:
            pass

    m = _MONTH_YEAR.search(blob)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        day_n = int(m.group(2))
        year = int(m.group(3))
        if mon:
            try:
                return date(year, mon, min(day_n, monthrange(year, mon)[1])), "day"
            except ValueError:
                pass

    m = _MONTH_ONLY.search(blob)
    if m:
        mon = _MONTHS.get(m.group(1).lower())
        year = int(m.group(2))
        if mon:
            return date(year, mon, monthrange(year, mon)[1]), "month"

    m = _END_OF_QUARTER.search(blob)
    if m:
        q = m.group(1).upper()
        year = int(m.group(2) or today.year)
        end_month = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}[q]
        return date(year, end_month, monthrange(year, end_month)[1]), "quarter"

    m = _RELATIVE.search(blob)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        if unit.startswith("day"):
            return today + timedelta(days=n), "day"
        if unit.startswith("week"):
            return today + timedelta(weeks=n), "week"
        if unit.startswith("month"):
            # Approximate months
            return today + timedelta(days=30 * n), "month"

    # "by 2027" / "in 2026"
    m = re.search(r"\b(?:by|in|before)\s+(20\d{2})\b", blob, re.I)
    if m:
        year = int(m.group(1))
        return date(year, 12, 31), "year"

    return None, "unknown"


def looks_forward_looking(text: str) -> bool:
    return bool(_FORWARD_MARKERS.search(text or ""))


def extract_expectation_from_claim(
    claim: dict[str, Any],
    *,
    domain_key: str,
    as_of: date | None = None,
) -> dict[str, Any] | None:
    """Build an expectation row dict from an extracted_claims-like mapping."""
    subject = (claim.get("subject_text") or "").strip()
    predicate = (claim.get("predicate_text") or "").strip()
    obj = (claim.get("object_text") or "").strip()
    claim_text = claim.get("claim_text") or f"{subject} {predicate} {obj}".strip()
    if not claim_text or not looks_forward_looking(claim_text):
        return None
    due, precision = parse_due_date(claim_text, as_of=as_of)
    if due is None:
        return None
    return {
        "domain_key": domain_key,
        "storyline_id": claim.get("storyline_id"),
        "source_claim_id": claim.get("id"),
        "context_id": claim.get("context_id"),
        "claim_text": claim_text[:4000],
        "subject_text": subject[:500] or None,
        "expected_outcome": obj[:2000] or None,
        "due_date": due,
        "due_date_precision": precision,
        "confidence": float(claim.get("confidence") or 0.5),
        "metadata": {"predicate": predicate},
    }


def store_expectation(row: dict[str, Any]) -> int | None:
    from shared.database.connection import get_db_connection_context
    import json

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.narrative_expectations (
                        domain_key, storyline_id, source_claim_id, context_id,
                        claim_text, subject_text, expected_outcome, due_date,
                        due_date_precision, confidence, metadata
                    ) VALUES (
                        %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb
                    )
                    ON CONFLICT (source_claim_id) WHERE source_claim_id IS NOT NULL
                    DO UPDATE SET
                        updated_at = NOW(),
                        due_date = EXCLUDED.due_date,
                        claim_text = EXCLUDED.claim_text
                    RETURNING id
                    """,
                    (
                        row["domain_key"],
                        row.get("storyline_id"),
                        row.get("source_claim_id"),
                        row.get("context_id"),
                        row["claim_text"],
                        row.get("subject_text"),
                        row.get("expected_outcome"),
                        row["due_date"],
                        row.get("due_date_precision") or "day",
                        float(row.get("confidence") or 0.5),
                        json.dumps(row.get("metadata") or {}),
                    ),
                )
                got = cur.fetchone()
            conn.commit()
            return int(got[0]) if got else None
    except Exception as e:
        logger.warning("store_expectation: %s", e)
        return None


def harvest_expectations_from_claims(
    *,
    domain_key: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Scan recent high-confidence claims for forward-looking due dates."""
    if not expectation_tracking_enabled():
        return {"enabled": False, "stored": 0}

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_active_domain_keys
    from psycopg2.extras import RealDictCursor

    domains = [domain_key] if domain_key else list(get_pipeline_active_domain_keys())
    stored = 0
    scanned = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                for dk in domains:
                    cur.execute(
                        """
                        SELECT id, context_id, subject_text, predicate_text, object_text,
                               confidence, metadata
                        FROM intelligence.extracted_claims
                        WHERE confidence >= 0.55
                          AND created_at > NOW() - INTERVAL '30 days'
                          AND (
                            predicate_text ~* 'will|expect|by |before|scheduled|due|deadline'
                            OR object_text ~* 'will|expect|by |before|scheduled|due|deadline'
                          )
                        ORDER BY confidence DESC, id DESC
                        LIMIT %s
                        """,
                        (limit,),
                    )
                    for row in cur.fetchall() or []:
                        scanned += 1
                        claim = dict(row)
                        claim["storyline_id"] = (claim.get("metadata") or {}).get(
                            "storyline_id"
                        ) if isinstance(claim.get("metadata"), dict) else None
                        exp = extract_expectation_from_claim(claim, domain_key=dk)
                        if not exp:
                            continue
                        if store_expectation(exp):
                            stored += 1
    except Exception as e:
        logger.warning("harvest_expectations_from_claims: %s", e)
        return {"enabled": True, "stored": stored, "scanned": scanned, "error": str(e)[:200]}
    return {"enabled": True, "stored": stored, "scanned": scanned}


def list_expectations(
    *,
    status: str | None = None,
    domain_key: str | None = None,
    overdue_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append("status = %s")
        params.append(status)
    if domain_key:
        clauses.append("domain_key = %s")
        params.append(domain_key)
    if overdue_only:
        clauses.append("due_date < CURRENT_DATE")
        clauses.append("status IN ('open', 'due_soon', 'overdue')")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(int(limit), 200)))
    sql = f"""
        SELECT id, created_at, updated_at, domain_key, storyline_id, source_claim_id,
               claim_text, subject_text, expected_outcome, due_date, due_date_precision,
               status, resolved_at, outcome_event_id, outcome_summary, confidence, metadata
        FROM intelligence.narrative_expectations
        {where}
        ORDER BY due_date ASC NULLS LAST, id DESC
        LIMIT %s
    """
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("list_expectations: %s", e)
        return []


def mark_overdue(*, as_of: date | None = None) -> int:
    today = as_of or datetime.now(timezone.utc).date()
    from shared.database.connection import get_db_connection_context

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.narrative_expectations
                    SET status = 'overdue', updated_at = NOW()
                    WHERE due_date < %s
                      AND status IN ('open', 'due_soon')
                    """,
                    (today,),
                )
                n = cur.rowcount
            conn.commit()
            return int(n or 0)
    except Exception as e:
        logger.warning("mark_overdue: %s", e)
        return 0


def search_outcome_events(
    expectation: dict[str, Any],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Keyword search chronological_events for likely outcome coverage."""
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    subject = (expectation.get("subject_text") or "").strip()
    outcome = (expectation.get("expected_outcome") or "").strip()
    tokens = [t for t in re.split(r"\W+", f"{subject} {outcome}") if len(t) > 3][:6]
    if not tokens:
        return []
    like_clauses = " AND ".join(["(title ILIKE %s OR description ILIKE %s)"] * len(tokens))
    params: list[Any] = []
    for t in tokens:
        params.extend([f"%{t}%", f"%{t}%"])
    params.append(limit)
    sql = f"""
        SELECT id, title, description, actual_event_date, storyline_id
        FROM public.chronological_events
        WHERE {like_clauses}
        ORDER BY COALESCE(actual_event_date, created_at) DESC NULLS LAST
        LIMIT %s
    """
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("search_outcome_events: %s", e)
        return []


def resolve_overdue_expectations(*, limit: int = 40) -> dict[str, Any]:
    """Mark overdue and attempt outcome event matching."""
    if not expectation_tracking_enabled():
        return {"enabled": False, "resolved": 0}

    marked = mark_overdue()
    rows = list_expectations(status="overdue", limit=limit)
    resolved = 0
    from shared.database.connection import get_db_connection_context

    for exp in rows:
        events = search_outcome_events(exp, limit=3)
        if not events:
            continue
        ev = events[0]
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.narrative_expectations
                        SET status = 'resolved',
                            resolved_at = NOW(),
                            outcome_event_id = %s,
                            outcome_summary = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            int(ev["id"]),
                            (ev.get("title") or "")[:1000],
                            int(exp["id"]),
                        ),
                    )
                conn.commit()
                resolved += 1
        except Exception as e:
            logger.debug("resolve expectation %s: %s", exp.get("id"), e)
    return {"enabled": True, "marked_overdue": marked, "resolved": resolved, "checked": len(rows)}
