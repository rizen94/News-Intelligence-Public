# Domain Silo Architecture — Evolution & Runtime Model

> **Operators:** This is the domain registry, schema routing, and migration history for every domain silo.  
> Last reviewed: 2026-10-22 · Source: `api/shared/domain_registry.py`, migrations 201–227, `api/config/domains/*.yaml`.

---

## Core Concept

Every **domain** (politics, finance, science-tech, etc.) is a **Postgres schema** with its own copies of `articles`, `storylines`, `topics`, `events` tables. The **single global `public.domains` table** maps `domain_key → schema_name + metadata`. A domain silo is not hard-coded; it is resolved at runtime through a **two-layer registry**: database (authoritative) plus YAML overlay.

---

## Two-Layer Registry Model

### Layer 1: `public.domains` (Database — authoritative)

```sql
SELECT domain_key, schema_name, name, display_order, is_active FROM public.domains;
```

- `is_active = true` → domain participates in pipeline ingestion, RSS feeds, storyline discovery, automation scheduling.
- `display_order` → sort position for UI ordering and API defaults.
- **No YAML file can create a domain** that does not have a DB row. YAML only enriches (prompts, focus hints, RSS seed URLs).

### Layer 2: `api/config/domains/*.yaml` (Config overlay — non-authoritative)

- Files prefixed with `_` are ignored.
- Keys prefixed with `_` inside a document are stripped at load time.
- YAML can **never** deactivate a domain — that is DB-only.

### Merge Rules (`domain_registry.get_domain_entries()`)

```python
db_rows = _load_domain_entries_from_db()   # authoritative
yaml_docs = _load_yaml_domain_files()       # enrichment only
merged = {**y, **by_key[k]}                 # DB overrides YAML on collision
```

**Key insight:** YAML is development/deployment convenience. The DB is always the source of truth. Migrations 201–227 shifted from YAML-only to DB-first.

---

## Schema Routing Pipeline

Every request flows through: `URL/domain_key → resolve_domain_schema() → registry lookup → schema name`

### Critical Functions

| Function | Purpose | Fail-Safe |
|----------|---------|-----------|
| `resolve_domain_schema(domain_key)` | URL key → schema for SQL routing | Falls back to hyphen→underscore |
| `normalize_domain_key(token)` | Canonicalize URL/token → registry key | Scans registry; returns raw if no match |
| `domain_key_to_schema(key)` | Registry-lookup only; **raises KeyError** | Never falls back |
| `get_active_domain_keys()` | Tuple of active keys for pipeline iteration | Empty tuple → pipeline skips |
| `first_active_domain_key()` | Default domain for API requests without one | Returns `"politics"` hardcoded fallback |

---

## Active vs Inactive Domains

**How domains become inactive:** `UPDATE public.domains SET is_active = false WHERE domain_key = 'science-tech';`

**Consequences of `is_active = false`:**
- RSS feed processing **skips** the domain (`pipeline_include` filtered by `ACTIVE_DOMAIN_KEYS`)
- AutomationManager **does not schedule** refinement/jobs for the domain
- Frontend product root switcher excludes from navigation
- YAML file is still loaded but **never surfaced**

### Active domains (current)

**politics** and **finance** are active. **science-tech** remains in registry but is inactive until explicitly enabled.

---

## Migration History — Politics/Finance Cutover (Migrations 201–227)

This was the most migration-complex phase of domain silo evolution.

| Phase | Change |
|-------|--------|
| ~201 | `public.domains` schema adoption — domains moved from YAML-only to DB-managed |
| ~210 | Schema creation for new domains (politics, finance) per DB rows |
| ~215 | Data migration: articles/storylines re-routed from flat tables to domain schemas |
| ~220 | AutomationManager wiring: `pipeline_include` filtered by active domains |
| ~227 | YAML-only bootstrap removed for production; DB is required |

### Operator pitfall

- **Running YAML-only locally** after migration breaks pipeline routing because the registry merge assumes at least one DB row exists.
- **`domain_key_to_schema()` raises KeyError** — never use in hot paths without validation via `resolve_domain_schema()`.

---

## Key Rules (Do Not Violate)

1. **DB is authoritative.** YAML is enrichment only.
2. **Never use `domain_key_to_schema()` in hot paths** without validation — it raises `KeyError`.
3. **`is_active` controls everything downstream:** pipeline, automation, UI navigation.
4. **Adding a domain requires both DB row AND (optionally) YAML config.** DB row is the gate.
5. **Schema names are Postgres schemas**, not table prefixes. Tables live inside `schema.articles`, not `prefix_articles`.

---

## Related Files

- `api/shared/domain_registry.py` — registry merge logic, schema resolution
- `api/config/domains/README.md` — domain extension template
- `api/database/migrations/` (201–227) — politics/finance cutover migrations
- `docs/DOMAIN_CUTOVER_POLITICS_FINANCE.md` — human-readable migration narrative

