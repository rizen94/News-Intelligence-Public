# Politics & finance domain cutover (schemas ``politics_2`` / ``finance_2``)

Canonical **URL keys** are **`politics`** and **`finance`**. Postgres **schemas** stay **`politics_2`** and **`finance_2`** (migration 201) so we do not have to move rows into the legacy `politics` / `finance` schemas.

## Ordered steps

### 1. Backup

Full database backup first.

### 2. Copy silo data (no data loss)

Use `api/scripts/copy_domain_silo_table_data.py` with a `--target-domain-key` that matches **`public.domains`** *at the time you run it*:

- **Before migration 211:** registry still has `politics-2` / `finance-2` → use `--target-domain-key politics-2` (and `finance-2` for finance).
- **After migration 211:** keys are `politics` / `finance` → use those.

Typical first-time cutover (pre-211):

```bash
cd api
PYTHONPATH=. uv run python scripts/copy_domain_silo_table_data.py \
  --source-schema politics --target-schema politics_2 --target-domain-key politics-2 --dry-run
# then without --dry-run
```

Repeat for `finance` → `finance_2` (apply migration **206** first if you need finance-only tables on `finance_2`).

### 3. RSS / ingest

Copy or seed `rss_feeds` in `politics_2` / `finance_2`, set `RSS_INGEST_EXCLUDE_DOMAIN_KEYS` to avoid duplicate collection into legacy + template schemas.

### 4. Migration **210**

`api/database/migrations/210_retire_legacy_domain_keys.sql` — repoints shared `domain_key` strings off legacy `politics` / `finance` / `science-tech` and deactivates those three `public.domains` rows.

### 5. Migration **211**

`api/database/migrations/211_rename_template_domain_keys_to_politics_finance.sql` — removes inactive stubs, renames `politics-2` → `politics` and `finance-2` → `finance`, updates `intelligence.*` references.

Repo YAML: `api/config/domains/politics.yaml`, `finance.yaml` (`domain_key` `politics` / `finance`, `schema_name` `politics_2` / `finance_2`).

### 6. Env defaults (after 211)

`POLITICS_PG_CONTENT_DOMAIN_KEY` defaults to **`politics`**; `FINANCE_PG_CONTENT_DOMAIN_KEY` to **`finance`**.

### 7. Restart API + web

Reload registry (DB + merged YAML).

See also `docs/LEGACY_DOMAIN_RETIREMENT.md` for science-tech and migration 210 context.
