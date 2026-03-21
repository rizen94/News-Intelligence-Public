# Domain onboarding YAML (`api/config/domains/`)

Optional domains (beyond the built-in **politics**, **finance**, **science-tech**) are declared here. The Python loader is [`api/shared/domain_registry.py`](../../shared/domain_registry.py).

**Canonical procedure:** [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](../../../docs/DOMAIN_EXTENSION_TEMPLATE.md) (order of operations, migration, installer).

## Loader rules (must match code)

- **Ignored files:** Any `*.yaml` whose filename **starts with `_`** (e.g. `_template.example.yaml`) is **not** loaded for registration. Copy the template to `my-domain.yaml` — never `__my-domain.yaml` for a real domain.
- **`is_active`:** If `is_active: false`, the file is **skipped** — the `domain_key` will **not** appear in `ACTIVE_DOMAIN_KEYS` or FastAPI `DOMAIN_PATH_PATTERN`. If the key is omitted, YAML treats it as missing; the loader defaults missing to **true** (`raw.get("is_active", True)`), so **always set `is_active: false` explicitly** until you are ready.
- **Underscore keys:** Any YAML key whose name starts with `_` (e.g. `_instructions`, `_comment`) is **removed** before merge — **human documentation only**, never read by application logic.
- **Core domains:** YAML **cannot** override `politics`, `finance`, or `science-tech` (ignored if present).

## Files

| File | Purpose |
|------|---------|
| `_template.example.yaml` | **Example only** — not loaded. Copy to `{domain_key}.yaml`. |
| `{domain_key}.yaml` | One optional domain per file; `is_active: false` until DB + verify complete. |

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
| `data_sources` | no | object | **Future / docs** — not auto-seeded by registry |
| `focus_areas` | no | list | **Future / docs** |
| `llm_prompt_guidance` | no | multiline | **Future / docs** — use `\|` in YAML for paragraphs |
| `workload_assumptions` | no | object | Hints for catch-up estimators |
| `_…` | no | any | **Stripped** — not loaded into merged config used by code |

### What code consumes **today**

| Consumed by `domain_registry` | Used for |
|-------------------------------|----------|
| `domain_key`, `schema_name`, `display_name`, `display_order`, `is_active` | Merged with built-ins; routing / schema map |
| `description` | Carried in merged entry if present (callers may use later) |
| `data_sources`, `focus_areas`, `llm_prompt_guidance`, `workload_assumptions` | Stored on merged dict **if** present — **no** automatic RSS seed or LLM wiring yet unless another service reads them |

Treat undocumented keys as **reserved for future** — safe to add for your runbooks.

## How to use (ordered checklist)

1. Copy [`_template.example.yaml`](_template.example.yaml) → `{domain_key}.yaml` (filename **without** leading `_`).
2. Set **`is_active: false`**, fill **`domain_key`**, **`schema_name`**, **`display_name`** (≤ 100 chars).
3. Validate YAML (see **Validation** in [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](../../../docs/DOMAIN_EXTENSION_TEMPLATE.md)).
4. Apply SQL migration for the new silo (`public.domains`, `CREATE SCHEMA`, table parity — see template doc).
5. Run **`api/scripts/provision_domain.py`** with your config path, SQL file, and verify command (see template doc).
6. When verify exits **0**: set **`is_active: true`**, restart API.
7. Update **[`web/src/utils/domainHelper.ts`](../../../web/src/utils/domainHelper.ts)** — `DomainKey` and **`AVAILABLE_DOMAINS`** must include the new key (until the UI loads domains from an API).

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| **YAML parse error** | Invalid syntax, wrong encoding, unquoted `:` or `#` in a plain scalar |
| **404** on `/api/{key}/...` | Key not in **`ACTIVE_DOMAIN_KEYS`** — check **`is_active: true`**, filename does not start with **`_`**, restart API |
| **Duplicate `domain_key`** | Two YAML files defining the same key — keep one file per key |
| **DB insert fails** | `domain_key` / `schema_name` violates **`^...$`** checks or **`display_name` > 100** |
| **YAML ↔ DB mismatch** | `schema_name` in YAML must match **`public.domains.schema_name`** for that key |
| **Schema missing errors** | Migration not applied or wrong schema name |
| **`politics` / `finance` / `science-tech` in YAML** | Ignored by loader — do not try to redefine built-ins |
