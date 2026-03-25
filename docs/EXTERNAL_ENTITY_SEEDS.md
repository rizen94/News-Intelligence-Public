# External entity seeds (quick matching coverage)

Use these **before or alongside** gap-catalog seeding so `entity_canonical` / `entity_profiles` align with common news strings.

| Script | Source | Notes |
|--------|--------|--------|
| `api/scripts/restcountries_seed.py` | [REST Countries](https://restcountries.com/) JSON | All ISO countries + aliases (`cca2`, native names). Seeds **subject** rows; default **`--domains all`** = every active silo from **`domain_registry`** (override with a comma list). |
| `api/scripts/wikidata_sparql_seed.py` | [Wikidata Query Service](https://query.wikidata.org/) | Presets: `countries`, `central_banks`, `universities`, `us_senate`. Set `--domain` per silo. Use `--output-csv` to export without DB. **Respect** Wikimedia [User-Agent policy](https://meta.wikimedia.org/wiki/User-Agent_policy) (script sends a descriptive UA). |
| `api/scripts/seed_entities_from_csv.py` | Your CSV | Columns: `domain_key`, `name`, `type`, `aliases` (semicolon-separated). |
| `api/scripts/second_pass_frequent_subjects.py` | Local DB | Top `extracted_claims.subject_text` or `article_entities.entity_name` by frequency; seeds `subject` (default) to tighten matching. Review `--dry-run` first. |

**GeoNames / OSM / SEC:** not automated here (bulk downloads + licensing). Import via CSV or extend `seed_world_entities.yaml`.

**Suggested order**

1. `restcountries_seed.py` (broad country coverage).
2. `wikidata_sparql_seed.py --preset central_banks --domain finance` (and `universities` → `science-tech`).
3. `wikidata_sparql_seed.py --preset us_senate --domain politics` (verify SPARQL results).
4. `second_pass_frequent_subjects.py --dry-run` on **claims**, then run without `--dry-run` with a conservative `--limit`.

All paths call `bulk_seed_canonical_entries` in `api/services/entity_seed_catalog_service.py` (idempotent; syncs profiles unless `--no-sync`).
