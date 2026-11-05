# Database Connections — MANDATORY pattern

## Rule: NEVER call `psycopg2.connect()` directly

All database connections **MUST** go through the canonical utility:

```python
import psycopg2
from shared.database.connection import get_db_connect_kwargs

kwargs = get_db_connect_kwargs()   # Resolves host, port, DB, user, pool, PgBouncer
conn = psycopg2.connect(**kwargs)  # ← only place psycopg2.connect is allowed in app code
```

## When you need a connection (prioritize):

| Need | Use | Import |
|------|-----|--------|
| Single-use / context manager (auto-close) | `ephemeral_db_connection()` | `from shared.database.connection import ephemeral_db_connection` |
| One-off raw conn | `get_db_connect_kwargs()` + `psycopg2.connect(**kwargs)` | same |
| Repeated use in loop/worker | `create_pool()` | `from shared.database.connection import create_pool` |
| ORM (SQLAlchemy) | Existing model engine — do **not** create a second engine | via existing imports |

## Why this rule exists (1-line justification):

1. **Hardcoded localhost/db/user/password breaks on Widow, staging, prod** — env-driven config is the only deployable pattern.
2. **Manual `.env` parsing diverges from canonical logic** — timeouts, PgBouncer awareness, pool params live in `connection.py`. If you copy-paste env reading, your code goes stale when those values change.
3. **Secrets in code are a security risk.**
4. **Connection pooling / max-lifetime logic lives only in `connection.py`.**

## Exceptions

Only migration scripts (`migrations/*.py`) may parse `.env` themselves, because they may run before the app's dependency tree is fully importable. Even there, prefer `get_db_connect_kwargs()` if it is importable.

## Before writing ANY database code, check:

1. Does `api/shared/database/connection.py` already provide what I need?
2. If yes — use that function. Never write your own env-reader for DB creds.
3. If no (new pool type needed) — add the function to `connection.py`, then use it everywhere.

## Audit command (quick check):

```bash
grep -rn 'psycopg2\.connect' api/ --include='*.py' \
  | grep -v 'get_db_connect_kwargs' \
  | grep -v 'shared/database/connection.py'
```

Any output = violation. Fix it before committing.

## Related docs

- `docs/CODING_STYLE_GUIDE.md` → § Database Connection Rules (full table of anti-patterns + correct code)
- `.pre-commit-config.yaml` → Semgrep hook blocks raw calls at commit time
- `docs/PGBOUNCER_AND_CONNECTION_BUDGET.md` → Pool sizes and PgBouncer config