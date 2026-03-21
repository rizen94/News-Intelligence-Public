# Legal domain — deployment runbook

First optional-domain expansion using the onboarding template: **DB silo** (`legal` schema), **registry** ([`api/config/domains/legal.yaml`](../api/config/domains/legal.yaml)), **synthesis prompts** ([`api/config/domain_synthesis_config.yaml`](../api/config/domain_synthesis_config.yaml)), and **web domain list** ([`web/src/utils/domainHelper.ts`](../web/src/utils/domainHelper.ts)).

---

## Scope and non-goals

- **In scope:** RSS and other **public** sources; same article → processing → storyline pipeline as built-in domains.
- **Out of scope:** Licensed legal databases (Westlaw, Lexis), PACER, or attorney-client workflows. This system **does not provide legal advice**; summaries and “pros/cons” are **stakeholder-oriented tradeoffs inferred from articles**, not professional opinions.

---

## Prerequisites

- Repository root; `uv` and Python env per [`docs/SETUP_ENV_AND_RUNTIME.md`](SETUP_ENV_AND_RUNTIME.md).
- Database reachable (`DB_HOST`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`).
- Read [`docs/DOMAIN_EXTENSION_TEMPLATE.md`](DOMAIN_EXTENSION_TEMPLATE.md) and [`api/config/domains/README.md`](../api/config/domains/README.md).
- **Production:** Take a DB backup before mutating schema; use `provision_domain.py --require-backup-ack --ack-backup` if you want the script to refuse without an explicit acknowledgement (the script does not perform the backup).

---

## Guardrails and rollback

| Mechanism | Detail |
|-----------|--------|
| **API off until ready** | Keep `is_active: false` in `legal.yaml` until migration + verification + post-checks succeed. Inactive files are not loaded into `ACTIVE_DOMAIN_KEYS`. |
| **YAML** | Validate before DB work; `display_name` ≤ 100 characters; `domain_key` matches `^[a-z0-9-]+$`; `schema_name` matches `^[a-z0-9_]+$`. |
| **`provision_domain.py`** | **Preflight:** aborts if `legal` schema already contains tables (prevents clobbering). **On SQL failure:** rolls back transaction, then **teardown** (remove `public.domains` / `public.domain_metadata` for `legal`, `DROP SCHEMA legal CASCADE`). **On verify failure:** same teardown. **Do not use `--skip-verify`** for the first cut—it disables the rollback guarantee after SQL. |
| **Manual rollback** | `PYTHONPATH=api uv run python api/scripts/provision_domain.py --config api/config/domains/legal.yaml --teardown-only` (destructive). Then set `is_active: false` and remove `legal` from `domainHelper.ts` if it was added. |
| **`run_migration_180.py`** | Applies `180_legal_domain_silo.sql` **without** the provision wrapper (no automatic teardown). Prefer **`provision_domain.py`** for the first silo test so failure recovery is ordered. **Do not** apply 180 twice via two different paths without checking state. |

---

## Pre-flight checklist

1. Confirm [`api/database/migrations/180_legal_domain_silo.sql`](../api/database/migrations/180_legal_domain_silo.sql) exists.
2. Confirm [`api/config/domains/legal.yaml`](../api/config/domains/legal.yaml) has `is_active: false` until cutover.
3. Validate YAML from repo root:

```bash
uv run python -c "
import yaml, pathlib
p = pathlib.Path('api/config/domains/legal.yaml')
yaml.safe_load(p.read_text(encoding='utf-8'))
print('OK:', p)
"
```

---

## Provision (recommended path)

From **repository root** (adjust verify if your project standard differs):

```bash
PYTHONPATH=api uv run python api/scripts/provision_domain.py \
  --config api/config/domains/legal.yaml \
  --sql api/database/migrations/180_legal_domain_silo.sql \
  --verify-cmd "PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py"
```

Production-style (requires explicit backup acknowledgement):

```bash
PYTHONPATH=api uv run python api/scripts/provision_domain.py \
  --require-backup-ack --ack-backup \
  --config api/config/domains/legal.yaml \
  --sql api/database/migrations/180_legal_domain_silo.sql \
  --verify-cmd "PYTHONPATH=api uv run python api/scripts/verify_migrations_160_167.py"
```

On success, the script prints the next steps (activate YAML, restart API, update frontend).

---

## Post-SQL checks

Run in `psql` or any SQL client:

```sql
-- Registry row
SELECT domain_key, name, schema_name, display_order
FROM public.domains
WHERE domain_key = 'legal';

-- Core silo tables (expect one row per table name)
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'legal'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;
```

Confirm at minimum: `articles`, `storylines`, `topics`, `rss_feeds`, `article_topic_assignments`, `storyline_articles`, `story_entity_index`, and related entity/topic tables created by migration 180.

---

## Migration ledger (176+)

After a successful apply, record migration **180** per [`api/database/migrations/README.md`](../api/database/migrations/README.md):

```bash
PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 180 \
  --notes "legal domain silo (provision_domain or run_migration_180)" \
  --file api/database/migrations/180_legal_domain_silo.sql
```

Reconcile with:

```bash
PYTHONPATH=api uv run python api/scripts/migration_ledger_report.py
```

---

## Enable routing and UI

1. Set **`is_active: true`** in [`api/config/domains/legal.yaml`](../api/config/domains/legal.yaml).
2. **Restart the API** so `domain_registry` reloads optional domains.
3. Add **`legal`** to [`web/src/utils/domainHelper.ts`](../web/src/utils/domainHelper.ts): extend `DomainKey` and `AVAILABLE_DOMAINS` with `{ key: 'legal', name: 'Legal', schema: 'legal' }`.
4. Smoke-test: `GET /api/legal/articles` (or health-appropriate list endpoint) returns 200, not 404.

---

## RSS and public sources (seed list)

**Rule:** Paste each URL into a browser or `curl` and confirm valid RSS/Atom **before** adding feeds to `legal.rss_feeds` (URLs and platforms change).

| Tier | Purpose | Examples to verify and add |
|------|---------|------------------------------|
| **Local** | Newton / West Newton / nearby municipal signal | City of Newton news/alerts ([Newton, MA](https://www.newtonma.gov/)) — use official RSS or email/SMS if RSS is unavailable; local outlets (e.g. community news sites) if they publish open feeds. |
| **Boston / MA** | State legislation, AG, courts, Boston metro | [Massachusetts Legislature](https://malegislature.gov/) (search for RSS/alerts); [Mass.gov](https://www.mass.gov/) news/executive press; [Attorney General Maura Healey — News](https://www.mass.gov/orgs/attorney-generals-office) (confirm feed or page scrape policy); [Massachusetts Courts](https://www.mass.gov/orgs/trial-court) news; [Universal Hub](http://www.universalhub.com/) if RSS remains available. |
| **Federal** | Rules, statutes-adjacent news, high courts | [Federal Register documents search RSS](https://www.federalregister.gov/documents/search.rss) (narrow with search parameters in the UI, then use the resulting RSS link); SCOTUS-related **public** commentary feeds (e.g. SCOTUSblog) — verify licensing/ToS; [Congress.gov](https://www.congress.gov/) RSS where offered. |

Duplicate starter URLs also live under `data_sources.rss.seed_feed_urls` in `legal.yaml` for copy-paste; they are **not** auto-ingested by the registry.

---

## Prompt and synthesis configuration

- **Runtime LLM bias** (event extraction, briefing lead, synthesis helpers): [`api/config/domain_synthesis_config.yaml`](../api/config/domain_synthesis_config.yaml) → `domains.legal` (`llm_context`, `event_type_priorities`, `focus_areas`, `editorial_sections`, `topic_filter`). This repo includes a `legal` block aligned with **Newton/Boston → Massachusetts → federal** priority and **court proceedings / new laws / implementation / balanced tradeoffs**.
- **Operator documentation** in YAML: [`api/config/domains/legal.yaml`](../api/config/domains/legal.yaml) (`llm_prompt_guidance`, `focus_areas`) — merged by `domain_registry` for future use; **not** a substitute for `domain_synthesis_config.yaml` for current extraction/synthesis paths.

---

## Rollback summary

1. Set `is_active: false` and restart API.
2. Remove `legal` from `domainHelper.ts` if users should not select it.
3. If you must **remove the silo**: `provision_domain.py --teardown-only --config api/config/domains/legal.yaml` (drops schema and domain rows for `legal` only).

---

## Related docs

- [`DOMAIN_EXTENSION_TEMPLATE.md`](DOMAIN_EXTENSION_TEMPLATE.md)
- [`AGENTS.md`](../AGENTS.md) — domain terminology and `/api/{domain}/...` conventions
