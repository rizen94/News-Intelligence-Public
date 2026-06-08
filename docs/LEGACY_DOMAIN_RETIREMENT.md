# Retiring legacy domains (politics, finance; science-tech silo removed)

The application registry is driven by **`public.domains`** (merged with `api/config/domains/*.yaml`).

## Cutover sequence for politics & finance

See **`docs/DOMAIN_CUTOVER_POLITICS_FINANCE.md`**: migrations **210**–**211** repointed URL keys; migration **219** unified Postgres schemas to **`politics`** and **`finance`**.

## Defaults

- `POLITICS_PG_CONTENT_DOMAIN_KEY` defaults to **`politics`** (schema **`politics`**).
- `FINANCE_PG_CONTENT_DOMAIN_KEY` defaults to **`finance`** (schema **`finance`**).

## Science & technology (retired `science-tech` / `science_tech`)

Shared metadata is repointed in migration **210**. After reclassifying any remaining `science_tech.articles` rows into **`artificial_intelligence`**, **`medicine`**, **`environment_climate`**, etc., apply migration **212** to **`DROP SCHEMA science_tech`** and remove the stale `public.domains` row.
