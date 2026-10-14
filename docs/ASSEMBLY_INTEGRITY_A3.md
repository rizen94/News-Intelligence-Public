# Assembly integrity A3 remasure

Generated: `2026-10-04T21:15:58.838653+00:00` (UTC)

episode_container_assembly: `True`

**Verdict: PASS** — `admit()` probe on short/false-enriched body → `False, not_yieldable` (logged). 14d EEL false-enrich proxy (14/87) is historical residual; new admits fail closed. No LENGTH/attach-floor retune.

## A1 EEL vs bag

```json
{
  "bag_only": 0,
  "eel_only": 0,
  "drift_total": 0,
  "count_drift_episodes": 0,
  "episodes_checked": 3629,
  "count_drift_rate": 0.0
}
```

## A2 Prime freshness / Pull

```json
{
  "expansions_7d": 37,
  "max_age_hours": 119.28109867138889,
  "min_age_hours": 123.41896917833333,
  "median_age_hours": 120.19007879666667,
  "pull_total_14d": 26,
  "pull_deferred_14d": 3,
  "pull_deferred_share": 0.11538461538461539,
  "stale_novel_episodes_36h": 0
}
```

## A3 Yieldable before attach

```json
{
  "eel_source_articles_14d": 87,
  "false_enrich_proxy": 14,
  "false_enrich_rate": 0.16091954022988506
}
```

## A4 Package↔vault

```json
{
  "packages_30d": 1244,
  "packages_with_vault_brief": 89,
  "vault_brief_share": 0.07154340836012862,
  "article_members_30d": 2297,
  "article_members_with_clipping": 54,
  "clipping_share": 0.023508924684370918
}
```
