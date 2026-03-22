# Database cleanup bundles (A / B / C)

**Purpose:** Deliberate, ordered remediation aligned with the full DB assessment plan. **No blind deletes.** Every **bundle C** item requires the pre-delete checklist in [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md) §7 and [DB_FULL_ASSESSMENT.md](DB_FULL_ASSESSMENT.md) pre-delete section.

---

## Pre-delete checklist (summary)

1. Code reference pass (`api/`, `web/`, migrations, scripts).  
2. API contract pass (routes, background jobs).  
3. Web pass (no dependent UI).  
4. Backup + verify.  
5. Dry-run SQL / rollback rehearsal on lower env.  
6. Second review for production.  
7. Post-delete smoke tests + matrix update + ticket id.

---

## Bundle A — Non-destructive (apply first)

| ID | Action | Status / notes |
|----|--------|----------------|
| A1 | Apply missing migrations; run `verify_migrations_160_167.py` | Track in `public.applied_migrations` |
| A2 | Add indexes / fix constraints (idempotent SQL only) | |
| A3 | Code alignment: domain-qualify SQL, fix API response vs web types | See diagnose unqualified-table report |
| A4 | Improve persistence visibility (`automation_run_history` insert failures logged) | Implemented in `automation_manager` |
| A5 | Register migration ledger table (176) | `api/database/migrations/176_applied_migrations_ledger.sql` |

---

## Bundle B — Archive before destructive

| ID | Action | Artifact |
|----|--------|----------|
| B1 | `pg_dump` / logical export of tables targeted by C | Path + date in ticket |
| B2 | CSV or JSON export for small reference tables | |

---

## Bundle C — Destructive (per object only)

**Rule:** One ticket per table or coherent row batch. No bulk “cleanup day” without per-item rows in this table.

| Target | Evidence of non-use | Backup ref | Sign-off | Executed env | Date |
|--------|---------------------|------------|----------|--------------|------|
| *(empty — add rows as needed)* | | | | | |

**Examples of high-risk scripts (do not run without matrix marking deprecated):**

- `api/scripts/tidy_public_legacy_tables.py` — truncates `public.articles`, `public.rss_feeds` with CASCADE.

---

## Current classification (from baseline — adjust after each assessment)

| Finding | Class | Next action |
|---------|-------|-------------|
| `public.articles` / `public.storylines` / `public.rss_feeds` empty | **keep (expected)** post–migration 125 | Ensure no runtime path relies on `public` for live data |
| 122 unqualified `articles`/`storylines`/`rss_feeds` in API code | **migrate/fix** (A3) | Domain-aware services or explicit schema |
| `content_enrichment` no 24h success in sample baseline | **investigate** | Gates, schedule, or eligibility SQL |
| `politics` storylines with synthesis vs `finance`/`science_tech` zero storylines | **data / config** | Expected if no storylines created in those domains |
| `pipeline_traces` / `pipeline_checkpoints` small | **keep** | Optional retention policy later (bundle C only with checklist) |

---

## Rollback checkpoints

- Before bundle B/C: note LSN or backup filename in ticket.  
- After A: re-run `verify_migrations_160_167.py` + `scripts/db_persistence_gates.py`.  
- Application: restart API if connection pool stale after major DDL.
