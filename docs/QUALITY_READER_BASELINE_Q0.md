# Quality reader baseline Q0

Generated: `2026-10-04T16:39:44.032905+00:00` (UTC)

Automated SQL metrics + **hand-proxy** scores on a 20-storyline sample (not a human rater — replace proxy columns when a human scores).

## Prod gate flags observed

- `expansion_coherence_gate_enabled`: `True`
- `briefing_require_citations_enabled`: `True`
- `entity_md_min_hits`: `3`
- `max_member_articles` (politics config): `32`
- slate expansions examined: `37`

## Ranked failures (by automated pain rate)

| Rank | ID | Failure | Pain rate | Notes |
|------|----|---------|-----------|-------|
| 1 | F10 | uncited briefing prose | 0.800 | no_slate_citations |
| 2 | F6 | slate by score not novelty | 0.550 | mean_qs_slate=0.8367567567567562 mean_qs_magnet=0.9 |
| 3 | F7 | vault stub flood | 0.520 | stub=5139 index=4708 living=35 |
| 4 | F8 | multi-home exclusive confusion | 0.452 |  |
| 5 | F3 | expansion title↔body junk | 0.135 |  |
| 6 | F9 | false enriched | 0.120 | enriched_14d=2781 |
| 7 | F1 | magnet bag on slate | 0.108 |  |
| 8 | F11 | near-dupe arcs on slate | 0.054 | pairs=2 |
| 9 | F2 | stale durable as live | 0.000 |  |
| 10 | F4 | no usable brief | 0.000 |  |
| 11 | F5 | thin/non-yieldable members | 0.000 |  |

## Metric detail

```json
{
  "F1_magnet_rate": 0.10810810810810811,
  "F2_stale_durable_rate": 0.0,
  "F3_coherence_fail_rate": 0.13513513513513514,
  "F4_no_usable_brief_rate": 0.0,
  "F5_thin_member_arc_rate": 0.0,
  "F6_mean_quality_on_slate": 0.8367567567567562,
  "F6_mean_quality_on_magnets": 0.9,
  "F7_entity_stub": 5139,
  "F7_entity_index": 4708,
  "F7_entity_living": 35,
  "F7_stub_share": 0.5200364298724954,
  "F8_multi_home_share": 0.4517876489707476,
  "F8_multi_home_n": 2502,
  "F9_false_enriched_proxy_rate": 0.11974110032362459,
  "F9_enriched_14d": 2781,
  "F10_citations_ok": false,
  "F10_citations_reason": "no_slate_citations",
  "F10_require_citations_enabled": true,
  "F11_near_dupe_pairs": 2,
  "slate_n": 37,
  "magnet_max_member_articles": 32,
  "expansion_coherence_gate_enabled": true,
  "entity_md_min_hits": 3
}
```

## Hand-proxy means (n=20)

- F1: 4.30
- F2: 2.50
- F3: 2.70
- F4: 2.50
- F5: 4.00

## Sample (20)

| domain | id | articles | proxy_mean | title |
|--------|----|----------|------------|-------|
| politics | 10159 | 3 | 3.8 | Trump's Justice Department Targets Far-Right Extremist as SP |
| politics | 12165 | 13 | 3.0 | £50bn Benefit Cut Sparks Outrage as Virgin Trains Secures Eu |
| politics | 12030 | 13 | 4.2 | JP Morgan's Dimon Warns UK Chancellor Amid Wildfires and Mus |
| politics | 6501 | 7 | 4.2 | US Politician Max Miller Faces Resignation Calls Amid Domest |
| politics | 12708 | 4 | 4.2 | Trump Administration's Data Deletions Spark Concerns Amid On |
| politics | 10270 | 3 | 4.2 | Telstra's $700k Pay Rise Sparks Outrage Amid Australia-Wide  |
| politics | 12108 | 21 | 3.0 | Private Investigators Hired by Arron Banks to Dig into Conse |
| politics | 11912 | 0 | 4.2 | Trump Orders Pentagon to Scale Back Joint Exercises with Sou |
| politics | 6493 | 7 | 4.2 | Domestic Abuse Allegations Against Ohio Republican Max Mille |
| politics | 10249 | 3 | 4.2 | Israeli: Israeli militants besiege two Palestinia |
| legal | 5057 | 37 | 2.0 | Supreme Court to Weigh in on Heller and Bruen Rulings, Amid  |
| legal | 12175 | 32 | 2.0 | Trump Considers Removing Supreme Court Justice Lisa Cook Ami |
| legal | 5409 | 19 | 2.6 | Ongoing: Supreme Court |
| legal | 10982 | 18 | 2.6 | President Trump's Birthright Citizenship Order Faces Supreme |
| legal | 3875 | 18 | 2.6 | Justice Kagan Defends Court's Reputation Amid Criticism |
| legal | 12300 | 18 | 2.6 | Supreme Court Docket Heats Up Amid Global Tensions |
| legal | 3809 | 18 | 2.6 | 2026 Cyclospora / Taylor Farms Lettuce Outbreak |
| legal | 3940 | 13 | 2.6 | Citing Court's Permission, Education Department Seeks to Can |
| legal | 4001 | 11 | 2.6 | Detained 'Cockroach' Protesters Face Uncertain Fate Amid Ong |
| legal | 4002 | 11 | 2.6 | Tate Brothers to Remain in Jail as Zelenskyy Visits Burnham, |

## Q1 recommendation

**Top failure:** `F10` — uncited briefing prose (pain=0.800).

Ship only the candidate gate for this ID next (see quality plan F-table).

