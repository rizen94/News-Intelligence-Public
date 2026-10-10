# Quality reader baseline Q0

Generated: `2026-10-04T21:46:58.041765+00:00` (UTC)

Automated SQL metrics + **hand-proxy** scores on a 20-storyline sample (not a human rater — replace proxy columns when a human scores).

## Prod gate flags observed

- `expansion_coherence_gate_enabled`: `True`
- `briefing_require_citations_enabled`: `True`
- `entity_md_min_hits`: `3`
- `max_member_articles` (politics config): `32`
- slate expansions examined: `34`

## Ranked failures (by automated pain rate)

| Rank | ID | Failure | Pain rate | Notes |
|------|----|---------|-----------|-------|
| 1 | F11 | near-dupe arcs on slate | 0.059 | pairs=2 |
| 2 | F7 | vault stub flood | 0.036 | stub=357 index=9551 living=35 |
| 3 | F8 | multi-home exclusive confusion | 0.012 | also_in_exposed=0.9884393063583815 multi_share=0.30936401406200065 |
| 4 | F1 | magnet bag on slate | 0.000 |  |
| 5 | F2 | stale durable as live | 0.000 |  |
| 6 | F3 | expansion title↔body junk | 0.000 |  |
| 7 | F4 | no usable brief | 0.000 |  |
| 8 | F5 | thin/non-yieldable members | 0.000 |  |
| 9 | F9 | false enriched | 0.000 | enriched_14d=1257 |
| 10 | F6 | slate by score not novelty | 0.000 | mean_qs_slate=0.8311764705882353 mean_qs_magnet=None |
| 11 | F10 | uncited briefing prose | 0.000 | all_cited |

## Acceptance bar

| Criterion | Pass | Evidence |
|-----------|------|----------|
| Home novel/coherent/non-magnet | PASS | F1=0.000 F3=0.000 F6=0.0 |
| Storyline living or durable | FAIL | living_or_durable=1.000 hand_F4=2.50 |
| Pull ready/cached | PASS | deferred_share=0.115 |
| Reading=living Index=stubs | PASS | stub_share=0.036 |
| Durable not competing live | PASS | F2=0.000 F8_also_in_gap=0.012 |

## Metric detail

```json
{
  "F1_magnet_rate": 0.0,
  "F2_stale_durable_rate": 0.0,
  "F3_coherence_fail_rate": 0.0,
  "F4_no_usable_brief_rate": 0.0,
  "F5_thin_member_arc_rate": 0.0,
  "F6_mean_quality_on_slate": 0.8311764705882353,
  "F6_mean_quality_on_magnets": null,
  "F7_entity_stub": 357,
  "F7_entity_index": 9551,
  "F7_entity_living": 35,
  "F7_stub_share": 0.03590465654229106,
  "F8_multi_home_share": 0.30936401406200065,
  "F8_multi_home_n": 968,
  "F8_also_in_exposed_rate": 0.9884393063583815,
  "F8_without_also_in_rate": 0.011560693641618491,
  "F8_multi_home_storylines_sampled": 173,
  "F9_false_enriched_proxy_rate": 0.0,
  "F9_enriched_14d": 1257,
  "F10_citations_ok": true,
  "F10_citations_reason": "all_cited",
  "F10_fail_share": 0.0,
  "F10_require_citations_enabled": true,
  "F11_near_dupe_pairs": 2,
  "slate_n": 34,
  "magnet_max_member_articles": 32,
  "expansion_coherence_gate_enabled": true,
  "entity_md_min_hits": 3,
  "living_or_durable_rate": 1.0,
  "pull_total_14d": 26,
  "pull_ready_cached_14d": 24,
  "pull_deferred_14d": 3,
  "pull_deferred_share": 0.11538461538461539
}
```

## Hand-proxy means (n=20)

- F1: 4.85
- F2: 2.50
- F3: 3.00
- F4: 2.50
- F5: 4.00

## Sample (20)

| domain | id | articles | proxy_mean | title |
|--------|----|----------|------------|-------|
| politics | 10202 | 3 | 4.2 | Trump's Next Press Secretary: Will They Be Better at Spinnin |
| politics | 8494 | 1 | 4.2 | Ex-Gang Boss on Trial for Tupac Shakur's Killing Sparks Glob |
| politics | 10109 | 1 | 4.2 | UK Economy Shows Resilience Amid Iran Tensions and Energy Pr |
| politics | 10199 | 1 | 4.2 | Trump's Cyber Privateering Push Sparks Concern as Australia  |
| politics | 10141 | 1 | 4.2 | Wong Escalates Rhetoric Against Hanson Over 'Monoculture' Co |
| politics | 10144 | 1 | 4.2 | South Korean airport becomes busiest in world for global tra |
| politics | 12591 | 2 | 4.2 | Trump's Shift on North Korea Sparks South Korean President t |
| politics | 12712 | 2 | 4.2 | Las Vegas: Tupac Shakur murder trial: gang leader in court a |
| politics | 12473 | 1 | 4.2 | Trump's Warship Diplomacy Sparks Concern Amid Rising Global  |
| politics | 12108 | 9 | 4.2 | Private Investigators Hired by Arron Banks to Dig into Conse |
| legal | 3847 | 36 | 2.0 | Exxon can pursue suit over contaminated oil at Baton Rouge r |
| legal | 9514 | 11 | 2.6 | Federal Judge Blocks Postal Service's Involvement in Mail-in |
| legal | 5556 | 9 | 2.6 | Russia's Aggression Sparks Border Security Concerns Globally |
| legal | 3823 | 8 | 2.6 | 1:25-CV-12456 (docket) |
| legal | 5117 | 8 | 2.6 | Man with Sharpened Chopsticks Calls Bomb Threat After Ejecti |
| legal | 6080 | 8 | 2.6 | Judge Revokes Bond of Convicted Fraudster Involved in Minnes |
| legal | 10819 | 7 | 2.6 | Luigi Mangione Pleads Guilty in Federal Case Over Killing of |
| legal | 6172 | 6 | 2.6 | Africa in Crisis: Ebola Outbreak Surges Amid Global Migratio |
| legal | 5057 | 6 | 2.6 | Supreme Court to Weigh in on Heller and Bruen Rulings, Amid  |
| legal | 10775 | 6 | 2.6 | Feds Face Backlash from States Over Data Collection and Pris |

## Q1 recommendation

**Top failure:** `F11` — near-dupe arcs on slate (pain=0.059).

Ship only the candidate gate for this ID next (see quality plan F-table).

