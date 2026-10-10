# Assembly integrity A2 remasure (after 72h-floor wake)

**Verdict: PASS** — after 72h freshness-floor wake + `vault_morning_prime`, expansion `max_age_hours` **119 → ~0.03** (≤36h). Deferred share unchanged (0.115).

Generated: `2026-10-04T21:53:55.102681+00:00` (UTC)

episode_container_assembly: `True`

## A1 EEL vs bag

```json
{
  "bag_only": 0,
  "eel_only": 0,
  "drift_total": 0,
  "count_drift_episodes": 1,
  "episodes_checked": 3630,
  "count_drift_rate": 0.0002754820936639118
}
```

## A2 Prime freshness / Pull

```json
{
  "expansions_7d": 42,
  "max_age_hours": 0.025597996388888888,
  "min_age_hours": 124.0513074375,
  "median_age_hours": 120.56426856583333,
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
  "article_members_with_clipping": 519,
  "clipping_share": 0.22594688724423162
}
```
