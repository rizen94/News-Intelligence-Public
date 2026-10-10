# Quality reader baseline Q0

Generated: `2026-10-04T20:23:13.005445+00:00` (UTC)

Automated SQL metrics + **hand-proxy** scores on a 20-storyline sample (not a human rater — replace proxy columns when a human scores).

## Prod gate flags observed

- `expansion_coherence_gate_enabled`: `True`
- `briefing_require_citations_enabled`: `True`
- `entity_md_min_hits`: `3`
- `max_member_articles` (politics config): `32`
- slate expansions examined: `32`

## Ranked failures (by automated pain rate)

| Rank | ID | Failure | Pain rate | Notes |
|------|----|---------|-----------|-------|
| 1 | F9 | false enriched | 0.120 | enriched_14d=2758 |
| 2 | F11 | near-dupe arcs on slate | 0.062 | pairs=2 |
| 3 | F7 | vault stub flood | 0.010 | stub=104 index=9776 living=35 |
| 4 | F1 | magnet bag on slate | 0.000 |  |
| 5 | F2 | stale durable as live | 0.000 |  |
| 6 | F3 | expansion title↔body junk | 0.000 |  |
| 7 | F4 | no usable brief | 0.000 |  |
| 8 | F5 | thin/non-yieldable members | 0.000 |  |
| 9 | F8 | multi-home exclusive confusion | 0.000 | also_in_exposed=1.0 multi_share=0.4517876489707476 |
| 10 | F6 | slate by score not novelty | 0.000 | mean_qs_slate=0.8268749999999996 mean_qs_magnet=None |
| 11 | F10 | uncited briefing prose | 0.000 | all_cited |

## Acceptance bar

| Criterion | Pass | Evidence |
|-----------|------|----------|
| Home novel/coherent/non-magnet | PASS | F1=0.000 F3=0.000 F6=0.0 |
| Storyline living or durable | FAIL | living_or_durable=1.000 hand_F4=2.50 |
| Pull ready/cached | PASS | deferred_share=0.115 |
| Reading=living Index=stubs | PASS | stub_share=0.010 |
| Durable not competing live | PASS | F2=0.000 F8_also_in_gap=0.000 |

## Metric detail

```json
{
  "F1_magnet_rate": 0.0,
  "F2_stale_durable_rate": 0.0,
  "F3_coherence_fail_rate": 0.0,
  "F4_no_usable_brief_rate": 0.0,
  "F5_thin_member_arc_rate": 0.0,
  "F6_mean_quality_on_slate": 0.8268749999999996,
  "F6_mean_quality_on_magnets": null,
  "F7_entity_stub": 104,
  "F7_entity_index": 9776,
  "F7_entity_living": 35,
  "F7_stub_share": 0.01048915784165406,
  "F8_multi_home_share": 0.4517876489707476,
  "F8_multi_home_n": 2502,
  "F8_also_in_exposed_rate": 1.0,
  "F8_without_also_in_rate": 0.0,
  "F8_multi_home_storylines_sampled": 200,
  "F9_false_enriched_proxy_rate": 0.11965192168237854,
  "F9_enriched_14d": 2758,
  "F10_citations_ok": true,
  "F10_citations_reason": "all_cited",
  "F10_fail_share": 0.0,
  "F10_require_citations_enabled": true,
  "F11_near_dupe_pairs": 2,
  "slate_n": 32,
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

- F1: 4.70
- F2: 2.50
- F3: 3.00
- F4: 2.50
- F5: 4.00

## Sample (20)

| domain | id | articles | proxy_mean | title |
|--------|----|----------|------------|-------|
| politics | 10202 | 4 | 4.2 | Trump's Next Press Secretary: Will They Be Better at Spinnin |
| politics | 8267 | 0 | 4.2 | Netanyahu Rejects Trump's Gaza Disarmament Plan, Vows No Wit |
| politics | 8494 | 3 | 4.2 | Ex-Gang Boss on Trial for Tupac Shakur's Killing Sparks Glob |
| politics | 10109 | 3 | 4.2 | UK Economy Shows Resilience Amid Iran Tensions and Energy Pr |
| politics | 10199 | 4 | 4.2 | Trump's Cyber Privateering Push Sparks Concern as Australia  |
| politics | 10141 | 2 | 4.2 | Wong Escalates Rhetoric Against Hanson Over 'Monoculture' Co |
| politics | 10144 | 2 | 4.2 | South Korean airport becomes busiest in world for global tra |
| politics | 12591 | 3 | 4.2 | Trump's Shift on North Korea Sparks South Korean President t |
| politics | 12712 | 4 | 4.2 | Las Vegas: Tupac Shakur murder trial: gang leader in court a |
| politics | 10249 | 3 | 4.2 | Israeli: Israeli militants besiege two Palestinia |
| legal | 5057 | 37 | 2.0 | Supreme Court to Weigh in on Heller and Bruen Rulings, Amid  |
| legal | 12175 | 32 | 2.0 | Trump Considers Removing Supreme Court Justice Lisa Cook Ami |
| legal | 5409 | 19 | 2.6 | Ongoing: Supreme Court |
| legal | 12300 | 18 | 2.6 | Supreme Court Docket Heats Up Amid Global Tensions |
| legal | 10982 | 18 | 2.6 | President Trump's Birthright Citizenship Order Faces Supreme |
| legal | 3809 | 18 | 2.6 | 2026 Cyclospora / Taylor Farms Lettuce Outbreak |
| legal | 3875 | 18 | 2.6 | Justice Kagan Defends Court's Reputation Amid Criticism |
| legal | 3940 | 13 | 2.6 | Citing Court's Permission, Education Department Seeks to Can |
| legal | 4002 | 11 | 2.6 | Tate Brothers to Remain in Jail as Zelenskyy Visits Burnham, |
| legal | 4001 | 11 | 2.6 | Detained 'Cockroach' Protesters Face Uncertain Fate Amid Ong |

## Q1 recommendation

**Top failure:** `F9` — false enriched (pain=0.120).

Ship only the candidate gate for this ID next (see quality plan F-table).

