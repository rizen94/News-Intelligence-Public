# Politics & finance domain cutover (completed)

**Status (migrations 219 / 227):** URL keys **`politics`** and **`finance`** use Postgres schemas **`politics`** and **`finance`** — no `politics_2`, `finance_2`, `politics-2`, or `finance-2`.

## Historical context

Migrations **201**–**211** introduced template silos (`politics_2` / `finance_2`) while retiring legacy keys. Migration **219** drops empty legacy schemas and renames `*_2` → canonical names when the fork silo was authoritative.

**Widow / homelab (2026):** Live data remained in **`politics`** / **`finance`**; **`227_drop_politics_finance_2_stubs.sql`** updates `public.domains` and drops the partial `politics_2` / `finance_2` forks without destroying primary silos.

## Operator steps

### Path A — fork silo was canonical (219)

1. Full database backup.
2. `PYTHONPATH=api uv run python api/scripts/audit_politics_finance_schemas.py`
3. If legacy `politics` / `finance` still have rows, copy into `politics_2` / `finance_2` with `copy_domain_silo_table_data.py`, then re-audit.
4. `PYTHONPATH=api uv run python api/scripts/run_migration_219.py`

### Path B — primary silo was canonical (227, Widow)

1. Full database backup.
2. Audit shows row counts in `politics` / `finance` and stubs in `politics_2` / `finance_2`.
3. `PYTHONPATH=api uv run python api/scripts/run_migration_227.py`
4. Register in `public.applied_migrations`.

### After either path

5. Restart API + workers; `verify_domain_provision.py --domain-key politics` and `finance`.
6. `check_domain_suffix_cruft.py` should pass.

## Config

- Domain specs: `api/config/domains/specs/politics.domain.json`, `finance.domain.json` (`schema_name` matches `domain_key` mapping).
- `POLITICS_PG_CONTENT_DOMAIN_KEY` / `FINANCE_PG_CONTENT_DOMAIN_KEY` default to **`politics`** / **`finance`**.

See also [`DOMAIN_EXTENSION_TEMPLATE.md`](DOMAIN_EXTENSION_TEMPLATE.md) and [`LEGACY_DOMAIN_RETIREMENT.md`](LEGACY_DOMAIN_RETIREMENT.md).
