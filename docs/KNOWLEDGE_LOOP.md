# Knowledge loop — product intent

**Thesis:** Content is stored and improved over time. As new articles arrive and data sources improve, material on the *same subject* should gain clarity — longer fact bases, richer vault timelines, better summaries and briefs. Each quality write should start from accumulated context, not from nothing.

This is the core product intent behind storyline evolution, vault Distill/Express, and the ~70B narrative finisher. Pipeline throughput is a means; compounding understanding is the end.

## Two twins of the loop

| Layer | What accumulates | How quality improves |
|-------|------------------|----------------------|
| **Evidence / structure** | Articles on a storyline, `versioned_facts`, chronological spine, vault clipping → wiki Distill timelines, knowledge-profile assertions | Append / promote / merge — durable memory grows |
| **Reader-facing prose** | `canonical_narrative`, morning expansions, package/desk `editorial_document` | Full rewrite when evidence is **material**, grounded on **prior canonical** (or prior expansion when fingerprint moves); skip when unchanged; defer narrow deltas to nightly debt drain |

Do not confuse “regenerate from a richer pile” with “start from nothing.” The pile (and prior desk prose) must enter the prompt.

## Canonical narrative path (~70B)

```text
Membership attach / fact snapshot
        │
        ▼
Materiality classify ── unchanged ──► skip (no GPU)
        │
        ├── narrow ──► mark narrow_debt_pending (nightly force)
        │
        └── material / initial / force ──► full walkthrough rewrite
                                              │
                                              ▼
                                    prior canonical + facts + vault + spine
                                              │
                                              ▼
                                    persist narrative + evidence_fingerprint
```

| Concern | Implementation |
|---------|----------------|
| Fingerprint / classify | [`api/services/storyline_narrative_materiality.py`](../api/services/storyline_narrative_materiality.py) |
| Finisher prompt + prior canonical | [`api/services/storyline_narrative_finisher_service.py`](../api/services/storyline_narrative_finisher_service.py), [`api/config/prompts/narrative/storyline_walkthrough.md`](../api/config/prompts/narrative/storyline_walkthrough.md) |
| Queue skip/defer + nightly debt drain | [`api/services/content_refinement_queue_service.py`](../api/services/content_refinement_queue_service.py) |
| Enqueue on attach | `maybe_enqueue_narrative_finisher_on_membership` (admit + API add-article) |
| Enqueue on fact snapshot | [`api/services/story_state_service.py`](../api/services/story_state_service.py) (`STORY_STATE_FACT_CHANGE_REFINEMENT`) |
| Env / operators | [`STORYLINE_HISTORICAL_MEMORY.md`](STORYLINE_HISTORICAL_MEMORY.md) |

**Design choice:** Prefer full coherent rewrite on material change over section surgery. Narrow deltas accumulate (`narrow_debt_pending`) until nightly forced finish — skipping unnecessary 70B runs beats shaving sections.

## Living vault twin

Obsidian / vault registry is the longform living twin of the same thesis:

- **Capture → Organize → Distill** — append timelines (idempotent by `article:id`); do not wipe history
- **Express** — morning prime refreshes expansions / daily briefing from vault evidence; fingerprint skip when unchanged; keep prior on coherence reject

See [`VAULT_NOTES_AND_PULL_CONTEXT.md`](VAULT_NOTES_AND_PULL_CONTEXT.md).

## What is intentionally not the same loop (yet)

| Surface | Current behavior vs thesis |
|---------|----------------------------|
| Entity profile *sections* | Refresh rebuilds sections from contexts; not prior-section merge |
| Morning expansion *body* | Rewrites from evidence pack when fingerprint moves (prior body not in prompt) |
| Package compose rounds | Structure accumulates; round prose is re-plan from members + vault framing |
| Targeted section rewrite | Out of scope; narrow → defer + nightly full pass |

Agents and operators should optimize for **compounding clarity**, not only phase throughput.

## Related

- [`STORYLINE_HISTORICAL_MEMORY.md`](STORYLINE_HISTORICAL_MEMORY.md) — memory vs signals; finisher env knobs
- [`VAULT_NOTES_AND_PULL_CONTEXT.md`](VAULT_NOTES_AND_PULL_CONTEXT.md) — living vault / Pull context
- [`MEMPALACE_NI.md`](MEMPALACE_NI.md) — process memory wing/rooms; search/wing hygiene
- [`QUALITY_READER_LOOP.md`](QUALITY_READER_LOOP.md) — reader-facing quality bar
- [`PIPELINE_AND_AUTOMATION.md`](PIPELINE_AND_AUTOMATION.md) — where refinement queue sits in automation
- [`../AGENTS.md`](../AGENTS.md) — agent entry (Project Intent + Key Flows)
