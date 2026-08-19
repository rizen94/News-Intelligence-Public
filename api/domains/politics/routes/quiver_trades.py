"""
Politics — Quiver Quantitative Congressional Trading Data.

Paths: ``/api/politics/congress/...`` — congressional stock trades, politician profiles, analytics.
Data sourced from Quiver Quantitative API, stored in intelligence.quiver_congress_trades.
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/politics/congress",
    tags=["Politics — Congressional Trading"],
    responses={404: {"description": "Not found"}},
)


@router.get("/trades")
async def get_congress_trades(
    days: int = Query(30, ge=1, le=365, description="Days back to search"),
    politician: str | None = Query(None, description="Filter by politician name (partial match)"),
    ticker: str | None = Query(None, description="Filter by stock ticker (e.g., AAPL)"),
    chamber: str | None = Query(None, description="Filter by chamber: Senate or House"),
    party: str | None = Query(None, description="Filter by party: Democrat, Republican, Independent"),
    transaction_type: str | None = Query(None, description="Filter by type: Purchase, Sale, Exchange"),
    min_amount: str | None = Query(None, description="Minimum amount range (e.g., $15,001)"),
    limit: int = Query(100, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict[str, Any]:
    """Get congressional trades with filters."""
    
    conditions = ["filed_date >= %s"]
    params = [date.today() - timedelta(days=days)]
    
    if politician:
        conditions.append("politician_name ILIKE %s")
        params.append(f"%{politician}%")
    
    if ticker:
        conditions.append("ticker = %s")
        params.append(ticker.upper())
    
    if chamber:
        conditions.append("chamber ILIKE %s")
        params.append(f"%{chamber}%")
    
    if party:
        conditions.append("party ILIKE %s")
        params.append(f"%{party}%")
    
    if transaction_type:
        conditions.append("transaction_type ILIKE %s")
        params.append(f"%{transaction_type}%")
    
    if min_amount:
        conditions.append("amount_range ILIKE %s")
        params.append(f"%{min_amount}%")
    
    where_clause = " AND ".join(conditions)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Get total count
            cur.execute(f"""
                SELECT COUNT(*) FROM intelligence.quiver_congress_trades
                WHERE {where_clause}
            """, params)
            total = cur.fetchone()[0]
            
            # Get paginated results
            params.extend([limit, offset])
            cur.execute(f"""
                SELECT id, quiver_trade_id, politician_name, politician_bioguide_id,
                       chamber, party, state, ticker, company_name, transaction_type,
                       amount_range, traded_date, filed_date, owner_type,
                       created_at
                FROM intelligence.quiver_congress_trades
                WHERE {where_clause}
                ORDER BY filed_date DESC, created_at DESC
                LIMIT %s OFFSET %s
            """, params)
            
            cols = [desc[0] for desc in cur.description]
            trades = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Convert dates to ISO strings for JSON
            for trade in trades:
                for key in ["traded_date", "filed_date", "created_at"]:
                    if trade.get(key):
                        trade[key] = trade[key].isoformat() if hasattr(trade[key], "isoformat") else str(trade[key])
    
    return {
        "success": True,
        "data": trades,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total
        },
        "filters": {
            "days": days,
            "politician": politician,
            "ticker": ticker,
            "chamber": chamber,
            "party": party,
            "transaction_type": transaction_type
        }
    }


@router.get("/trades/summary")
async def get_congress_trade_summary(
    days: int = Query(30, ge=1, le=365, description="Days back for summary"),
) -> dict[str, Any]:
    """Get aggregated congressional trading statistics."""
    
    cutoff = date.today() - timedelta(days=days)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Overall stats
            cur.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(DISTINCT politician_name) as unique_politicians,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    COUNT(DISTINCT politician_bioguide_id) as unique_politicians_id,
                    SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                    SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
                    SUM(CASE WHEN transaction_type ILIKE '%exchange%' THEN 1 ELSE 0 END) as exchanges,
                    SUM(CASE WHEN chamber ILIKE 'senate' THEN 1 ELSE 0 END) as senate_trades,
                    SUM(CASE WHEN chamber ILIKE 'house' THEN 1 ELSE 0 END) as house_trades,
                    MIN(filed_date) as earliest_trade,
                    MAX(filed_date) as latest_trade
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s
            """, (cutoff,))
            stats = cur.fetchone()
            stat_cols = [desc[0] for desc in cur.description]
            summary = dict(zip(stat_cols, stats))
            
            # Top politicians by trade count
            cur.execute("""
                SELECT politician_name, politician_bioguide_id, chamber, party, state,
                       COUNT(*) as trade_count,
                       COUNT(DISTINCT ticker) as unique_tickers,
                       SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                       SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
                       MAX(filed_date) as latest_trade
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s
                GROUP BY politician_name, politician_bioguide_id, chamber, party, state
                ORDER BY trade_count DESC
                LIMIT 20
            """, (cutoff,))
            cols = [desc[0] for desc in cur.description]
            top_politicians = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Most traded tickers
            cur.execute("""
                SELECT ticker, company_name,
                       COUNT(*) as trade_count,
                       COUNT(DISTINCT politician_name) as unique_politicians,
                       SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                       SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
                       MAX(filed_date) as latest_trade
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s
                GROUP BY ticker, company_name
                ORDER BY trade_count DESC
                LIMIT 20
            """, (cutoff,))
            cols = [desc[0] for desc in cur.description]
            top_tickers = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Party breakdown
            cur.execute("""
                SELECT party, 
                       COUNT(*) as trade_count,
                       COUNT(DISTINCT politician_name) as unique_politicians,
                       SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                       SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s AND party IS NOT NULL
                GROUP BY party
                ORDER BY trade_count DESC
            """, (cutoff,))
            cols = [desc[0] for desc in cur.description]
            party_breakdown = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Chamber breakdown
            cur.execute("""
                SELECT chamber, 
                       COUNT(*) as trade_count,
                       COUNT(DISTINCT politician_name) as unique_politicians,
                       SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                       SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s AND chamber IS NOT NULL
                GROUP BY chamber
                ORDER BY trade_count DESC
            """, (cutoff,))
            cols = [desc[0] for desc in cur.description]
            chamber_breakdown = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            # Amount range distribution
            cur.execute("""
                SELECT amount_range, COUNT(*) as count
                FROM intelligence.quiver_congress_trades
                WHERE filed_date >= %s AND amount_range IS NOT NULL
                GROUP BY amount_range
                ORDER BY 
                    CASE amount_range
                        WHEN '$1,001 - $15,000' THEN 1
                        WHEN '$15,001 - $50,000' THEN 2
                        WHEN '$50,001 - $100,000' THEN 3
                        WHEN '$100,001 - $250,000' THEN 4
                        WHEN '$250,001 - $500,000' THEN 5
                        WHEN '$500,001 - $1,000,000' THEN 6
                        WHEN '$1,000,001 - $5,000,000' THEN 7
                        WHEN '$5,000,001 - $25,000,000' THEN 8
                        WHEN '$25,000,001 - $50,000,000' THEN 9
                        WHEN 'Over $50,000,000' THEN 10
                        ELSE 11
                    END
            """, (cutoff,))
            cols = [desc[0] for desc in cur.description]
            amount_distribution = [dict(zip(cols, row)) for row in cur.fetchall()]
    
    # Convert dates in summary
    for key in ["earliest_trade", "latest_trade"]:
        if summary.get(key):
            summary[key] = summary[key].isoformat() if hasattr(summary[key], "isoformat") else str(summary[key])
    
    for pol in top_politicians:
        if pol.get("latest_trade"):
            pol["latest_trade"] = pol["latest_trade"].isoformat() if hasattr(pol["latest_trade"], "isoformat") else str(pol["latest_trade"])
    
    for ticker in top_tickers:
        if ticker.get("latest_trade"):
            ticker["latest_trade"] = ticker["latest_trade"].isoformat() if hasattr(ticker["latest_trade"], "isoformat") else str(ticker["latest_trade"])
    
    return {
        "success": True,
        "data": {
            "period_days": days,
            "summary": summary,
            "top_politicians": top_politicians,
            "top_tickers": top_tickers,
            "party_breakdown": party_breakdown,
            "chamber_breakdown": chamber_breakdown,
            "amount_distribution": amount_distribution
        }
    }


@router.get("/trades/politician/{politician_name}")
async def get_politician_trades(
    politician_name: str,
    days: int = Query(365, ge=1, le=1825, description="Days back (default 1 year)"),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    """Get all trades for a specific politician."""
    
    cutoff = date.today() - timedelta(days=days)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, quiver_trade_id, politician_name, politician_bioguide_id,
                       chamber, party, state, ticker, company_name, transaction_type,
                       amount_range, traded_date, filed_date, owner_type, created_at
                FROM intelligence.quiver_congress_trades
                WHERE politician_name ILIKE %s AND filed_date >= %s
                ORDER BY filed_date DESC, traded_date DESC
                LIMIT %s
            """, (f"%{politician_name}%", cutoff, limit))
            
            cols = [desc[0] for desc in cur.description]
            trades = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            for trade in trades:
                for key in ["traded_date", "filed_date", "created_at"]:
                    if trade.get(key):
                        trade[key] = trade[key].isoformat() if hasattr(trade[key], "isoformat") else str(trade[key])
            
            # Get summary for this politician
            cur.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(DISTINCT ticker) as unique_tickers,
                    SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                    SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
                    MIN(filed_date) as first_trade,
                    MAX(filed_date) as latest_trade,
                    chamber, party, state
                FROM intelligence.quiver_congress_trades
                WHERE politician_name ILIKE %s
                GROUP BY chamber, party, state
            """, (f"%{politician_name}%",))
            summary = cur.fetchone()
            summary_cols = [desc[0] for desc in cur.description]
            summary_dict = dict(zip(summary_cols, summary)) if summary else {}
            if summary_dict:
                for key in ["first_trade", "latest_trade"]:
                    if summary_dict.get(key):
                        summary_dict[key] = summary_dict[key].isoformat() if hasattr(summary_dict[key], "isoformat") else str(summary_dict[key])
    
    return {
        "success": True,
        "data": {
            "politician": politician_name,
            "summary": summary_dict,
            "trades": trades,
            "count": len(trades)
        }
    }


@router.get("/trades/ticker/{ticker}")
async def get_ticker_congress_activity(
    ticker: str,
    days: int = Query(365, ge=1, le=1825, description="Days back (default 1 year)"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Get congressional trading activity for a specific ticker."""
    
    cutoff = date.today() - timedelta(days=days)
    ticker = ticker.upper()
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, quiver_trade_id, politician_name, politician_bioguide_id,
                       chamber, party, state, ticker, company_name, transaction_type,
                       amount_range, traded_date, filed_date, owner_type, created_at
                FROM intelligence.quiver_congress_trades
                WHERE ticker = %s AND filed_date >= %s
                ORDER BY filed_date DESC
                LIMIT %s
            """, (ticker, cutoff, limit))
            
            cols = [desc[0] for desc in cur.description]
            trades = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            for trade in trades:
                for key in ["traded_date", "filed_date", "created_at"]:
                    if trade.get(key):
                        trade[key] = trade[key].isoformat() if hasattr(trade[key], "isoformat") else str(trade[key])
            
            # Summary
            cur.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    COUNT(DISTINCT politician_name) as unique_politicians,
                    SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END) as purchases,
                    SUM(CASE WHEN transaction_type ILIKE '%sale%' THEN 1 ELSE 0 END) as sales,
                    SUM(CASE WHEN chamber ILIKE 'senate' THEN 1 ELSE 0 END) as senate_trades,
                    SUM(CASE WHEN chamber ILIKE 'house' THEN 1 ELSE 0 END) as house_trades,
                    MIN(filed_date) as earliest_trade,
                    MAX(filed_date) as latest_trade
                FROM intelligence.quiver_congress_trades
                WHERE ticker = %s AND filed_date >= %s
            """, (ticker, cutoff))
            summary = cur.fetchone()
            summary_cols = [desc[0] for desc in cur.description]
            summary_dict = dict(zip(summary_cols, summary)) if summary else {}
            if summary_dict:
                for key in ["earliest_trade", "latest_trade"]:
                    if summary_dict.get(key):
                        summary_dict[key] = summary_dict[key].isoformat() if hasattr(summary_dict[key], "isoformat") else str(summary_dict[key])
    
    return {
        "success": True,
        "data": {
            "ticker": ticker,
            "summary": summary_dict,
            "trades": trades,
            "count": len(trades)
        }
    }


@router.get("/politicians/top")
async def get_top_politicians(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get most active congressional traders."""
    
    cutoff = date.today() - timedelta(days=days)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM intelligence.quiver_politician_trade_summary
                WHERE latest_trade_date >= %s
                ORDER BY total_trades DESC
                LIMIT %s
            """, (cutoff, limit))
            
            cols = [desc[0] for desc in cur.description]
            politicians = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            for p in politicians:
                for key in ["first_trade_date", "latest_trade_date"]:
                    if p.get(key):
                        p[key] = p[key].isoformat() if hasattr(p[key], "isoformat") else str(p[key])
    
    return {
        "success": True,
        "data": politicians,
        "period_days": days
    }


@router.get("/tickers/top")
async def get_top_tickers(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """Get most traded tickers by Congress."""
    
    cutoff = date.today() - timedelta(days=days)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM intelligence.quiver_ticker_congress_activity
                WHERE latest_trade_date >= %s
                ORDER BY total_trades DESC
                LIMIT %s
            """, (cutoff, limit))
            
            cols = [desc[0] for desc in cur.description]
            tickers = [dict(zip(cols, row)) for row in cur.fetchall()]
            
            for t in tickers:
                if t.get("latest_trade_date"):
                    t["latest_trade_date"] = t["latest_trade_date"].isoformat() if hasattr(t["latest_trade_date"], "isoformat") else str(t["latest_trade_date"])
    
    return {
        "success": True,
        "data": tickers,
        "period_days": days
    }