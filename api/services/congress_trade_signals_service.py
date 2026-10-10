"""Congressional trade signals product: enrich → score → paper vs SPY → HITL.

No live brokerage. Quiver remains ingest SSOT. as_of / paper dates use filed_date only.
"""

from __future__ import annotations

import json
import logging
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config.feature_registry import is_feature_enabled
from services.congress_trade_scoring_service import (
    amount_bucket,
    committee_sector_overlap,
    freshness_days,
    issuer_sector,
    lag_days,
    leadership_weight,
    load_congress_trade_config,
    normalize_side,
    score_enriched_trade,
)

logger = logging.getLogger(__name__)


def is_enabled() -> bool:
    from config.runtime import env_bool

    if env_bool("CONGRESS_TRADE_SIGNALS_ENABLED", False):
        return True
    cfg = load_congress_trade_config()
    if cfg.get("enabled") is False:
        return False
    return is_feature_enabled("congress_trade_signals", default=False)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _prev_month_end(d: date) -> date:
    first = _month_start(d)
    return first - timedelta(days=1)


# ---------------------------------------------------------------------------
# Enrichment
# ---------------------------------------------------------------------------


def _resolve_committees(bioguide_id: str | None, cfg: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Optional Congress.gov member committees; v1 returns empty without API/cache."""
    if not bioguide_id:
        return [], []
    enrich_cfg = cfg.get("enrichment") or {}
    if not enrich_cfg.get("use_congress_gov", True):
        return [], []
    try:
        from shared.services.congress_gov_client import congress_gov_api_key, congress_gov_request

        if not congress_gov_api_key():
            return [], []
        # Congress.gov member endpoint by bioguide (best-effort; ignore failures)
        res = congress_gov_request(f"member/{bioguide_id}")
        if not res.get("success"):
            return [], []
        data = res.get("data") or {}
        member = data.get("member") if isinstance(data, dict) else None
        if not isinstance(member, dict):
            member = data if isinstance(data, dict) else {}
        names: list[str] = []
        ids: list[str] = []
        # Some payloads nest committee assignments under terms[].
        for term in member.get("terms") or []:
            if not isinstance(term, dict):
                continue
            for c in term.get("committees") or []:
                if isinstance(c, dict):
                    n = c.get("name") or c.get("systemCode")
                    if n:
                        names.append(str(n))
                    cid = c.get("systemCode") or c.get("code")
                    if cid:
                        ids.append(str(cid))
        return ids, names
    except Exception as e:
        logger.debug("committee resolve %s: %s", bioguide_id, e)
        return [], []


def _assign_bipartisan_clusters(
    rows: list[dict[str, Any]],
    *,
    window_days: int,
) -> dict[str, str]:
    """
    Same ticker + opposite major parties within window of filed_date → shared cluster id.
    Returns quiver_trade_id → cluster_id.
    """
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        t = (r.get("ticker") or "").upper()
        if t:
            by_ticker.setdefault(t, []).append(r)

    out: dict[str, str] = {}
    for ticker, group in by_ticker.items():
        group = sorted(group, key=lambda x: x.get("filed_date") or date.min)
        for i, a in enumerate(group):
            party_a = (a.get("party") or "").lower()
            filed_a = a.get("filed_date")
            if not filed_a:
                continue
            for b in group[i + 1 :]:
                filed_b = b.get("filed_date")
                if not filed_b:
                    continue
                if abs((filed_b - filed_a).days) > window_days:
                    if filed_b > filed_a + timedelta(days=window_days):
                        break
                    continue
                party_b = (b.get("party") or "").lower()
                opposite = (
                    ("dem" in party_a and "rep" in party_b)
                    or ("rep" in party_a and "dem" in party_b)
                )
                if not opposite:
                    continue
                cid = f"{ticker}:{min(filed_a, filed_b).isoformat()}"
                out[str(a["quiver_trade_id"])] = cid
                out[str(b["quiver_trade_id"])] = cid
    return out


def enrich_congress_trades(*, limit: int = 500, days_back: int | None = 365) -> dict[str, Any]:
    """Idempotent upsert into congress_trade_enrichment for recent Quiver trades."""
    if not is_enabled():
        return {"ok": False, "error": "feature_disabled"}

    cfg = load_congress_trade_config()
    window = int((cfg.get("enrichment") or {}).get("bipartisan_cluster_window_days") or 14)
    today = _today()

    from shared.database.connection import get_db_connection_context
    from psycopg2.extras import RealDictCursor

    upserted = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                params: list[Any] = [max(1, min(int(limit), 5000))]
                date_clause = ""
                if days_back is not None:
                    date_clause = "AND filed_date >= %s"
                    params.insert(0, today - timedelta(days=max(1, int(days_back))))
                cur.execute(
                    f"""
                    SELECT quiver_trade_id, politician_bioguide_id, party, ticker,
                           transaction_type, amount_range, traded_date, filed_date
                    FROM intelligence.quiver_congress_trades
                    WHERE ticker IS NOT NULL
                      {date_clause}
                    ORDER BY filed_date DESC NULLS LAST
                    LIMIT %s
                    """,
                    params,
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
                clusters = _assign_bipartisan_clusters(rows, window_days=window)

                # Cache committees per bioguide within this run
                committee_cache: dict[str, tuple[list[str], list[str]]] = {}

                for r in rows:
                    bid = r.get("politician_bioguide_id")
                    if bid and bid not in committee_cache:
                        committee_cache[bid] = _resolve_committees(bid, cfg)
                    c_ids, c_names = committee_cache.get(bid or "", ([], []))
                    side = normalize_side(r.get("transaction_type"))
                    mid, ordinal = amount_bucket(r.get("amount_range"), cfg)
                    sector = issuer_sector(r.get("ticker"), cfg)
                    lead = leadership_weight(bid, cfg)
                    lag = lag_days(r.get("traded_date"), r.get("filed_date"))
                    fresh = freshness_days(r.get("filed_date"), today=today)
                    cluster = clusters.get(str(r["quiver_trade_id"]))
                    cur.execute(
                        """
                        INSERT INTO intelligence.congress_trade_enrichment (
                            quiver_trade_id, lag_days, amount_bucket_mid, amount_ordinal,
                            side, committee_ids, committee_names, issuer_sector,
                            leadership_weight, bipartisan_cluster_id,
                            disclosure_freshness_days, enrichment_meta, enriched_at, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW()
                        )
                        ON CONFLICT (quiver_trade_id) DO UPDATE SET
                            lag_days = EXCLUDED.lag_days,
                            amount_bucket_mid = EXCLUDED.amount_bucket_mid,
                            amount_ordinal = EXCLUDED.amount_ordinal,
                            side = EXCLUDED.side,
                            committee_ids = EXCLUDED.committee_ids,
                            committee_names = EXCLUDED.committee_names,
                            issuer_sector = EXCLUDED.issuer_sector,
                            leadership_weight = EXCLUDED.leadership_weight,
                            bipartisan_cluster_id = EXCLUDED.bipartisan_cluster_id,
                            disclosure_freshness_days = EXCLUDED.disclosure_freshness_days,
                            enrichment_meta = EXCLUDED.enrichment_meta,
                            updated_at = NOW()
                        """,
                        (
                            r["quiver_trade_id"],
                            lag,
                            mid,
                            ordinal,
                            side,
                            c_ids,
                            c_names,
                            sector,
                            lead,
                            cluster,
                            fresh,
                            json.dumps({"source": "congress_trade_enricher"}),
                        ),
                    )
                    upserted += 1
            conn.commit()
    except Exception as e:
        logger.warning("enrich_congress_trades: %s", e)
        return {"ok": False, "error": str(e)[:300], "upserted": upserted}

    return {"ok": True, "upserted": upserted, "rows_seen": len(rows)}


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_congress_trades(*, limit: int = 500) -> dict[str, Any]:
    """Score enrichment rows into congress_trade_signals (as_of = filed_date)."""
    if not is_enabled():
        return {"ok": False, "error": "feature_disabled"}

    cfg = load_congress_trade_config()
    from shared.database.connection import get_db_connection_context
    from psycopg2.extras import RealDictCursor

    written = 0
    eligible_n = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT e.*, q.ticker, q.filed_date
                    FROM intelligence.congress_trade_enrichment e
                    JOIN intelligence.quiver_congress_trades q
                      ON q.quiver_trade_id = e.quiver_trade_id
                    WHERE q.filed_date IS NOT NULL
                    ORDER BY q.filed_date DESC
                    LIMIT %s
                    """,
                    (max(1, min(int(limit), 5000)),),
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
                for r in rows:
                    overlap = committee_sector_overlap(
                        list(r.get("committee_names") or []),
                        r.get("issuer_sector"),
                        cfg,
                    )
                    score, parts, eligible = score_enriched_trade(
                        side=r.get("side") or "other",
                        amount_ordinal=int(r.get("amount_ordinal") or 0),
                        lag_days=r.get("lag_days"),
                        has_bipartisan_cluster=bool(r.get("bipartisan_cluster_id")),
                        committee_overlap=overlap,
                        leadership_w=float(r.get("leadership_weight") or 1.0),
                        disclosure_freshness_days=r.get("disclosure_freshness_days"),
                        cfg=cfg,
                    )
                    paper_w = score if eligible else None
                    cur.execute(
                        """
                        INSERT INTO intelligence.congress_trade_signals (
                            quiver_trade_id, ticker, signal_score, score_parts,
                            eligible, paper_weight, as_of_date, updated_at
                        ) VALUES (
                            %s, %s, %s, %s::jsonb, %s, %s, %s, NOW()
                        )
                        ON CONFLICT (quiver_trade_id) DO UPDATE SET
                            ticker = EXCLUDED.ticker,
                            signal_score = EXCLUDED.signal_score,
                            score_parts = EXCLUDED.score_parts,
                            eligible = EXCLUDED.eligible,
                            paper_weight = EXCLUDED.paper_weight,
                            as_of_date = EXCLUDED.as_of_date,
                            updated_at = NOW()
                        """,
                        (
                            r["quiver_trade_id"],
                            (r.get("ticker") or "").upper(),
                            score,
                            json.dumps(parts),
                            eligible,
                            paper_w,
                            r["filed_date"],
                        ),
                    )
                    written += 1
                    if eligible:
                        eligible_n += 1
            conn.commit()
    except Exception as e:
        logger.warning("score_congress_trades: %s", e)
        return {"ok": False, "error": str(e)[:300], "written": written}

    return {"ok": True, "written": written, "eligible": eligible_n}


# ---------------------------------------------------------------------------
# Paper portfolio (monthly, disclosure-dated)
# ---------------------------------------------------------------------------


def _close_on_or_before(rows: list[dict[str, Any]], as_of: date) -> float | None:
    """rows newest-last Stooq daily; pick last close with date <= as_of."""
    best = None
    for r in rows:
        d_raw = r.get("date")
        if not d_raw:
            continue
        try:
            d = date.fromisoformat(str(d_raw)[:10])
        except ValueError:
            continue
        if d <= as_of:
            best = float(r["close"])
    return best


def rebuild_monthly_paper_portfolio(*, as_of_month: date | None = None) -> dict[str, Any]:
    """
    Rebuild positions for a calendar month using only signals with as_of_date < month_start
    (no look-ahead into the month being traded). Marks NAV vs SPY at month end.
    """
    if not is_enabled():
        return {"ok": False, "error": "feature_disabled"}

    cfg = load_congress_trade_config()
    paper = cfg.get("paper") or {}
    max_pos = int(paper.get("max_positions") or 20)
    max_sector = float(paper.get("max_sector_weight") or 0.25)
    max_single = float(paper.get("max_single_weight") or 0.10)
    start_nav = float(paper.get("starting_nav") or 100.0)
    bench = str(paper.get("benchmark_ticker") or "SPY").upper()

    month = _month_start(as_of_month or _today())
    # Selection cutoff: end of prior month — never use filings from the trade month
    cutoff = _prev_month_end(month)
    last_day = date(month.year, month.month, monthrange(month.year, month.month)[1])
    mark_date = min(last_day, _today())

    from shared.database.connection import get_db_connection_context
    from psycopg2.extras import RealDictCursor
    from services.trading_signals_service import fetch_stooq_daily_csv

    try:
        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT s.id, s.ticker, s.signal_score, s.paper_weight, s.as_of_date,
                           e.issuer_sector, e.side
                    FROM intelligence.congress_trade_signals s
                    LEFT JOIN intelligence.congress_trade_enrichment e
                      ON e.quiver_trade_id = s.quiver_trade_id
                    WHERE s.eligible = TRUE
                      AND s.as_of_date <= %s
                      AND COALESCE(e.side, 'buy') = 'buy'
                    ORDER BY s.signal_score DESC, s.as_of_date DESC
                    LIMIT 200
                    """,
                    (cutoff,),
                )
                candidates = [dict(r) for r in (cur.fetchall() or [])]

                # Dedupe by ticker (best score wins); apply sector + single caps
                picked: list[dict[str, Any]] = []
                seen_ticker: set[str] = set()
                sector_w: dict[str, float] = {}
                raw_weight = 1.0 / max(1, min(max_pos, len(candidates) or 1))

                for c in candidates:
                    ticker = (c.get("ticker") or "").upper()
                    if not ticker or ticker in seen_ticker:
                        continue
                    sector = (c.get("issuer_sector") or "other").lower()
                    w = min(max_single, raw_weight)
                    if sector_w.get(sector, 0.0) + w > max_sector + 1e-9:
                        continue
                    seen_ticker.add(ticker)
                    sector_w[sector] = sector_w.get(sector, 0.0) + w
                    c["weight"] = w
                    picked.append(c)
                    if len(picked) >= max_pos:
                        break

                # Renormalize weights to sum <= 1
                total_w = sum(float(p["weight"]) for p in picked) or 1.0
                if total_w > 1.0:
                    for p in picked:
                        p["weight"] = float(p["weight"]) / total_w

                cur.execute(
                    "DELETE FROM intelligence.congress_paper_positions WHERE as_of_month = %s",
                    (month,),
                )
                # Mark NAV vs SPY (entry = last close on/before prior-month cutoff)
                port_ret = 0.0
                for p in picked:
                    rows = fetch_stooq_daily_csv(p["ticker"], max_rows=80)
                    entry = _close_on_or_before(rows, cutoff)
                    mark = _close_on_or_before(rows, mark_date)
                    p["entry_price"] = entry
                    if entry and mark and entry > 0:
                        port_ret += float(p["weight"]) * ((mark / entry) - 1.0)
                    cur.execute(
                        """
                        INSERT INTO intelligence.congress_paper_positions (
                            as_of_month, ticker, weight, side, signal_ids, sector,
                            entry_price, metadata
                        ) VALUES (%s, %s, %s, 'long', %s, %s, %s, %s::jsonb)
                        """,
                        (
                            month,
                            p["ticker"],
                            float(p["weight"]),
                            [int(p["id"])],
                            p.get("issuer_sector"),
                            entry,
                            json.dumps({"cutoff": cutoff.isoformat(), "score": p.get("signal_score")}),
                        ),
                    )
                cash = max(0.0, 1.0 - sum(float(p["weight"]) for p in picked))
                nav = start_nav * (1.0 + port_ret)

                spy_rows = fetch_stooq_daily_csv(bench, max_rows=80)
                spy_entry = _close_on_or_before(spy_rows, cutoff)
                spy_mark = _close_on_or_before(spy_rows, mark_date)
                spy_nav = None
                if spy_entry and spy_mark and spy_entry > 0:
                    spy_nav = start_nav * (spy_mark / spy_entry)

                cur.execute(
                    """
                    INSERT INTO intelligence.congress_paper_nav (
                        as_of_date, nav, spy_nav, cash_weight, positions_count, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (as_of_date) DO UPDATE SET
                        nav = EXCLUDED.nav,
                        spy_nav = EXCLUDED.spy_nav,
                        cash_weight = EXCLUDED.cash_weight,
                        positions_count = EXCLUDED.positions_count,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        mark_date,
                        nav,
                        spy_nav,
                        cash,
                        len(picked),
                        json.dumps(
                            {
                                "month": month.isoformat(),
                                "cutoff": cutoff.isoformat(),
                                "benchmark": bench,
                                "look_ahead_impossible": True,
                            }
                        ),
                    ),
                )
            conn.commit()
    except Exception as e:
        logger.warning("rebuild_monthly_paper_portfolio: %s", e)
        return {"ok": False, "error": str(e)[:300]}

    return {
        "ok": True,
        "month": month.isoformat(),
        "cutoff": cutoff.isoformat(),
        "positions": len(picked),
        "nav": nav,
        "spy_nav": spy_nav,
        "mark_date": mark_date.isoformat(),
    }


# ---------------------------------------------------------------------------
# HITL promotion
# ---------------------------------------------------------------------------


def promote_to_trading_signals(*, top_n: int | None = None) -> dict[str, Any]:
    """Insert top eligible congress signals into intelligence.trading_signals (pending)."""
    if not is_enabled():
        return {"ok": False, "error": "feature_disabled"}

    cfg = load_congress_trade_config()
    hitl = cfg.get("hitl") or {}
    n = int(top_n if top_n is not None else hitl.get("top_n_per_day") or 10)
    min_score = float(hitl.get("min_score") or 0.65)
    source = str(hitl.get("metadata_source") or "congress_quiver")
    today = _today()

    from shared.database.connection import get_db_connection_context
    from psycopg2.extras import RealDictCursor

    created = 0
    skipped = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT s.id, s.quiver_trade_id, s.ticker, s.signal_score, s.as_of_date,
                           s.hitl_signal_id, e.side, e.lag_days, q.politician_name, q.amount_range
                    FROM intelligence.congress_trade_signals s
                    JOIN intelligence.quiver_congress_trades q
                      ON q.quiver_trade_id = s.quiver_trade_id
                    LEFT JOIN intelligence.congress_trade_enrichment e
                      ON e.quiver_trade_id = s.quiver_trade_id
                    WHERE s.eligible = TRUE
                      AND s.signal_score >= %s
                      AND s.hitl_signal_id IS NULL
                      AND s.as_of_date >= %s
                    ORDER BY s.signal_score DESC
                    LIMIT %s
                    """,
                    (min_score, today - timedelta(days=14), max(1, min(n, 50))),
                )
                rows = [dict(r) for r in (cur.fetchall() or [])]
                for r in rows:
                    summary = (
                        f"Congress {r.get('side') or 'trade'} {r['ticker']} "
                        f"by {r.get('politician_name') or 'member'} "
                        f"(score={float(r['signal_score']):.2f}, lag={r.get('lag_days')}, "
                        f"amt={r.get('amount_range') or '?'}) — HITL only, no auto-exec"
                    )
                    direction = "up" if (r.get("side") or "buy") == "buy" else "down"
                    meta = {
                        "source": source,
                        "quiver_trade_id": r["quiver_trade_id"],
                        "congress_signal_id": int(r["id"]),
                        "as_of_date": r["as_of_date"].isoformat()
                        if hasattr(r["as_of_date"], "isoformat")
                        else str(r["as_of_date"]),
                        "direction": direction,
                        "no_auto_execution": True,
                    }
                    cur.execute(
                        """
                        INSERT INTO intelligence.trading_signals (
                            impact_id, ticker, idea_summary, expected_move_pct,
                            confidence, review_status, metadata
                        ) VALUES (
                            NULL, %s, %s, %s, %s, 'pending', %s::jsonb
                        )
                        RETURNING id
                        """,
                        (
                            r["ticker"],
                            summary,
                            1.0 if direction == "up" else -1.0,
                            float(r["signal_score"]),
                            json.dumps(meta),
                        ),
                    )
                    sid_row = cur.fetchone()
                    if not sid_row:
                        skipped += 1
                        continue
                    hitl_id = int(sid_row["id"])
                    cur.execute(
                        """
                        UPDATE intelligence.congress_trade_signals
                        SET hitl_signal_id = %s, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (hitl_id, int(r["id"])),
                    )
                    created += 1
            conn.commit()
    except Exception as e:
        logger.warning("promote_to_trading_signals: %s", e)
        return {"ok": False, "error": str(e)[:300], "created": created}

    return {"ok": True, "created": created, "skipped": skipped}


# ---------------------------------------------------------------------------
# Pipeline + read APIs
# ---------------------------------------------------------------------------


def run_congress_trade_signals_pipeline(
    *,
    enrich_limit: int = 500,
    score_limit: int = 500,
    rebuild_paper: bool = True,
    promote_hitl: bool = True,
) -> dict[str, Any]:
    if not is_enabled():
        return {"ok": False, "error": "feature_disabled"}
    out: dict[str, Any] = {"ok": True}
    out["enrich"] = enrich_congress_trades(limit=enrich_limit)
    out["score"] = score_congress_trades(limit=score_limit)
    if rebuild_paper:
        out["paper"] = rebuild_monthly_paper_portfolio()
    if promote_hitl:
        out["hitl"] = promote_to_trading_signals()
    out["ok"] = all(
        (out.get(k) or {}).get("ok", True)
        for k in ("enrich", "score", "paper", "hitl")
        if k in out
    )
    return out


def list_congress_signals(
    *,
    eligible_only: bool = True,
    limit: int = 50,
) -> list[dict[str, Any]]:
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    where = "WHERE eligible = TRUE" if eligible_only else ""
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    f"""
                    SELECT id, quiver_trade_id, ticker, signal_score, score_parts,
                           eligible, paper_weight, as_of_date, hitl_signal_id,
                           created_at, updated_at
                    FROM intelligence.congress_trade_signals
                    {where}
                    ORDER BY signal_score DESC, as_of_date DESC
                    LIMIT %s
                    """,
                    (max(1, min(int(limit), 200)),),
                )
                return [dict(r) for r in (cur.fetchall() or [])]
    except Exception as e:
        logger.debug("list_congress_signals: %s", e)
        return []


def get_paper_portfolio(*, months: int = 12) -> dict[str, Any]:
    from shared.database.connection import get_ui_db_connection_context
    from psycopg2.extras import RealDictCursor

    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT as_of_date, nav, spy_nav, cash_weight, positions_count, metadata
                    FROM intelligence.congress_paper_nav
                    ORDER BY as_of_date DESC
                    LIMIT %s
                    """,
                    (max(1, min(int(months) * 3, 100)),),
                )
                nav_rows = [dict(r) for r in (cur.fetchall() or [])]
                cur.execute(
                    """
                    SELECT as_of_month, ticker, weight, side, sector, entry_price, signal_ids
                    FROM intelligence.congress_paper_positions
                    WHERE as_of_month = (
                        SELECT MAX(as_of_month) FROM intelligence.congress_paper_positions
                    )
                    ORDER BY weight DESC
                    """
                )
                positions = [dict(r) for r in (cur.fetchall() or [])]
        return {
            "nav_history": nav_rows,
            "latest_positions": positions,
            "no_live_brokerage": True,
        }
    except Exception as e:
        logger.debug("get_paper_portfolio: %s", e)
        return {"nav_history": [], "latest_positions": [], "error": str(e)[:200]}
