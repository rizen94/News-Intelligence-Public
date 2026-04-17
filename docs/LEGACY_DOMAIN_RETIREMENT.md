# Retiring legacy domains (politics, finance; science-tech silo removed)

The application registry is driven by **`public.domains`** (merged with `api/config/domains/*.yaml`).

## Cutover sequence for politics & finance

Use **`docs/DOMAIN_CUTOVER_POLITICS_FINANCE.md`**: copy data → migration **210** → migration **211** so URL keys become plain **`politics`** and **`finance`** while data stays in schemas **`politics_2`** and **`finance_2`**.

## Defaults (post–211 naming)

- `POLITICS_PG_CONTENT_DOMAIN_KEY` defaults to **`politics`** (schema `politics_2`).
- `FINANCE_PG_CONTENT_DOMAIN_KEY` defaults to **`finance`** (schema `finance_2`).

## Science & technology (retired `science-tech` / `science_tech`)

Shared metadata is repointed in migration **210**. After reclassifying any remaining `science_tech.articles` rows into **`artificial_intelligence`**, **`medicine`**, **`environment_climate`**, etc., apply migration **212** to **`DROP SCHEMA science_tech`** and remove the stale `public.domains` row.
