# Domain registry and provisioning — March 2026 updates

**Purpose:** Record changes that make YAML-onboarded silos show up in routing and the pipeline without a full-process restart for every touch, and align migration runners with RSS / `public.domains` activation.

**Related:** [`api/config/domains/README.md`](../api/config/domains/README.md), [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](DOMAIN_EXTENSION_TEMPLATE.md), [`AGENTS.md`](../AGENTS.md).

---

## What changed

### Registry and API path validation

- **`is_valid_domain_key()`** ([`api/shared/domain_registry.py`](../api/shared/domain_registry.py)) now checks **`get_active_domain_keys()`** on each call (re-reads active YAML + built-ins), instead of a frozen import-time set.
- **`DOMAIN_PATH_PATTERN`** is a **shape-only** regex (`^[a-z0-9]+(?:-[a-z0-9]+)*$`). The allowlist is **`is_valid_domain_key()`** / DB **`validate_domain()`** where applicable. **`ACTIVE_DOMAIN_KEYS` / `ACTIVE_DOMAIN_KEYS_SET`** remain for backward compatibility only and are now **lazy module attributes** (PEP 562) rather than import-time snapshots — see “Registry cache” below.

### Registry cache (2026-09)

- **`get_domain_entries()`** caches per process for **`DOMAIN_REGISTRY_CACHE_TTL_SECONDS`** (default **60**), so `resolve_domain_schema()` / `get_pipeline_active_domain_keys()` no longer cost a `public.domains` round trip plus a re-parse of every `domains/*.yaml` on every call. The YAML-only bootstrap result uses the shorter **`DOMAIN_REGISTRY_BOOTSTRAP_CACHE_TTL_SECONDS`** (default **5**) so a process that starts before Postgres is ready still picks the DB registry up.
- **`invalidate_domain_registry_cache()`** drops it; **`activate_domain_row()`** calls it so provisioning stays immediate. Set the TTL to `0` to disable caching.
- Reading `ACTIVE_DOMAIN_KEYS` no longer opens the reserved UI pool at import time, so scripts, workers, and tests can import registry-touching modules without DB credentials.

### Services using dynamic keys

- Content refinement queue, storyline narrative finisher guard, and finance route checks use **`get_active_domain_keys()`** or **`is_valid_domain_key()`** instead of **`ACTIVE_DOMAIN_KEYS_SET`** at import.
- **`cross_domain_sql_domains_array()`** ([`api/services/commodity_event_bridge.py`](../api/services/commodity_event_bridge.py)) builds tokens from active registry keys (excluding finance) instead of a hardcoded three-domain list.

### Provisioning and migration

- **`api/scripts/provision_domain.py`:** **`public.domains.is_active = TRUE`** after a successful run **by default**; **`--no-activate-in-db`** opts out. Shares **`activate_domain_row()`** with the new helper below.
- **`api/shared/services/domain_silo_post_migration.py`:** After domain silo SQL, seeds **`rss_feeds`** from onboarding YAML and optionally activates **`public.domains`** (SQL files alone cannot do this).
- **`api/scripts/run_migration_180.py`:** After **`180_legal_domain_silo.sql`**, by default runs RSS seed from **`api/config/domains/legal.yaml`** and activates the **`legal`** row. Flags: **`--sql-only`**, **`--skip-rss-seed`**, **`--no-activate-in-db`**, **`--domain-config`**.

### Onboarding YAML

- **`legal.yaml`:** **`is_active: true`**; instructions updated for registry/API discovery.
- **`medicine.yaml`** / **`artificial-intelligence.yaml`:** Already **`is_active: true`**; header workflows updated so they do not imply these silos are still off.

### Documentation

- **`api/config/domains/README.md`** and **`docs/DOMAIN_EXTENSION_TEMPLATE.md`:** Restart requirements, dual activation, and **`provision_domain`** defaults brought in line with the code.
- **`api/database/migrations/README.md`:** Notes post-SQL domain follow-up for future **`run_migration_NNN.py`** scripts.

### Repository hygiene

- **`.local/`** added to **`.gitignore`** (e.g. **`db_pending_writes`** spill); see **`docs/GITIGNORE.md`**.

---

## Operator checklist (unchanged in spirit)

1. Migration / **`provision_domain.py`** creates schema + **`public.domains`** row and seeds RSS when YAML lists URLs.
2. Set onboarding YAML **`is_active: true`** when the silo should appear in **`domain_registry`** / **`url_schema_pairs()`** (not auto-edited by migration helpers).
3. Keep **`public.domains`** rows aligned with YAML for catalog metadata; **`get_all_domains()`** and RSS follow **YAML + existing schema** (default **`is_active = TRUE`** from **`provision_domain.py`** / **`run_migration_180.py`** post-steps helps operators).

---

## Commit

This file was added in the same change set as the implementation; see git history on **`master`** for the full diff.
