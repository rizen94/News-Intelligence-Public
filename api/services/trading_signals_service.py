"""Phase C: event→ticker impact scoring + HITL trading signals (no auto-execution)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Narrow commodity/geopolitics heuristics for v1
_TICKER_KEYWORDS: list[tuple[re.Pattern[str], str, float, str]] = [
    (re.compile(r"\b(oil|crude|brent|wti|opec)\b", re.I), "USO", 1.5, "up"),
    (re.compile(r"\b(natural gas|lng)\b", re.I), "UNG", 1.2, "up"),
    (re.compile(r"\b(gold|bullion)\b", re.I), "GLD", 0.8, "up"),
    (re.compile(r"\b(war|conflict|sanctions|embargo)\b", re.I), "USO", 1.0, "up"),
    (re.compile(r"\b(rate cut|fed cut|easing)\b", re.I), "SPY", 0.6, "up"),
    (re.compile(r"\b(rate hike|tightening|inflation spike)\b", re.I), "TLT", 0.7, "down"),
]


def upsert_ticker_mapping(
    *,
    entity_name: str,
    ticker: str,
    entity_id: int | None = None,
    exchange: str | None = None,
    source: str = "manual",
    confidence: float = 0.8,
) -> int | None:
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO intelligence.entity_ticker_map (
                        entity_id, entity_name, ticker, exchange, source, confidence, active
                    ) VALUES (%s, %s, %s, %s, %s, %s, TRUE)
                    RETURNING id
                    """,
                    (
                        entity_id,
                        entity_name,
                        ticker.upper(),
                        exchange,
                        source,
                        max(0.0, min(1.0, float(confidence))),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row[0]) if row else None
    except Exception as e:
        logger.warning("upsert_ticker_mapping: %s", e)
        return None


def resolve_tickers_for_text(text: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    blob = text or ""
    for pat, ticker, move, direction in _TICKER_KEYWORDS:
        if pat.search(blob) and ticker not in seen:
            seen.add(ticker)
            hits.append(
                {
                    "ticker": ticker,
                    "expected_move_pct": move,
                    "direction": direction,
                    "method": "heuristic",
                    "confidence": 0.45,
                }
            )
    # Also pull mapped entity tickers by name substring
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT entity_name, ticker, confidence
                    FROM intelligence.entity_ticker_map
                    WHERE active = TRUE
                    LIMIT 200
                    """
                )
                for row in cur.fetchall() or []:
                    name = (row.get("entity_name") or "").strip()
                    ticker = (row.get("ticker") or "").upper()
                    if name and ticker and name.lower() in blob.lower() and ticker not in seen:
                        seen.add(ticker)
                        hits.append(
                            {
                                "ticker": ticker,
                                "expected_move_pct": 1.0,
                                "direction": "unknown",
                                "method": "entity_map",
                                "confidence": float(row.get("confidence") or 0.6),
                            }
                        )
    except Exception as e:
        logger.debug("resolve_tickers_for_text map: %s", e)
    return hits


def score_event_impacts(
    *,
    tracked_event_id: int,
    event_name: str = "",
    event_summary: str = "",
    causal_edge_id: int | None = None,
) -> list[dict[str, Any]]:
    text = f"{event_name} {event_summary}".strip()
    candidates = resolve_tickers_for_text(text)
    # Boost confidence when a typed causal edge is attached
    if causal_edge_id:
        for c in candidates:
            c["confidence"] = min(0.85, float(c.get("confidence") or 0.4) + 0.15)
            c["causal_edge_id"] = causal_edge_id
    written: list[dict[str, Any]] = []
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for c in candidates:
                    cur.execute(
                        """
                        INSERT INTO intelligence.event_ticker_impacts (
                            tracked_event_id, causal_edge_id, ticker,
                            expected_move_pct, confidence, method, direction,
                            rationale, evidence, status, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'proposed', NOW()
                        )
                        RETURNING id
                        """,
                        (
                            tracked_event_id,
                            c.get("causal_edge_id") or causal_edge_id,
                            c["ticker"],
                            float(c.get("expected_move_pct") or 0),
                            float(c.get("confidence") or 0.4),
                            c.get("method") or "heuristic",
                            c.get("direction") or "unknown",
                            f"Heuristic impact for {c['ticker']} from event {tracked_event_id}",
                            json.dumps({"event_name": event_name}),
                        ),
                    )
                    row = cur.fetchone()
                    if row:
                        item = dict(c)
                        item["impact_id"] = int(row[0])
                        item["tracked_event_id"] = tracked_event_id
                        written.append(item)
            conn.commit()
    except Exception as e:
        logger.warning("score_event_impacts: %s", e)
    return written


def create_signal_from_impact(impact_id: int, *, idea_summary: str | None = None) -> int | None:
    try:
        from shared.database.connection import get_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM intelligence.event_ticker_impacts WHERE id = %s",
                    (int(impact_id),),
                )
                imp = cur.fetchone()
                if not imp:
                    return None
                summary = idea_summary or (
                    f"{imp['ticker']}: expected {imp.get('expected_move_pct')}% "
                    f"({imp.get('direction')}) — HITL review required"
                )
                cur.execute(
                    """
                    INSERT INTO intelligence.trading_signals (
                        impact_id, ticker, idea_summary, expected_move_pct,
                        confidence, review_status, metadata
                    ) VALUES (%s, %s, %s, %s, %s, 'pending', %s::jsonb)
                    RETURNING id
                    """,
                    (
                        int(impact_id),
                        imp["ticker"],
                        summary,
                        imp.get("expected_move_pct"),
                        float(imp.get("confidence") or 0.4),
                        json.dumps({"tracked_event_id": imp.get("tracked_event_id")}),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
            return int(row["id"]) if row else None
    except Exception as e:
        logger.warning("create_signal_from_impact: %s", e)
        return None


def list_signals(
    *,
    review_status: str | None = "pending",
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if review_status:
        clauses.append("review_status = %s")
        params.append(review_status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(int(limit), 200)))
    sql = f"""
        SELECT id, created_at, updated_at, impact_id, ticker, idea_summary,
               expected_move_pct, confidence, review_status, review_reason,
               reviewed_at, reviewed_by, metadata
        FROM intelligence.trading_signals
        {where}
        ORDER BY created_at DESC
        LIMIT %s
    """
    try:
        from shared.database.connection import get_ui_db_connection_context
        from psycopg2.extras import RealDictCursor

        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("list_signals: %s", e)
        return []


def review_signal(
    signal_id: int,
    *,
    decision: str,
    reason: str = "",
    reviewed_by: str = "operator",
) -> bool:
    if decision not in ("approved", "rejected"):
        raise ValueError("decision must be approved|rejected")
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.trading_signals
                    SET review_status = %s,
                        review_reason = %s,
                        reviewed_at = NOW(),
                        reviewed_by = %s,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (decision, reason[:500], reviewed_by, int(signal_id)),
                )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.warning("review_signal: %s", e)
        return False


def generate_signals_from_recent_events(*, days: int = 14, limit: int = 15) -> dict[str, Any]:
    """Scan recent tracked events for oil/commodity language and enqueue HITL signals."""
    created_impacts = 0
    created_signals = 0
    try:
        from shared.database.connection import get_db_connection_context
        from psycopg2.extras import RealDictCursor
        from services.causal_edges_service import edges_for_tracked_event

        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, event_name, COALESCE(global_narrative, '') AS summary
                    FROM intelligence.tracked_events
                    WHERE COALESCE(updated_at, created_at) >= NOW() - (%s * INTERVAL '1 day')
                    ORDER BY COALESCE(updated_at, created_at) DESC
                    LIMIT %s
                    """,
                    (max(1, days), limit),
                )
                events = [dict(r) for r in (cur.fetchall() or [])]
        for ev in events:
            edges = edges_for_tracked_event(int(ev["id"]), limit=3)
            edge_id = int(edges[0]["id"]) if edges else None
            impacts = score_event_impacts(
                tracked_event_id=int(ev["id"]),
                event_name=ev.get("event_name") or "",
                event_summary=ev.get("summary") or "",
                causal_edge_id=edge_id,
            )
            created_impacts += len(impacts)
            for imp in impacts:
                sid = create_signal_from_impact(int(imp["impact_id"]))
                if sid:
                    created_signals += 1
    except Exception as e:
        logger.warning("generate_signals_from_recent_events: %s", e)
    return {"impacts": created_impacts, "signals": created_signals}
