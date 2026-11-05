# Postgres Pool Architecture — Four Independent Pools + Health

> **Operators:** Using the wrong pool or holding connections too long causes cascading failures in News Intelligence.  
> Last reviewed: 2026-10-22 · Source: `api/shared/database/connection.py` (single source of truth).

---

## The Four Pools — Overview

| Pool | Purpose | Min/Max | Checkout Timeout | Statement Timeout |
|------|---------|---------|------------------|-------------------|
| **UI pool** | Page loads, monitoring API | 2 / 16 | 3 seconds | 120 s (default) |
| **Worker pool** | Automation, batch jobs, pipeline | 2 / 28 | 30 seconds | 120 s (default) |
| **Health pool** | `health_check` probes only | 1 / 4 | Embedded in health logic | ~5 s |
| **SA pool (SQLAlchemy)** | ORM-based services | 3 / 8 (overflow) | Pool-managed | Configurable |

---

## Why Four Pools Exist

Without separate pools, a slow batch job in the worker pool could hold connections that UI page loads need. Separating pools creates **traffic isolation**: even if the worker pool is at capacity, UI responses get their 2–16 dedicated connections.

### Pool Exhaustion Impact Matrix

| Pool Exhausted | Symptom | Severity |
|----------------|---------|----------|
| UI pool | Page loads timeout (3 s hard cutoff) | High — direct user impact |
| Worker pool | Pipeline phases block/defer; automation stalls | Critical — data freshness drops |
| Health pool | `health_check` returns stale/wrong status | Medium — monitoring blind spot |
| SA pool | ORM services fail to start queries | Low (specific features) |

---

## Pool Configuration Environment Variables

| Variable | Default | Pool |
|----------|---------|------|
| `DB_POOL_WORKER_MIN` / `_MAX` | 2 / 28 | Worker |
| `DB_POOL_UI_MIN` / `_MAX` | 2 / 16 | UI |
| `DB_POOL_HEALTH_MIN` / `_MAX` | 1 / 4 | Health |
| `DB_POOL_SA_SIZE` / `_OVERFLOW` | 3 / 8 | SA |

**Raising Worker MAX:** Only increase when Postgres/PgBouncer headroom allows.

---

## PooledConnection Wrapper — How It Works

Every checked-out connection is wrapped in `PooledConnection`:

1. **Delegates all methods** (`execute()`, `cursor()`) to underlying `psycopg2.connection`
2. **Intercepts `.close()`** to return to pool instead of destroying
3. **Rolls back before returning** — prevents "aborted transaction" errors for next borrower

```python
def close(self):
    self._conn.rollback()           # Critical: prevents leaked transaction state
    if self._pool is not None:
        self._pool.putconn(self._conn)  # Return to pool
```

**Key insight:** Calling `conn.close()` directly on the underlying connection (bypassing wrapper) **destroys** the connection — permanently exhausting a slot.

---

## Checkout Timeout Pattern

```python
timeout = int(os.environ.get("DB_GETCONN_TIMEOUT_SECONDS", "30"))
```

If timeout fires, the call raises instead of blocking forever. This prevents process crashes from pool exhaustion.

**Operator action:** On `getconn` timeouts → check for connection leaks or consider increasing max with PgBouncer headroom awareness.

---

## Ephemeral Connections (Escape Hatch)

For infrequent batch work that should NOT leave sessions in shared pools:

```python
from shared.database.connection import get_ephemeral_db_connection_context

with get_ephemeral_db_connection_context() as conn:
    cur.execute("SELECT ...")
# Connection destroyed here, not returned to any pool
```

**When to use:** Daily briefing, weekly digest, narrative finisher.  
**When NOT to use:** RSS intake, enrichment, entity extraction — frequent enough to justify pooling.

---

## Pool Pressure Diagnostics

The module tracks in-flight checkout attempts: `_pool_waiters = {"worker": 0, "ui": 0, "health": 0}`

AutomationManager detects worker pool pressure → **defers new schedules** rather than adding load. PopOS workers read `public.db_pool_pressure_advisory` for the same signal.

---

## Direct Fallback Gate

```python
# DB_ALLOW_DIRECT_FALLBACK — when false, pool exhaustion fails fast
# instead of opening unaccounted direct sessions (bypasses pool tracking)
```

**Default:** `true`. Set to `"false"` in production for strict pool accounting.

---

## Key Rules (Do Not Violate — These Cause Cascading Failures)

1. **Always use `get_db_connection_context()` or `try/finally conn.close()`.** No raw `psycopg2.connect()` outside ephemeral context.
2. **Never hold a connection across LLM calls, HTTP requests, or sleeps.** Close before slow I/O.
3. **Worker pool checkout timeout is 30s — if you wait longer, something is wrong.** Fix the leak; don't increase timeout blindly.
4. **UI pool has 3s checkout timeout — page loads fail fast by design.**
5. **Health pool is reserved for `health_check` only.** Do not use it for pipeline work.
6. **Statement timeouts inherit from the pool.** Long migrations need separate connection with `SET statement_timeout = 0`.

---

## Related Files

- `api/shared/database/connection.py` — full implementation (this note's source)
- `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md` — multiplexing app connections onto fewer Postgres backends
- `docs/CODING_STYLE_GUIDE.md` § Database Connection Rules
- `docs/MONITOR_REPORTING_AND_METRICS.md` — pool monitoring via Monitor UI

