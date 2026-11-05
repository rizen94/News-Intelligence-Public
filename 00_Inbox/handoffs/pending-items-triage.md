# Database Pool Exhaustion — Full Investigation Findings

## 1. Symptoms Recap

- `news-intelligence-api-public` service fails with connection pool exhaustion errors (check logs via Docker)
- Ollama CPU inference also affected — may share the same PostgreSQL backend on Widow
- Items stuck in "pending" state due to inability to check out DB connections for processing

## 2. Architecture Overview

### Connection Pool Setup (`api/shared/database/connection.py`)

- **Pool class**: `psycopg.pool.ThreadedConnectionPool` (NOT SQLAlchemy)
- **Main worker pool**: defaults to minconn=2, maxconn=28 (via `DB_POOL_MIN`/`DB_POOL_MAX` env vars)
- **UI pool**: minconn=2, maxconn=16 (`DB_POOL_UI_*`)
- **Health check pool**: minconn=1, maxconn=4 (`DB_POOL_HEALTH_*`)
- **SA pool** (SQLAlchemy): minconn=3, max_overflow=8
- **All pools connect to same PostgreSQL instance on Widow** (same physical DB)

### Pool's `close()` method — connection dropping behavior

The `PooledConnection.close()` method (lines 196-253) has a critical safety net:

    # If there's an uncommitted transaction, drop the connection instead of returning it.
    if PooledConnection._has_uncommitted_tx(self._conn):
        logger.warning("uncommitted tx — dropping")
        self._pool.putconn(self._conn, close=True)  # DROPS, does NOT return to pool

**This means: any function that opens a connection but leaves an uncommitted transaction and then closes it will permanently lose that connection from the pool.** This is by design to prevent poisoned connections, but it can rapidly deplete the pool when many threads have pending transactions.

## 3. Line-by-Line Findings per Service

### 3a. `advanced_monitoring_service.py` — HIGH RISK

**`_get_database_metrics()` (line ~250)**:
- Line 269: `conn = get_db_connection()` — **raw checkout, no context manager**
- Lines 270-318: Processing loop with potential exceptions
- **NO try/finally block** — if any exception fires between lines 269 and function end, connection leaks
- The `prometheus_http_gateway` call (HTTP I/O) can raise and short-circuit before `conn.close()`

**`_get_cache_metrics()`**: Same pattern: raw checkout without try/finally.

**`_check_for_stuck_enrichment()` (lines 475-545)**:
- Line 479: `conn = get_db_connection()` — **raw checkout, no context manager**
- Calls `_process_monitoring_check(domain_key, ...)` for EVERY domain at line 484
- Each call may open its own connection (nested pool checkouts)
- The monitoring thread loops over all domains, each holding a connection

### 3b. `ai_storyline_discovery.py` — MODERATE RISK

**Review of lines 215-260**: Uses `get_db_connection_context()` (context manager) in most places — **safe**.
**Review of lines 455-480**: Pattern uses `get_db_connection()` raw checkout with try/except but missing finally close in some paths.
**Review of lines 490-545**: Similar patterns — mixed usage between context-manager and raw checkouts.

### 3c. `article_content_enrichment_service.py` — MODERATE RISK (tail reviewed)

**`demote_false_enriched_batch()` (line 589)**:
- Uses `get_db_connection_context()` — **safe**, auto-commit/rollback/close.

**`enrich_articles_batch()` (lines 985-1240)**:
- Line 1025: `conn = get_db_connection()` — raw checkout **outside** any try block
- Lines 1031-1223: Main loop in try block
- Lines 1224-1240: Proper try/except/finally with conn.close() at end
- **One potential leak path**: If `get_db_config()` at line 1030 raises before the try block, conn is never closed. But this is extremely unlikely (just a dict lookup).

## 4. Root Cause Analysis

### Primary Cause: Connection Leak via Uncommitted Transactions + Missing Cleanup

The combination of these patterns creates a leak spiral:

1. **Raw checkout without try/finally** (`advanced_monitoring_service.py`):
   - `conn = get_db_connection()` — pool uses one slot, now at maxconn-1
   - If exception fires → connection is NEVER closed → lost from pool until GC or restart
   - HTTP I/O in monitoring thread (Prometheus gateway call) is the most likely trigger

2. **Even when finally blocks exist**: If the transaction was left uncommitted, `close()` **drops** the connection (doesn't return it to pool). So connections are being consumed and permanently removed.

3. **Pool size too small for concurrency**: Default worker pool maxconn=28 shared across ALL application threads (monitoring + enrichment + API request handlers). If just 30 API requests + monitoring + enrichment run simultaneously → pool exhausted.

### Secondary Cause: PgBouncer Interaction (if enabled)

If PgBouncer is in front of PostgreSQL on Widow, check its `pool_mode` and `max_client_conn`. With transaction pooling, each client connection can have one transaction at a time. If PgBouncer's max clients < sum of all app pool maxconn values across services, you get connection refusal regardless of app-level pool size.

## 5. Verification Queries to Run on PostgreSQL

### Check active connections right now:
```sql
SELECT count(*) as total FROM pg_stat_activity WHERE datname = 'news_intel';
SELECT state, count(*) FROM pg_stat_activity WHERE datname = 'news_intel' GROUP BY state;
```

### Check for long-running queries (stuck connections):
```sql
SELECT query_start, now() - query_start as duration, state
FROM pg_stat_activity WHERE datname = 'news_intel'
  AND query NOT LIKE '%pg_stat_activity%'
ORDER BY query_start;
```

## 6. Recommended Fixes (Ranked by Impact)

### Fix 1: Add try/finally to all raw `get_db_connection()` calls [HIGH IMPACT]
Every function doing raw checkout needs:
```python
conn = get_db_connection()
if not conn: return None
try:
    # work
except Exception as e:
    logger.error("...: %s", e)
    return None
finally:
    try: conn.close()
    except Exception: pass
```

### Fix 2: Switch to `get_db_connection_context()` [HIGH IMPACT]
The context manager handles commit/rollback/close automatically. Replace raw checkouts with:
```python
with get_db_connection_context() as conn:
    # work (auto-commits on success, rolls back + closes on exception)
```

### Fix 3: Increase pool sizes [MEDIUM IMPACT]
Add/update in docker-compose/.env:
    DB_POOL_WORKER_MAX=50
    DB_POOL_UI_MAX=24
Within PostgreSQL `max_connections` limit (default 100).

### Fix 4: Reduce monitoring thread frequency [MEDIUM IMPACT]
If monitoring runs every N seconds and each iteration opens multiple connections, reduce frequency.

## 7. Ollama CPU Inference Impact

Ollama may share the same PostgreSQL backend on Widow. Connection exhaustion in News Intelligence API could manifest as:
- Ollama unable to check out DB connections for model metadata/status
- General database unavailability → both services fail

**Immediate recovery steps**:
1. Restart `news-intelligence-api-public` service to clear leaked connections
2. Check PgBouncer pool health after restart
3. Apply code fixes (Fix 1 + Fix 2 above)
4. Monitor connection counts for 24h post-fix

## 8. Files That Need Code Changes

| File | Functions to fix | Pattern change |
|------|-----------------|----------------|
| `advanced_monitoring_service.py` | `_get_database_metrics`, `_get_cache_metrics`, all monitoring functions with raw checkout | Add try/finally or switch to context manager |
| `ai_storyline_discovery.py` | Lines 455-545 areas | Add missing finally blocks |
| `.env` / docker-compose | Pool size vars | Increase DB_POOL_WORKER_MAX, DB_POOL_UI_MAX |

## 9. Investigation Notes — What I Could Not Verify from This Machine

1. **Current pool utilization**: Cannot run queries on Widow DB remotely; need SSH access to confirm live state.
2. **PgBouncer configuration on Widow**: Need SSH access to confirm `/etc/pgbouncer/pgbouncer.ini` settings.
3. **Actual connection leak rate**: Would need monitoring data over time (Prometheus metrics).
4. **Ollama's exact database dependency**: Is it the same `news_intel` DB or a separate Postgres instance? Need to check Ollama's config on Widow.
5. **How PgBouncer health endpoint (`/health`) works**: I assumed it returns 200 OK; need to verify actual behavior on Widow (might return detailed pool stats).

## Summary

The root cause is a **connection leak spiral**:
- Raw `get_db_connection()` checkouts without try/finally in `advanced_monitoring_service.py`
- Uncommitted transactions causing the pool's `close()` method to drop connections
- Pool size (28) too small for concurrent API + monitoring + enrichment workloads
- Possible additional pressure from PgBouncer connection limits

**Immediate fix**: Restart service → clear leaked connections.
**Permanent fix**: Add try/finally blocks everywhere or switch to context manager pattern; increase pool sizes; audit PgBouncer config.
