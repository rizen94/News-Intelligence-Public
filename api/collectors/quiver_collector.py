#!/usr/bin/env python3
"""
Quiver Quantitative API Collector for News Intelligence System
Collects congressional trades, government contracts, lobbying, and insider trades.
Maps tickers to entities and triggers intelligence correlation.
"""
from config.runtime import env_bool, env_int, env_str

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import psycopg2
import psycopg2.errors
import psycopg2.extras

from shared.database.connection import get_db_connection_context

logger = logging.getLogger(__name__)


def _quiver_api_key() -> str | None:
    """Get Quiver API key from environment."""
    return env_str("QUIVER_API_KEY", "")


def _quiver_base_url() -> str:
    """Get Quiver API base URL."""
    return env_str("QUIVER_API_BASE_URL", "https://api.quiverquant.com/beta")


def _quiver_collection_interval_hours() -> int:
    return env_int("QUIVER_COLLECTION_INTERVAL_HOURS", 6)


def _quiver_enabled() -> bool:
    return env_bool("QUIVER_COLLECTOR_ENABLED", True) and bool(_quiver_api_key())


def _quiver_headers() -> dict[str, str]:
    key = _quiver_api_key()
    if not key:
        return {}
    # Quiver API uses "Token" prefix, not "Bearer"
    return {"Authorization": f"Token {key}"}


def _quiver_get(endpoint: str, params: dict | None = None) -> dict[str, Any] | list[Any] | None:
    """Make authenticated request to Quiver API."""
    if not _quiver_enabled():
        logger.warning("Quiver collector not enabled or API key missing")
        return None
    
    url = f"{_quiver_base_url()}{endpoint}"
    try:
        response = requests.get(url, headers=_quiver_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        # Quiver wraps data in {"data": [...]} format
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Quiver API request failed: {endpoint} - {e}")
        return None
    except Exception as e:
        logger.error(f"Quiver API unexpected error: {endpoint} - {e}")
        return None


def _upsert_congress_trade(cur, trade: dict) -> bool:
    """Insert or update a congressional trade record. Returns True if inserted."""
    # Quiver trade fields: Ticker, Company, Transaction, Amount, Date, Filed, 
    # Politician, Chamber, Party, State, Owner, Trade_ID
    trade_id = trade.get("Trade_ID") or trade.get("trade_id")
    if not trade_id:
        logger.warning(f"Trade missing Trade_ID: {trade}")
        return False
    
    try:
        cur.execute("""
            INSERT INTO intelligence.quiver_congress_trades
            (quiver_trade_id, politician_name, politician_bioguide_id, chamber, party, state,
             ticker, company_name, transaction_type, amount_range, traded_date, filed_date,
             owner_type, raw_data, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
            ON CONFLICT (quiver_trade_id) DO UPDATE SET
                politician_name = EXCLUDED.politician_name,
                chamber = EXCLUDED.chamber,
                party = EXCLUDED.party,
                state = EXCLUDED.state,
                ticker = EXCLUDED.ticker,
                company_name = EXCLUDED.company_name,
                transaction_type = EXCLUDED.transaction_type,
                amount_range = EXCLUDED.amount_range,
                traded_date = EXCLUDED.traded_date,
                filed_date = EXCLUDED.filed_date,
                owner_type = EXCLUDED.owner_type,
                raw_data = EXCLUDED.raw_data,
                updated_at = NOW()
            WHERE intelligence.quiver_congress_trades.raw_data IS DISTINCT FROM EXCLUDED.raw_data
            RETURNING (xmax = 0) AS inserted
        """, (
            trade_id,
            trade.get("Politician") or trade.get("politician"),
            trade.get("Bioguide_ID") or trade.get("bioguide_id"),
            trade.get("Chamber") or trade.get("chamber"),
            trade.get("Party") or trade.get("party"),
            trade.get("State") or trade.get("state"),
            trade.get("Ticker") or trade.get("ticker"),
            trade.get("Company") or trade.get("company"),
            trade.get("Transaction") or trade.get("transaction"),
            trade.get("Amount") or trade.get("amount"),
            _parse_date(trade.get("Date") or trade.get("date")),
            _parse_date(trade.get("Filed") or trade.get("filed")),
            trade.get("Owner") or trade.get("owner"),
            json.dumps(trade)
        ))
        result = cur.fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Failed to upsert congress trade {trade_id}: {e}")
        return False


def _upsert_gov_contract(cur, contract: dict) -> bool:
    """Insert or update a government contract record."""
    contract_id = contract.get("Contract_ID") or contract.get("contract_id")
    if not contract_id:
        logger.warning(f"Contract missing Contract_ID: {contract}")
        return False
    
    try:
        cur.execute("""
            INSERT INTO intelligence.quiver_gov_contracts
            (quiver_contract_id, ticker, company_name, agency, award_amount, award_date,
             description, contract_type, raw_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (quiver_contract_id) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                company_name = EXCLUDED.company_name,
                agency = EXCLUDED.agency,
                award_amount = EXCLUDED.award_amount,
                award_date = EXCLUDED.award_date,
                description = EXCLUDED.description,
                contract_type = EXCLUDED.contract_type,
                raw_data = EXCLUDED.raw_data
            WHERE intelligence.quiver_gov_contracts.raw_data IS DISTINCT FROM EXCLUDED.raw_data
            RETURNING (xmax = 0) AS inserted
        """, (
            contract_id,
            contract.get("Ticker") or contract.get("ticker"),
            contract.get("Company") or contract.get("company"),
            contract.get("Agency") or contract.get("agency"),
            _parse_numeric(contract.get("Amount") or contract.get("amount")),
            _parse_date(contract.get("Date") or contract.get("date")),
            contract.get("Description") or contract.get("description"),
            contract.get("Type") or contract.get("type"),
            json.dumps(contract)
        ))
        result = cur.fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Failed to upsert gov contract {contract_id}: {e}")
        return False


def _upsert_lobbying(cur, lobbying: dict) -> bool:
    """Insert or update a lobbying record."""
    # Quiver lobbying doesn't have a unique ID, create composite key
    client = lobbying.get("Client") or lobbying.get("client")
    year = lobbying.get("Year") or lobbying.get("year")
    quarter = lobbying.get("Quarter") or lobbying.get("quarter")
    ticker = lobbying.get("Ticker") or lobbying.get("ticker")
    
    if not client or not year or not quarter:
        logger.warning(f"Lobbying missing key fields: {lobbying}")
        return False
    
    composite_id = f"{client}|{year}|{quarter}|{ticker}"
    
    try:
        cur.execute("""
            INSERT INTO intelligence.quiver_lobbying
            (composite_id, ticker, client_name, amount, year, quarter, issues, lobbyists, raw_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (composite_id) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                client_name = EXCLUDED.client_name,
                amount = EXCLUDED.amount,
                year = EXCLUDED.year,
                quarter = EXCLUDED.quarter,
                issues = EXCLUDED.issues,
                lobbyists = EXCLUDED.lobbyists,
                raw_data = EXCLUDED.raw_data
            WHERE intelligence.quiver_lobbying.raw_data IS DISTINCT FROM EXCLUDED.raw_data
            RETURNING (xmax = 0) AS inserted
        """, (
            composite_id,
            ticker,
            client,
            _parse_numeric(lobbying.get("Amount") or lobbying.get("amount")),
            int(year) if year else None,
            int(quarter) if quarter else None,
            lobbying.get("Issues") or lobbying.get("issues"),
            lobbying.get("Lobbyists") or lobbying.get("lobbyists"),
            json.dumps(lobbying)
        ))
        result = cur.fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Failed to upsert lobbying {composite_id}: {e}")
        return False


def _upsert_insider_trade(cur, trade: dict) -> bool:
    """Insert or update an insider trade record."""
    trade_id = trade.get("Trade_ID") or trade.get("trade_id")
    if not trade_id:
        logger.warning(f"Insider trade missing Trade_ID: {trade}")
        return False
    
    try:
        cur.execute("""
            INSERT INTO intelligence.quiver_insider_trades
            (quiver_trade_id, ticker, company_name, insider_name, title, transaction_type,
             shares, price, value, traded_date, filed_date, raw_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
            ON CONFLICT (quiver_trade_id) DO UPDATE SET
                ticker = EXCLUDED.ticker,
                company_name = EXCLUDED.company_name,
                insider_name = EXCLUDED.insider_name,
                title = EXCLUDED.title,
                transaction_type = EXCLUDED.transaction_type,
                shares = EXCLUDED.shares,
                price = EXCLUDED.price,
                value = EXCLUDED.value,
                traded_date = EXCLUDED.traded_date,
                filed_date = EXCLUDED.filed_date,
                raw_data = EXCLUDED.raw_data
            WHERE intelligence.quiver_insider_trades.raw_data IS DISTINCT FROM EXCLUDED.raw_data
            RETURNING (xmax = 0) AS inserted
        """, (
            trade_id,
            trade.get("Ticker") or trade.get("ticker"),
            trade.get("Company") or trade.get("company"),
            trade.get("Insider") or trade.get("insider"),
            trade.get("Title") or trade.get("title"),
            trade.get("Transaction") or trade.get("transaction"),
            _parse_numeric(trade.get("Shares") or trade.get("shares")),
            _parse_numeric(trade.get("Price") or trade.get("price")),
            _parse_numeric(trade.get("Value") or trade.get("value")),
            _parse_date(trade.get("Date") or trade.get("date")),
            _parse_date(trade.get("Filed") or trade.get("filed")),
            json.dumps(trade)
        ))
        result = cur.fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f"Failed to upsert insider trade {trade_id}: {e}")
        return False


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse various date formats from Quiver API."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {date_str}")
    return None


def _parse_numeric(val: str | int | float | None) -> float | None:
    """Parse numeric values, handling $ and commas."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Remove $ and commas
        cleaned = val.replace("$", "").replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            # Handle ranges like "$1,001 - $15,000" - return midpoint
            if "-" in cleaned:
                parts = [p.strip() for p in cleaned.split("-")]
                try:
                    return (float(parts[0]) + float(parts[1])) / 2
                except (ValueError, IndexError):
                    pass
    return None


def collect_congress_trades(days_back: int = 7) -> dict[str, Any]:
    """Collect recent congressional trades."""
    if not _quiver_enabled():
        return {"error": "Quiver collector not enabled", "inserted": 0, "errors": 0}
    
    logger.info(f"Collecting congressional trades (last {days_back} days)")
    
    # Quiver congress trading endpoint
    data = _quiver_get("/live/congresstrading")
    if not data:
        return {"error": "No data returned", "inserted": 0, "errors": 0}
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    inserted = 0
    errors = 0
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for trade in data:
                # Filter by filed date
                filed_date = _parse_date(trade.get("Filed") or trade.get("filed"))
                if filed_date and filed_date < cutoff:
                    continue
                
                if _upsert_congress_trade(cur, trade):
                    inserted += 1
                else:
                    errors += 1
            conn.commit()
    
    logger.info(f"Congress trades: {inserted} inserted, {errors} errors")
    return {"inserted": inserted, "errors": errors, "total_fetched": len(data)}


def collect_gov_contracts(tickers: list[str] | None = None) -> dict[str, Any]:
    """Collect government contracts."""
    if not _quiver_enabled():
        return {"error": "Quiver collector not enabled", "inserted": 0, "errors": 0}
    
    logger.info("Collecting government contracts")
    
    data = _quiver_get("/live/govcontracts")
    if not data:
        return {"error": "No data returned", "inserted": 0, "errors": 0}
    
    # Filter by tickers if provided
    if tickers:
        ticker_set = set(t.upper() for t in tickers)
        data = [c for c in data if (c.get("Ticker") or c.get("ticker", "")).upper() in ticker_set]
    
    inserted = 0
    errors = 0
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for contract in data:
                if _upsert_gov_contract(cur, contract):
                    inserted += 1
                else:
                    errors += 1
            conn.commit()
    
    logger.info(f"Gov contracts: {inserted} inserted, {errors} errors")
    return {"inserted": inserted, "errors": errors, "total_fetched": len(data)}


def collect_lobbying(tickers: list[str] | None = None) -> dict[str, Any]:
    """Collect corporate lobbying data."""
    if not _quiver_enabled():
        return {"error": "Quiver collector not enabled", "inserted": 0, "errors": 0}
    
    logger.info("Collecting lobbying data")
    
    data = _quiver_get("/live/lobbying")
    if not data:
        return {"error": "No data returned", "inserted": 0, "errors": 0}
    
    if tickers:
        ticker_set = set(t.upper() for t in tickers)
        data = [l for l in data if (l.get("Ticker") or l.get("ticker", "")).upper() in ticker_set]
    
    inserted = 0
    errors = 0
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for lobbying in data:
                if _upsert_lobbying(cur, lobbying):
                    inserted += 1
                else:
                    errors += 1
            conn.commit()
    
    logger.info(f"Lobbying: {inserted} inserted, {errors} errors")
    return {"inserted": inserted, "errors": errors, "total_fetched": len(data)}


def collect_insider_trades(tickers: list[str] | None = None) -> dict[str, Any]:
    """Collect insider trading data."""
    if not _quiver_enabled():
        return {"error": "Quiver collector not enabled", "inserted": 0, "errors": 0}
    
    logger.info("Collecting insider trades")
    
    data = _quiver_get("/live/insidertrading")
    if not data:
        return {"error": "No data returned", "inserted": 0, "errors": 0}
    
    if tickers:
        ticker_set = set(t.upper() for t in tickers)
        data = [t for t in data if (t.get("Ticker") or t.get("ticker", "")).upper() in ticker_set]
    
    inserted = 0
    errors = 0
    
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for trade in data:
                if _upsert_insider_trade(cur, trade):
                    inserted += 1
                else:
                    errors += 1
            conn.commit()
    
    logger.info(f"Insider trades: {inserted} inserted, {errors} errors")
    return {"inserted": inserted, "errors": errors, "total_fetched": len(data)}


def collect_all(days_back: int = 7, tickers: list[str] | None = None) -> dict[str, Any]:
    """Run all Quiver collectors."""
    if not _quiver_enabled():
        return {"error": "Quiver collector not enabled - check QUIVER_API_KEY"}
    
    results = {}
    results["congress_trades"] = collect_congress_trades(days_back)
    results["gov_contracts"] = collect_gov_contracts(tickers)
    results["lobbying"] = collect_lobbying(tickers)
    results["insider_trades"] = collect_insider_trades(tickers)
    
    total_inserted = sum(r.get("inserted", 0) for r in results.values())
    total_errors = sum(r.get("errors", 0) for r in results.values())
    
    logger.info(f"Quiver collection complete: {total_inserted} total inserted, {total_errors} errors")
    return {
        "results": results,
        "total_inserted": total_inserted,
        "total_errors": total_errors
    }


if __name__ == "__main__":
    # Allow running as standalone script
    logging.basicConfig(level=logging.INFO)
    
    if not _quiver_enabled():
        print("QUIVER_API_KEY not set or collector disabled")
        sys.exit(1)
    
    result = collect_all()
    print(json.dumps(result, indent=2, default=str))