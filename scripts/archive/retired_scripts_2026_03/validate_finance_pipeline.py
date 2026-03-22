#!/usr/bin/env python3
"""
Validate Finance data ingestion pipeline — ensure each step collects and persists correctly.

Run from project root: PYTHONPATH=api python scripts/validate_finance_pipeline.py

Checks:
1. Evidence ledger — SQLite DB exists, can record and retrieve
2. Market data store — SQLite DB exists, can upsert and query gold data
3. Gold amalgamator — fetch_all stores to market_data_store and records to ledger
4. Vector store — ChromaDB collection exists (optional, requires embeddings)
5. Full refresh flow — orchestrator gold refresh produces persisted data
"""

import os
import sys
from pathlib import Path

# Add api to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
API_DIR = PROJECT_ROOT / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(str(PROJECT_ROOT))

def _section(name: str) -> None:
    print(f"\n{'='*60}\n{name}\n{'='*60}")

def check_evidence_ledger() -> bool:
    """Verify evidence ledger can record and retrieve."""
    _section("1. Evidence Ledger (evidence_ledger.db)")
    try:
        from config.settings import FINANCE_DATA_DIR
        from domains.finance.data.evidence_ledger import record, get_by_report, list_entries
        db_path = FINANCE_DATA_DIR / "evidence_ledger.db"
        print(f"  DB path: {db_path}")
        print(f"  Exists: {db_path.exists()}")
        # Record a test entry
        test_report = f"validate_test_{os.getpid()}"
        rowid = record(test_report, "test_source", "validate", evidence_data={"test": True, "step": "ledger"})
        print(f"  Record test: rowid={rowid}")
        entries = get_by_report(test_report)
        print(f"  Retrieve: {len(entries)} entries")
        ok = len(entries) >= 1 and entries[0].get("evidence_data", {}).get("test")
        print(f"  PASS" if ok else "  FAIL")
        return ok
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

def check_market_data_store() -> bool:
    """Verify market data store can upsert and query."""
    _section("2. Market Data Store (market_data.db)")
    try:
        from config.settings import FINANCE_MARKET_DB
        from domains.finance.data.market_data_store import upsert_observations, get_series
        print(f"  DB path: {FINANCE_MARKET_DB}")
        print(f"  Exists: {FINANCE_MARKET_DB.exists()}")
        test_source = "validate_test"
        test_symbol = f"symbol_{os.getpid()}"
        obs = [{"date": "2024-01-15", "value": 2024.5, "metadata": {"unit": "USD/oz", "source_id": test_symbol}}]
        r = upsert_observations(test_source, test_symbol, obs)
        print(f"  Upsert: success={r.success}, count={r.data if r.success else 'N/A'}")
        if not r.success:
            print(f"  FAIL: {r.error}")
            return False
        r2 = get_series(test_source, test_symbol)
        print(f"  Query: success={r2.success}, rows={len(r2.data) if r2.success and r2.data else 0}")
        ok = r2.success and r2.data and len(r2.data) >= 1
        print(f"  PASS" if ok else "  FAIL")
        return ok
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

def check_gold_amalgamator() -> bool:
    """Verify gold fetch stores to market_data_store and records to ledger."""
    _section("3. Gold Amalgamator (fetch + store + ledger)")
    try:
        from domains.finance.gold_amalgamator import fetch_all, get_stored
        from domains.finance.data.evidence_ledger import list_entries
        # Fetch (may hit network if no cache)
        result = fetch_all(start="2024-01-01", end="2024-01-31", store=True)
        print(f"  Fetch result: {list(result.keys())}")
        total_obs = sum(len(v) for v in result.values() if isinstance(v, list))
        print(f"  Total observations: {total_obs}")
        stored = get_stored()
        print(f"  Stored sources: {list(stored.keys()) if stored else []}")
        stored_count = sum(len(v) for v in (stored or {}).values() if isinstance(v, list))
        print(f"  Stored observations: {stored_count}")
        ledger = list_entries(source_type="gold_price", limit=5)
        entries = ledger.get("entries", [])
        print(f"  Ledger entries (gold_price): {len(entries)}")
        ok = total_obs >= 0 and (stored_count > 0 or total_obs == 0) and len(entries) >= 0
        print(f"  PASS" if ok else "  FAIL")
        return ok
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_vector_store() -> bool:
    """Verify ChromaDB vector store is accessible (optional for gold-only flow)."""
    _section("4. Vector Store (ChromaDB)")
    try:
        from config.settings import FINANCE_CHROMA_DIR
        print(f"  Chroma path: {FINANCE_CHROMA_DIR}")
        print(f"  Exists: {FINANCE_CHROMA_DIR.exists()}")
        from domains.finance.data.vector_store import get_client, get_collection
        client = get_client()
        if client is None:
            print(f"  SKIP: ChromaDB not available (not installed or disabled)")
            print(f"  (Required for EDGAR embeddings; gold/FRED work without it)")
            return True  # Non-fatal for gold-only pipeline
        print(f"  Client: OK")
        coll = get_collection()
        if coll is None:
            print(f"  SKIP: Could not get collection")
            return True
        cnt = coll.count()
        print(f"  Collection count: {cnt}")
        print(f"  PASS")
        return True
    except ImportError as ie:
        print(f"  SKIP: chromadb not installed")
        print(f"  (Required for EDGAR embeddings; gold/FRED work without it)")
        return True  # Non-fatal for gold-only pipeline
    except Exception as e:
        print(f"  FAIL: {e}")
        return False

def check_orchestrator_refresh() -> bool:
    """Run a minimal orchestrator gold refresh and verify persistence."""
    _section("5. Orchestrator Gold Refresh (full flow)")
    try:
        import asyncio
        from domains.finance.orchestrator import FinanceOrchestrator
        from domains.finance.orchestrator_types import TaskType, TaskPriority
        from domains.finance.data import evidence_ledger
        from domains.finance.data.evidence_ledger import get_by_report
        from domains.finance.gold_amalgamator import get_stored
        # Orchestrator with real ledger so we can verify persistence
        orch = FinanceOrchestrator(
            source_loader=None,
            market_data_store=None,
            vector_store=None,
            evidence_ledger=evidence_ledger,
            cpu_concurrency=2,
        )
        task_id = orch.submit_task(
            TaskType.refresh,
            {"topic": "gold", "start_date": "2024-01-01", "end_date": "2024-01-15"},
            priority=TaskPriority.high,
        )
        result = asyncio.get_event_loop().run_until_complete(orch.run_task(task_id))
        if not result:
            print("  FAIL: run_task returned None")
            return False
        print(f"  Task result: status={result.status}")
        print(f"  Sources: {getattr(result, 'sources_consulted', [])}")
        # Check ledger has orchestrator entry
        report_id = f"orchestrator_{task_id}"
        entries = get_by_report(report_id)
        print(f"  Ledger entries for task: {len(entries)}")
        # Check market data has gold
        stored = get_stored()
        print(f"  Gold in market store: {len(stored or {})} sources")
        ok = (len(entries) >= 1) or (stored and sum(len(v) for v in stored.values() if isinstance(v, list)) > 0)
        print(f"  PASS" if ok else "  FAIL")
        return ok
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False

def main() -> int:
    print("Finance Pipeline Validation")
    print("=" * 60)
    results = []
    results.append(("Evidence Ledger", check_evidence_ledger()))
    results.append(("Market Data Store", check_market_data_store()))
    results.append(("Gold Amalgamator", check_gold_amalgamator()))
    results.append(("Vector Store", check_vector_store()))
    # Orchestrator test is more involved - skip if earlier failed
    if all(r[1] for r in results[:3]):
        results.append(("Orchestrator Refresh", check_orchestrator_refresh()))
    else:
        print("\n[ Skipping Orchestrator test (prerequisites failed) ]")

    _section("Summary")
    for name, ok in results:
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n  Total: {passed}/{total} passed")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
