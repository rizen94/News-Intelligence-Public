# Domain onboarding YAML (`api/config/domains/`)

**Additional silos** (beyond the built-in **politics**, **finance**, **science-tech**) are declared here — same routing, pipeline, and schema parity once migrated and provisioned. The Python loader is [`api/shared/domain_registry.py`](../../shared/domain_registry.py).

**Canonical procedure:** [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](../../../docs/DOMAIN_EXTENSION_TEMPLATE.md) (order of operations, migration, installer, dual activation, synthesis YAML).

**Dual `is_active` (do not confuse them):**

| Location | What it does |
|----------|----------------|
| **This YAML file — `is_active`** | If `false`, the file is **not loaded**; the domain is absent from **`get_active_domain_keys()`**, **`is_valid_domain_key()`**, and **`get_schema_names_active()`** / RSS **`url_schema_pairs()`** (those re-read YAML each call). FastAPI **`DOMAIN_PATH_PATTERN`** only constrains URL shape (hyphenated slug). |
| **`public.domains.is_active`** | Catalog metadata; **`get_all_domains()`** does **not** exclude silos when this is false — registry YAML + existing schema drive pipeline inclusion (set YAML **`is_active: false`** to disable a silo). |

A silo can exist in the DB with **`is_active: false`** in YAML (no registry / RSS) or appear in YAML while **`public.domains.is_active`** is false (**`DomainAwareService`** / **`validate_domain`** reject it). For a normal rollout, align **both** after verify; **`provision_domain.py`** sets **`public.domains.is_active = TRUE`** by default (use **`--no-activate-in-db`** to skip).

## Loader rules (must match code)

- **Ignored files:** Any `*.yaml` whose filename **starts with `_`** (e.g. `_template.example.yaml`) is **not** loaded for registration. Copy the template to `my-domain.yaml` — never `__my-domain.yaml` for a real domain.
- **`is_active`:** If `is_active: false`, the file is **skipped** — the `domain_key` will **not** appear in **`get_active_domain_keys()`** / RSS / iterators. If the key is omitted, YAML treats it as missing; the loader defaults missing to **true** (`raw.get("is_active", True)`), so **always set `is_active: false` explicitly** until you are ready.
- **Underscore keys:** Any YAML key whose name starts with `_` (e.g. `_instructions`, `_comment`) is **removed** before merge — **human documentation only**, never read by application logic.
- **Core domains:** YAML **cannot** override `politics`, `finance`, or `science-tech` (ignored if present).

## Files

| File | Purpose |
|------|---------|
| `_template.example.yaml` | **Example only** — not loaded. Copy to `{domain_key}.yaml` or run **`api/scripts/init_domain_yaml_from_template.py`**. |
| `{domain_key}.yaml` | One onboarded silo per file (full parity with built-ins once live). **`init_domain_yaml_from_template.py`** defaults to **`is_active: true`** (use **`--inactive`** for drafts). After migration + verify, run **`api/scripts/ensure_domain_silo_alignment.py`** so **`public.domains`** matches YAML on every host. |

## Strict requirements (**DB and routing**)

| Rule | Detail |
|------|--------|
| **`domain_key`** | **Required.** Must match **`^[a-z0-9-]+$`** (lowercase URL segment; hyphens allowed; **no** underscores). |
| **`schema_name`** | **Required.** Must match **`^[a-z0-9_]+$`** (Postgres schema; **no** hyphens). Map URL key to schema: e.g. `science-tech` → `science_tech`. |
| **`display_name`** | **Required.** **≤ 100 characters** — maps to `public.domains.name` (`VARCHAR(100)`). |
| **UTF-8** | Save files as UTF-8; **quote** values that contain `:` or `#`. |

## Field reference

| Field | Required | Max length / pattern | Notes |
|-------|-----------|------------------------|--------|
| `domain_key` | **yes** | `^[a-z0-9-]+$` | `/api/{domain_key}/...` |
| `schema_name` | **yes** | `^[a-z0-9_]+$` | Postgres schema name |
| `display_name` | **yes** | **≤ 100 chars** | `domains.name` |
| `description` | no | recommend < ~4k chars | `TEXT` in DB |
| `display_order` | no | integer | Nav sort |
| `is_active` | **strongly set** | boolean | **`false` until migration + verify pass** |
| `data_sources` | no | object | Optional **`rss.seed_feed_urls`** (strings or `{feed_name, feed_url, …}` objects) / **`rss.seed_feed_category`** — consumed by **`provision_domain.py`** and **`seed_domain_rss_from_yaml.py`**, not by `domain_registry` |
| `focus_areas` | no | list | **Future / docs** |
| `llm_prompt_guidance` | no | multiline | **Future / docs** — use `\|` in YAML for paragraphs |
| `workload_assumptions` | no | object | Hints for catch-up estimators |
| `_…` | no | any | **Stripped** — not loaded into merged config used by code |

### What code consumes **today**

| Consumed by `domain_registry` | Used for |
|-------------------------------|----------|
| `domain_key`, `schema_name`, `display_name`, `display_order`, `is_active` | Merged with built-ins; routing / schema map |
| `description` | Carried in merged entry if present (callers may use later) |
| `data_sources.rss.seed_feed_urls`, `data_sources.rss.seed_feed_category` | **Not** used by `domain_registry`. **`provision_domain.py`** / **`seed_domain_rss_from_yaml.py`** insert feeds (category defaults to **`General`**). |
| `focus_areas`, `llm_prompt_guidance`, `workload_assumptions` | Stored on merged dict **if** present — **no** automatic LLM wiring unless another service reads them |

**Synthesis / topic bias** lives in **[`api/config/domain_synthesis_config.yaml`](../domain_synthesis_config.yaml)** (separate from onboarding YAML). Add a `{domain_key}:` block there when you need clustering or narrative settings; the migration does not create it.

Treat undocumented keys as **reserved for future** — safe to add for your runbooks.

## Known code touchpoints for new domains

Until every path uses **`domain_registry`** / **`get_schema_names_active()`** / **`resolve_domain_schema()`**, operators should **grep** after adding a key:

| Pattern / area | Why |
|----------------|-----|
| `("politics", "finance"` or `science_tech` in tuples | Legacy multi-domain loops may omit YAML-onboarded silos. |
| `{"politics": "politics", "finance": "finance", "science-tech": "science_tech"}` | Prefer **`resolve_domain_schema(domain_key)`** for URL key → schema. |
| `DOMAIN_SCHEMA =` | Same — replace with registry helper where found. |
| Migrations that name one onboarded schema only (e.g. `legal.storylines`) | Prefer **`FOR schema IN SELECT … FROM public.domains`** when the change applies to all domain silos. |

**Already centralized (examples):** [`backlog_metrics.py`](../../services/backlog_metrics.py) uses **`get_schema_names_active()`** / **`url_schema_pairs()`**; [`domain_aware_service.get_domain_data_schemas()`](../../shared/services/domain_aware_service.py) delegates to **`get_schema_names_active()`**; RSS collection uses **`url_schema_pairs()`** for feed discovery.

**Verification:** [`verify_migrations_160_167.py`](../../scripts/verify_migrations_160_167.py) checks **167** and **177–179** for every **`public.domains`** schema that has an **`articles`** table (not only the three built-ins).

**Silo smoke check:** [`verify_domain_provision.py`](../../scripts/verify_domain_provision.py) — YAML, **`domain_registry`**, Postgres schema, **`public.domains`**, core/extended tables, active **`rss_feeds`**, optional **`domain_synthesis_config.yaml`** block. Exits non-zero on **errors** by default; **`--strict`** also fails on **warnings** (e.g. empty feeds); **`--yaml-only`** skips DB.

## How to use (ordered checklist)

1. Create `{domain_key}.yaml`: copy [`_template.example.yaml`](_template.example.yaml), **or** run **`api/scripts/init_domain_yaml_from_template.py`** with `--domain-key`, `--schema-name`, `--display-name` (filename **without** leading `_`).
2. Set **`is_active: false`**, fill **`domain_key`**, **`schema_name`**, **`display_name`** (≤ 100 chars).
3. Validate YAML (see **Validation** in [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](../../../docs/DOMAIN_EXTENSION_TEMPLATE.md)).
4. Apply SQL migration for the new silo (`public.domains`, `CREATE SCHEMA`, table parity — see template doc).
5. Run **`api/scripts/provision_domain.py`** with your config path, SQL file, and verify command (see template doc). That run seeds **`data_sources.rss.seed_feed_urls`** into **`rss_feeds`** unless you pass **`--no-seed-rss`**.
6. Run **`api/scripts/verify_domain_provision.py --domain-key {domain_key}`** (use **`--strict`** in CI if warnings should fail the job). Fix errors/warnings as needed.
7. Run **`api/scripts/ensure_domain_silo_alignment.py`** on each host that shares the DB (main, Widow, workers).
8. When satisfied: set **`is_active: true`** in YAML. **`public.domains.is_active`** is set by **`provision_domain.py`** unless you passed **`--no-activate-in-db`**. Restart long-lived workers only if they still cache domain lists at import (see below).
9. The web UI loads the domain list from **`GET /api/system_monitoring/registry_domains`** at startup (with a static fallback if the API is unreachable). You do not need to edit `domainHelper.ts` for each new domain.

### Process restart (when still required)

**`get_domain_entries()`** / **`get_active_domain_keys()`** / **`url_schema_pairs()`** and **`is_valid_domain_key()`** re-read YAML on **each call** — RSS collection and most iterators pick up a new onboarded silo **without** restarting the API.

**Import-time snapshot** [`ACTIVE_DOMAIN_KEYS`](../../shared/domain_registry.py) / [`ACTIVE_DOMAIN_KEYS_SET`](../../shared/domain_registry.py) is **stale** after YAML edits; prefer **`get_active_domain_keys()`** in new code. **`DOMAIN_PATH_PATTERN`** is a **shape-only** regex (not the allowlist).

Restart **API and workers** after YAML changes if you hit code that still **cached** domain lists at startup, or after changing **`domain_key` / `schema_name`** in a file (any process that read the old path).

## Authority: YAML registry vs `public.domains`

- **Pipeline, RSS, automation, and most API iteration** use **[`domain_registry`](../../shared/domain_registry.py)** (built-ins + active YAML). That is the **operational source of truth** for which silos run.
- **`public.domains`** is the **database catalog** (provisioning, constraints, operator SQL). It should stay **aligned** with YAML (`domain_key`, `schema_name`, `is_active`) when you use `provision_domain.py`.
- **Monitoring** (`database_stats` table counts for domain tables) uses **`get_schema_names_active()`** from the registry so per-domain article/storyline/rss counts match what the pipeline targets, even if a stale `public.domains` row drifts.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| **YAML parse error** | Invalid syntax, wrong encoding, unquoted `:` or `#` in a plain scalar |
| **404** on `/api/{key}/...` | Key fails **`is_valid_domain_key`** (YAML off or missing), or schema missing, or (before resolution) inactive **`public.domains`** — check **`is_active: true`** in YAML, row in **`public.domains`**, and that **`information_schema.schemata`** has **`schema_name`**. **`resolve_active_domain_schema()`** can allow registry + schema when the DB row is missing; align both for permanent domains. |
| **Duplicate `domain_key`** | Two YAML files defining the same key — keep one file per key |
| **DB insert fails** | `domain_key` / `schema_name` violates **`^...$`** checks or **`display_name` > 100** |
| **YAML ↔ DB mismatch** | `schema_name` in YAML must match **`public.domains.schema_name`** for that key (see **Authority** below) |
| **Schema missing errors** | Migration not applied or wrong schema name |
| **No RSS rows for new domain** | List URLs under **`data_sources.rss.seed_feed_urls`**, re-run **`seed_domain_rss_from_yaml.py`**, or re-provision without **`--no-seed-rss`** |
| **`politics` / `finance` / `science-tech` in YAML** | Ignored by loader — do not try to redefine built-ins |
