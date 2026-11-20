---
name: ni-verify-change
description: >-
  Verify News Intelligence code changes before claiming done — pytest, ruff,
  API route wiring, frontend lint, re-run the check that showed the bug. Use
  after Act edits, before commit, or when user asks if a fix is complete.
---

# NI verify change (definition of done)

*Done* ≠ confident prose. *Done* = commands run + evidence.

## Every code change

1. **Re-run the check that proved the issue** (SQL, curl, log line, failing test).
2. One sentence in chat: what ran + outcome (exit code / pass-fail).

## Python (repo root, `uv`)

```bash
uv sync --extra dev
./scripts/ast_grep_ni.sh             # optional: raw DB connect rule
uv run ruff check api tests          # lint touched areas at minimum
uv run ruff format api tests         # if formatting drifted
uv run pytest <relevant-test-path> -q
```

Smoke examples in `docs/CODING_STYLE_GUIDE.md` § Automation and tooling.

## API changes

- Route still registered (`__init__.py` / blueprint wiring).
- Grep callers if you changed a public symbol — skill **`ni-repomix-grep`**.

## Frontend (`web/`)

When touching TS/React:

```bash
cd web && npm run lint && npm run format:check
```

Typecheck via `npm run build` when types/routes changed.

## Pipeline / prod claims

Local diff alone is not Widow runtime. Authorized prod → skill **`ni-ship-widow`** + `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 re-check.

## Observability / metrics claims

Also skill **`ni-operating-principles`**: prove the **same SSOT** readers use (e.g. `read_monitor_backlog_snapshot`, not a one-off COUNT). After Grafana JSON change, note manual Homelab import (`api/monitoring/grafana/README.md`). Tag fulfilled `docs/NI_REPAIR_PLAN.md` IDs when applicable.

## Reader / feed / RSS → UI (product)

Also skill **`ni-golden-trace`**: same `golden_article_id` stage SQL before/after + `GET /api/reader/home` when claiming feed/brief fixes. Ops-only tickets exempt if user scoped them.

## Not done

- INSERT to “fill” tables without `api/` writers.
- Vault/MemPalace note without command output.
- “Successfully fixed” without diff + verify above.

## Notes

`vault_append_note` one line with verify summary; keep chat thin.
