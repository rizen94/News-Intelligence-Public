---
name: ni-postgres
description: >-
  News Intelligence live SQL via postgres-mcp (Widow news_intel), crystaldba tool
  ladder, and verify-before-done. Use when investigating pipeline DB state,
  schema, counts, or claiming a data fix is complete.
---

# NI Postgres (postgres-mcp)

## Server

Use the connected **`postgres-mcp`** server (SSE). There is no `news-intel-server` MCP.

| Target | Host | Port |
|--------|------|------|
| **NI `news_intel`** (postgres-mcp) | Widow `192.168.93.101` | `5432` |
| Homelab stack Postgres | PopOS Docker | `15432` |

**postgres-mcp** points at **NI on Widow** (`NEWS_INTEL_DATABASE_URI`). It does **not** query Homelab `:15432`.

Boundary: `~/Documents/projects/PROJECT_BOUNDARIES.md`.

## Tool order (required depth)

On **`postgres-mcp`**:

1. `list_schemas`
2. `list_objects`
3. `get_object_details` on tables you query
4. `execute_sql` — SELECT with `LIMIT` ≤ 50 unless the runtime doc specifies otherwise

Shallow guesses (table names from memory, migration filename only) are insufficient for diagnosis.

## Verify before "done"

Re-run the **same SQL** that demonstrated the bug after any claimed fix. Local repo edits ≠ Widow runtime until skill **ni-ship-widow** succeeds.

## Fallback

If MCP is down: migrations + `api/shared/database` as **secondary** evidence only — still prefer restoring MCP for live checks.

## Plans / Act

Same ladder in Plan and Act; Plan does not deploy — see skill **ni-plan-handoff**.
