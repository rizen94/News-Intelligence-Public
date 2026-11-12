---
name: ni-db-code
description: >-
  How to open PostgreSQL connections in NI Python code — get_db_connect_kwargs,
  ephemeral_db_connection, pools. Use when writing or reviewing api/ database
  access, not for postgres-mcp investigation.
---

# NI database connections (application code)

## Rule

**Never** call `psycopg2.connect()` with hand-built host/user/password in `api/`.

```python
from shared.database.connection import get_db_connect_kwargs
import psycopg2

kwargs = get_db_connect_kwargs()
conn = psycopg2.connect(**kwargs)
```

## Prefer

| Need | Use |
|------|-----|
| Single use / auto-close | `ephemeral_db_connection()` |
| Raw conn | `get_db_connect_kwargs()` + `psycopg2.connect(**kwargs)` |
| Loops / workers | `create_pool()` |
| SQLAlchemy | Existing model engine — no second engine |

## Before writing DB code

1. Read `api/shared/database/connection.py` — use what exists.
2. New pool behavior → add to `connection.py`, then call it everywhere.

## Audit

```bash
./scripts/ast_grep_ni.sh          # ast-grep rule raw-psycopg2-connect
# or ripgrep:
grep -rn 'psycopg2\.connect' api/ --include='*.py' \
  | grep -v 'get_db_connect_kwargs' \
  | grep -v 'shared/database/connection.py'
```

Semgrep in `.pre-commit-config.yaml` also blocks raw calls.

## Exceptions

Standalone migration scripts may parse env when imports are unsafe — still prefer `get_db_connect_kwargs()` when importable.

Docs: `docs/CODING_STYLE_GUIDE.md` (database section), `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md`.

Editing `api/shared/database/connection.py` requires explicit user approval (see `.clinerules/workflow.md`).
