# Storyline Assembly — Conceptual Review

**Status:** Accepted as the connection-model verdict for the event-core rebuild (2026-07-24).  
**Scope:** Conceptual only in this file — implementation lives in migrations + services under `EVENT_CORE_MEMBERSHIP_ENABLED`.

## 1. Executive verdict

The model is wrong at the root, and complicated because it is wrong. Its unit of connection is similarity-to-a-cluster (entity strings, blend scores, embeddings against an accumulating bag); the correct unit is co-reference to a bounded real-world event. No recalibration of weights, thresholds, or gates converts "shares entities with the bag" into "reports the same episode" — those are different claims, and the first cannot approximate the second once the bag drifts. Every downstream layer (absorb gates, HITL at 150, keeper filters, core prune, hygiene freeze, membership review) is compensatory stratigraphy over a membership assertion that asserts nothing. The rebuild window's yield is the tell: zero storylines met even a 70% title-purity bar with a non-disclaiming summary. Salvageable? Partially — the schema half-knows (core vs related, typed chemistry bonds, shell-title detection). Salvage requires redefining what membership means, not tuning how it is computed.

## 2. Weaknesses (ranked)

1. **W1 — Wrong unit of connection.** Similarity-to-bag vs same episode; target drifts with the bag.
2. **W2 — No event identity.** Title + entity bag only; distinctive events get absorbed into megas.
3. **W3 — Recall-attach / keeper-summarize asymmetry.** Storage is wrong if summaries must mask it.
4. **W4 — Self-ratifying pollution.** SEI widening, compound titles, score drift.
5. **W5 — Unpopulated ontology.** Uniform `related`, null `added_by`.
6. **W6 — Domain partition conflated with event identity.**
7. **W7 — Two unreconciled connection systems.** Chemistry does not write `storyline_articles`.
8. **W8 — Hygiene lacks "split"; gates sized for mega-bags.**

## 3. Recommended connection method (summary)

- **Link types:** `same_event`, `causal_link`, `same_instrument`, `actor_episode`; background = RAG only (not membership).
- **Identity:** Anchor set + particulars + arc state on a megathread (`tracked_events`).
- **Founding before absorb:** Rare unowned anchor mints; incumbency grants no claim.
- **Attach:** Retrieval proposes; co-reference disposes; every member names anchor + type.
- **Cross-domain:** Facets on one event; domain never bounds identity.
- **Invariants:** I1 no anonymous membership; I2 membership is evidence; I3 absorb never widens match surface; I4 artifacts never feed membership; I5 one event instance → one megathread.

## 4. Cyclosporiasis gold case

Distinctive name, multi-article, longitudinal origin → effects → resolution, domain-agnostic. Must found a megathread, not be absorbed into geopolitics bags.

## 5. Success metrics

Anchor purity; rare-anchor founding / false-absorb rate; untyped membership → 0; summary traceability; keeper-reject as defect; cross-domain event unity; compound-title incidence; sampled co-reference precision.

See also: [OPERATOR_ANSWERS.md](OPERATOR_ANSWERS.md), [DB_EXAMPLES.md](DB_EXAMPLES.md), [ASSEMBLY_CONNECTION_LOGIC.md](ASSEMBLY_CONNECTION_LOGIC.md).
