# Quality reader loop (instrument-first)

Tracks Q0–Q3 from the quality reader product plan. Baselines are SQL + hand-proxy on Widow prod.

Upstream product intent (why briefs should improve on the same subject over time): [`KNOWLEDGE_LOOP.md`](KNOWLEDGE_LOOP.md).

## Best product acceptance bar

Final product under test: **Home + storyline brief + Pull**. Packages-as-binder / FTM / domain-as-routing stay parked.

| Criterion | Automate | Hand (n=20) | Pass when |
|-----------|----------|-------------|-----------|
| Home: novel, coherent, non-magnet | Served-slate `F1` / `F3` / `F6` / `F11` | 1–5 “one story / why today?” | F1+F3 ≤ half of Q0; F6 magnet pain 0 |
| Storyline: citeable living or clear durable | Sample has living expansion **or** quality durable; `brief_source` set | 1–5 “understand arc?” | ≥80% living-or-durable; hand mean ≥3.5 |
| Pull ready/cached not invent | `cache_source` ∈ vault_expansion / prior_pull vs deferred | spot 5 Pulls | deferred share not rising; no on-read LLM |
| Obsidian Reading=living; Index=stubs | `F7` stub share + cleanup | open `00_Reading` / `00_Index` | stub share ~0 |
| Durable when desk published, not competing live | `brief_source` + UI labels (live vs durable) | 1–5 “current?” | F2 stays 0; durable never labeled “Morning brief” when living exists |

**Ops cadence:** daily Home + 5 storylines; after morning prime check expansions; weekly `quality_reader_baseline_q0.py` + same 20 hand scores.

Baseline markdown includes an **Acceptance bar** section with pass/fail against these thresholds.

## Q0 — Baseline (2026-10-04)

Artifacts: [`QUALITY_READER_BASELINE_Q0.md`](QUALITY_READER_BASELINE_Q0.md), `data/quality_reader_baseline_q0.json`.

| Rank | ID | Pain | Notes |
|------|----|------|-------|
| 1 | F10 | 0.800 | uncited living day card (science) |
| 2 | F6 | 0.550 | slate vs score / magnets |
| 3 | F7 | 0.520 | stub=5139 index=4708 living=35 |
| 4 | F8 | 0.452 | multi-home share |
| 5 | F3 | 0.135 | coherence fails still served |
| … | F2/F4/F5 | 0 | |

Prod flags already on: `NI_VAULT_EXPANSION_COHERENCE_GATE`, `NI_VAULT_BRIEFING_REQUIRE_CITATIONS`, `entity_md_min_hits=3`, `max_member_articles=32`.

## Q1 — Gate F10 (citations)

Shipped + deployed Widow `/opt`:

- Write: LLM assemble falls back to cited outline (skip invent)
- Serve: `get_latest_daily_briefing` + Reading MOC skip uncited
- Cleanup: `demote_uncited_daily_briefings` → `lifecycle=index`

Remeasure ([`QUALITY_READER_BASELINE_Q1.md`](QUALITY_READER_BASELINE_Q1.md)): **F10 pain 0.800 → 0.000** (`all_cited`; 1 briefing demoted).

## Q2 — Gates F6, F7, F8 (+ reader F1/F3 hide)

| Failure | Gate | Remeasure |
|---------|------|-----------|
| F6 | Novelty-first slate (`new_members_2d`, quality soft tie-break); skip magnet bags in heuristic + manager candidate filter | **0.550 → 0.000** on served slate |
| F7 | `vault_quality_cleanup` stub→index; hide `lifecycle=index` from reader entity/context pack | **0.520 → ~0.002** |
| F8 | Pack + UI `also_in` for multi-linked articles | UX gate (membership share still ~0.45 by design) |
| F1/F3 | `list_morning_expansions` (7d) hides magnets + coherence fails / `needs_reprime` | **F1 0.108→0; F3 0.135→0** |

Artifacts: [`QUALITY_READER_BASELINE_Q1.md`](QUALITY_READER_BASELINE_Q1.md), [`QUALITY_READER_BASELINE_Q2.md`](QUALITY_READER_BASELINE_Q2.md).

Stop bar (plan): F2–F4 hand means still proxy-only; F1 magnet rate ≤ 50% of baseline — **met** (0).

## Best-bar gates — F8 + F9 (2026-10-04)

| Gate | Change | Remeasure |
|------|--------|-----------|
| F8 | `brief_source` on pack; UI live vs durable labels; Also-in “primary home…” copy; F8 pain = multi-home **without** also_in | [`QUALITY_READER_BASELINE_Q3a.md`](QUALITY_READER_BASELINE_Q3a.md): **F8 without also_in  → 0** (`also_in_exposed=1.0`) |
| F9 | `is_false_enriched_body` blocks write/fast-path; `demote_false_enriched_batch` on drain | [`QUALITY_READER_BASELINE_Q3b.md`](QUALITY_READER_BASELINE_Q3b.md): **F9 0.120 → ~0.113** (write gate on; residual = long bodies that only match noisy `cookie` ILIKE proxy) |

Acceptance bar (Q3b): Home / Pull / Reading / Durable-not-competing **PASS**. Storyline living-or-durable automate **PASS** (1.0); hand_F4 proxy still FAIL (~2.5 on legal oversized sample — needs human n=20).

### Q3c — F9 metric aligned to yieldable (2026-10-04)

[`QUALITY_READER_BASELINE_Q3c.md`](QUALITY_READER_BASELINE_Q3c.md): F9 pain **0.113 → 0.000** after baseline uses `is_false_enriched_body` (drops noisy `cookie` ILIKE false positives). Hand sheet: [`HAND_F4_SCORING_SHEET.md`](HAND_F4_SCORING_SHEET.md).

### Fact gold (Trump grounding)

Complement to arc F4: score n=15–20 ledger facts after morning prime on Trump accountability arcs.

- Kit: `api/scripts/hand_fact_gold_kit.py` → [`HAND_FACT_GOLD_SHEET.md`](HAND_FACT_GOLD_SHEET.md) + `data/hand_fact_gold_sheet.json`
- Pass bar: mean ≥ **3.5** (Supported sequence match; CONFLICT sides not asserted as settled)
- Ledger SSOT: vault `40_Reference/timelines/trump_politics_background_review.md` (vn 41752)

## Q3 shape — Parked (after Q0–Q2 gains)

Do **not** unpark until reader F2–F4 hand means and magnet rates meet the bar:

- Domain as routing / cross-domain hubs
- Global FTM + domain facets
- Research lane boundaries (`/research` ≠ news storylines)
- Editorial packages as binder / membership merges
- Broader membership precision/recall beyond F1 magnet gate

## Assembly integrity (A1–A4)

Instrument-first assembly oversights (EEL↔bag, prime freshness, yieldable admit, thin package↔vault). Full loop: [`ASSEMBLY_INTEGRITY_LOOP.md`](ASSEMBLY_INTEGRITY_LOOP.md).

| Gate | Remeasure | Pass |
|------|-----------|------|
| A1 EEL↔bag reconcile | [`ASSEMBLY_INTEGRITY_A1.md`](ASSEMBLY_INTEGRITY_A1.md) | drift 20321 → 0 |
| A2 stale prime wake | [`ASSEMBLY_INTEGRITY_A2.md`](ASSEMBLY_INTEGRITY_A2.md) | wake idle (no novel); deferred stable |
| A3 yieldable admit | [`ASSEMBLY_INTEGRITY_A3.md`](ASSEMBLY_INTEGRITY_A3.md) | `not_yieldable` on probe |
| A4 package↔vault thin | [`ASSEMBLY_INTEGRITY_A4.md`](ASSEMBLY_INTEGRITY_A4.md) | brief registry + clipping up |

## Ops

- Deploy: `scripts/deploy_to_widow.sh` + `scripts/ensure_widow_api_runtime.sh`
- Remeasure: `PYTHONPATH=api .venv/bin/python api/scripts/quality_reader_baseline_q0.py --out docs/QUALITY_READER_BASELINE_Qn.md`
- Assembly baseline: `PYTHONPATH=api .venv/bin/python api/scripts/assembly_integrity_baseline.py --out docs/ASSEMBLY_INTEGRITY_An.md`
- Cleanup: `api/scripts/vault_quality_cleanup.py`
