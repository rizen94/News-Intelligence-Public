"""
Quiver Correlation Service - Cross-references Quiver trades with article contexts
to generate intelligence alerts and storyline triggers.
"""
import logging
from datetime import datetime, timedelta
from typing import Any

from shared.database.connection import get_db_connection_context
from services.quiver_entity_resolver import (
    increment_politician_trade_count,
    resolve_politician_entity,
)

logger = logging.getLogger(__name__)


def correlate_congress_trades_with_contexts(days_back: int = 7) -> dict[str, Any]:
    """
    Find article contexts mentioning tickers traded by Congress within ±7 days of filing.
    Creates content_refinement_queue entries for high-priority correlation.
    """
    if days_back > 30:
        days_back = 30  # Cap to prevent excessive queries
    
    cutoff = datetime.now() - timedelta(days=days_back)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Get recent congressional trades
            cur.execute("""
                SELECT 
                    qct.id as trade_id,
                    qct.ticker,
                    qct.company_name,
                    qct.politician_name,
                    qct.politician_bioguide_id,
                    qct.chamber,
                    qct.party,
                    qct.state,
                    qct.transaction_type,
                    qct.amount_range,
                    qct.filed_date,
                    qct.traded_date
                FROM intelligence.quiver_congress_trades qct
                WHERE qct.filed_date >= %s
                ORDER BY qct.filed_date DESC
            """, (cutoff.date(),))
            
            trades = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            
            if not trades:
                return {"trades_checked": 0, "correlations_found": 0, "alerts_created": 0}
            
            alerts_created = 0
            correlations = 0
            
            for trade_row in trades:
                trade = dict(zip(cols, trade_row))
                ticker = trade.get("ticker")
                if not ticker:
                    continue
                
                # Search for contexts mentioning this ticker around trade date
                trade_filed = trade.get("filed_date")
                if not trade_filed:
                    continue
                
                window_start = trade_filed - timedelta(days=7)
                window_end = trade_filed + timedelta(days=7)
                
                # Find contexts with ticker in metadata or content
                cur.execute("""
                    SELECT 
                        c.id as context_id,
                        c.title,
                        c.domain_key,
                        c.created_at,
                        c.metadata,
                        a.url,
                        a.source_name
                    FROM intelligence.contexts c
                    JOIN intelligence.articles a ON a.id = c.id
                    WHERE c.created_at BETWEEN %s AND %s
                    AND (
                        c.metadata->>'tickers' ILIKE %s
                        OR c.content ILIKE %s
                        OR c.title ILIKE %s
                        OR a.url ILIKE %s
                    )
                    ORDER BY c.created_at DESC
                    LIMIT 20
                """, (
                    window_start, window_end,
                    f"%{ticker}%", f"%{ticker}%", f"%{ticker}%", f"%{ticker}%"
                ))
                
                related_contexts = cur.fetchall()
                context_cols = [desc[0] for desc in cur.description]
                
                if related_contexts:
                    correlations += 1
                    
                    # Create politician entity if not exists
                    resolve_politician_entity(
                        trade["politician_name"],
                        trade.get("politician_bioguide_id"),
                        trade.get("chamber"),
                        trade.get("party"),
                        trade.get("state")
                    )
                    increment_politician_trade_count(
                        trade["politician_name"],
                        trade.get("politician_bioguide_id")
                    )
                    
                    # Create refinement queue entry for top context
                    top_context = dict(zip(context_cols, related_contexts[0]))
                    
                    priority = _calculate_priority(trade, top_context)
                    
                    cur.execute("""
                        INSERT INTO intelligence.content_refinement_queue
                        (context_id, priority, reason, metadata, created_at)
                        VALUES (%s, %s, %s, %s::jsonb, NOW())
                        ON CONFLICT (context_id) DO UPDATE SET
                            priority = GREATEST(intelligence.content_refinement_queue.priority, EXCLUDED.priority),
                            reason = EXCLUDED.reason,
                            metadata = EXCLUDED.metadata,
                            created_at = NOW()
                        WHERE intelligence.content_refinement_queue.priority < EXCLUDED.priority
                    """, (
                        top_context["context_id"],
                        priority,
                        _format_correlation_reason(trade, len(related_contexts)),
                        json.dumps({
                            "quiver_trade_id": trade["trade_id"],
                            "ticker": ticker,
                            "politician": trade["politician_name"],
                            "chamber": trade["chamber"],
                            "party": trade["party"],
                            "transaction_type": trade["transaction_type"],
                            "amount_range": trade["amount_range"],
                            "filed_date": trade["filed_date"].isoformat() if trade_filed else None,
                            "correlated_contexts": len(related_contexts),
                            "top_context_title": top_context["title"][:200],
                            "correlation_type": "congress_trade_article_match"
                        })
                    ))
                    alerts_created += 1
            
            conn.commit()
            
            return {
                "trades_checked": len(trades),
                "correlations_found": correlations,
                "alerts_created": alerts_created
            }


def _calculate_priority(trade: dict, context: dict) -> int:
    """Calculate priority for refinement queue (0-100)."""
    priority = 50  # Base
    
    # High-value tickers (large cap, defense, tech)
    high_value_tickers = {"AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "LMT", "RTX", "NOC", "BA"}
    if trade.get("ticker") in high_value_tickers:
        priority += 20
    
    # Large trade amounts
    amount = trade.get("amount_range", "")
    if "$100,001" in amount or "$250,001" in amount or "$500,001" in amount or "$1,000,001" in amount:
        priority += 15
    
    # Senate trades (higher profile)
    if trade.get("chamber") == "Senate":
        priority += 10
    
    # Party leadership positions (would need separate mapping)
    
    # Recent context (within 2 days)
    if context.get("created_at"):
        days_diff = (datetime.now() - context["created_at"]).days
        if days_diff <= 2:
            priority += 10
        elif days_diff <= 7:
            priority += 5
    
    return min(priority, 100)


def _format_correlation_reason(trade: dict, context_count: int) -> str:
    """Format human-readable reason for correlation alert."""
    politician = trade.get("politician_name", "Unknown")
    ticker = trade.get("ticker", "N/A")
    transaction = trade.get("transaction_type", "Trade")
    chamber = trade.get("chamber", "")
    party = trade.get("party", "")
    
    parts = [f"Congress {chamber} {party}: {politician} {transaction} {ticker}"]
    if trade.get("amount_range"):
        parts.append(f"Amount: {trade['amount_range']}")
    parts.append(f"{context_count} related article(s) found")
    
    return " | ".join(parts)


def correlate_gov_contracts_with_contexts(days_back: int = 30) -> dict[str, Any]:
    """Correlate government contracts with article contexts."""
    cutoff = datetime.now() - timedelta(days=days_back)
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT qgc.id, qgc.ticker, qgc.company_name, qgc.agency, 
                       qgc.award_amount, qgc.award_date, qgc.description
                FROM intelligence.quiver_gov_contracts qgc
                WHERE qgc.award_date >= %s
                ORDER BY qgc.award_date DESC
            """, (cutoff.date(),))
            
            contracts = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            
            if not contracts:
                return {"contracts_checked": 0, "correlations_found": 0}
            
            correlations = 0
            for contract_row in contracts:
                contract = dict(zip(cols, contract_row))
                ticker = contract.get("ticker")
                if not ticker:
                    continue
                
                window_start = contract["award_date"] - timedelta(days=14)
                window_end = contract["award_date"] + timedelta(days=14)
                
                cur.execute("""
                    SELECT c.id, c.title, c.domain_key, c.created_at
                    FROM intelligence.contexts c
                    JOIN intelligence.articles a ON a.id = c.id
                    WHERE c.created_at BETWEEN %s AND %s
                    AND (c.metadata->>'tickers' ILIKE %s OR c.content ILIKE %s OR c.title ILIKE %s)
                    ORDER BY c.created_at DESC
                    LIMIT 10
                """, (window_start, window_end, f"%{ticker}%", f"%{ticker}%", f"%{ticker}%"))
                
                contexts = cur.fetchall()
                if contexts:
                    correlations += 1
                    # Could create refinement queue entry here too
                    
            return {"contracts_checked": len(contracts), "correlations_found": correlations}


def correlate_lobbying_with_contexts() -> dict[str, Any]:
    """Correlate lobbying activity with article contexts."""
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Recent lobbying (last 2 quarters)
            cur.execute("""
                SELECT ql.ticker, ql.client_name, ql.amount, ql.year, ql.quarter,
                       ql.issues, ql.lobbyists
                FROM intelligence.quiver_lobbying ql
                WHERE ql.year >= EXTRACT(YEAR FROM NOW())::int - 1
                ORDER BY ql.year DESC, ql.quarter DESC
                LIMIT 200
            """)
            
            lobbying = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
            
            if not lobbying:
                return {"lobbying_checked": 0, "correlations_found": 0}
            
            correlations = 0
            for lob_row in lobbying:
                lob = dict(zip(cols, lob_row))
                ticker = lob.get("ticker")
                if not ticker:
                    continue
                
                # Search for recent contexts
                cur.execute("""
                    SELECT c.id, c.title, c.domain_key, c.created_at
                    FROM intelligence.contexts c
                    JOIN intelligence.articles a ON a.id = c.id
                    WHERE c.created_at >= NOW() - INTERVAL '90 days'
                    AND (c.metadata->>'tickers' ILIKE %s OR c.content ILIKE %s)
                    ORDER BY c.created_at DESC
                    LIMIT 5
                """, (f"%{ticker}%", f"%{ticker}%"))
                
                if cur.fetchall():
                    correlations += 1
                    
            return {"lobbying_checked": len(lobbying), "correlations_found": correlations}


def run_full_correlation_cycle(days_back: int = 7) -> dict[str, Any]:
    """Run all correlation checks and return summary."""
    results = {}
    
    logger.info("Starting Quiver correlation cycle...")
    
    results["congress_trades"] = correlate_congress_trades_with_contexts(days_back)
    results["gov_contracts"] = correlate_gov_contracts_with_contexts(days_back * 4)  # Contracts slower
    results["lobbying"] = correlate_lobbying_with_contexts()
    
    total_alerts = sum(r.get("alerts_created", 0) for r in results.values())
    logger.info(f"Correlation cycle complete: {total_alerts} total alerts created")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_full_correlation_cycle()
    import json
    print(json.dumps(result, indent=2, default=str))