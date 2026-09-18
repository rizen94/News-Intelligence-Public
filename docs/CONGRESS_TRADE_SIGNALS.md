# Congressional trade signals

Intelligence + HITL product on top of Quiver congressional disclosures. **No live brokerage.**

## Pipeline

1. **Ingest** — `api/collectors/quiver_collector.py` → `intelligence.quiver_congress_trades` (migration **265**)
2. **Enrich** — lag, amount ordinal, side, committees (optional Congress.gov), issuer sector, leadership, bipartisan cluster → `intelligence.congress_trade_enrichment`
3. **Score** — deterministic weighted features → `intelligence.congress_trade_signals` (`as_of_date` = **filed_date** only)
4. **Paper** — monthly rebalance using only signals with `as_of_date` ≤ prior month-end; NAV vs SPY → `congress_paper_positions` / `congress_paper_nav`
5. **HITL** — top scores → `intelligence.trading_signals` with `metadata.source = congress_quiver`

Migrations: **265** (Quiver tables) + **300** (enrichment / signals / paper).

## Feature flag

- Registry: `congress_trade_signals` in `api/config/features.yaml` (staged)
- Runtime: `CONGRESS_TRADE_SIGNALS_ENABLED=true` **or** `FEATURE_OVERRIDE_CONGRESS_TRADE_SIGNALS=true` **or** `FEATURE_STAGED_RUNTIME_ENABLED=true`
- Config: `api/config/congress_trade_signals.yaml`

## Ops

```bash
# Widow
export QUIVER_API_KEY=...   # required for collector
export CONGRESS_TRADE_SIGNALS_ENABLED=true
PYTHONPATH=api python3 api/scripts/run_migration.py 265
PYTHONPATH=api python3 api/scripts/run_migration.py 300
PYTHONPATH=api python3 -m collectors.quiver_collector
PYTHONPATH=api python3 api/scripts/run_congress_trade_signals.py --json
```

Automation schedules: `quiver_collector` (6h) → `congress_trade_signals` (6h, depends_on Quiver).

## API

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/politics/congress/trades` | Raw Quiver rows |
| GET | `/api/politics/congress/signals` | Scored eligible signals |
| GET | `/api/politics/congress/paper-portfolio` | NAV history + latest positions |
| POST | `/api/politics/congress/signals/run` | Operator pipeline kick |
| GET | `/api/signals` | Shared HITL queue (includes `congress_quiver`) |

## Look-ahead rule

Paper selection cutoff is **end of prior month**. Positions for month *M* never include filings dated in *M*. Stooq marks use closes on/before the mark date.

## Explicit non-goals

- Live order execution / broker APIs
- First-party PTR scraper (Quiver remains SSOT)
- LLM sizing or timing of trades (optional narrative into `idea_summary` only, not wired in v1)
