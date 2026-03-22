# Science & technology domain strategy

How **science-tech** differs from **politics** in the News Intelligence system, how we ingest breadth of coverage, and how we steer models toward **cross-field influence** and **honest capability bounds**.

---

## Goals

| Politics-style (avoid as default) | Science-tech emphasis |
|-----------------------------------|------------------------|
| Discrete “events” and who did what first | **Capability arcs**: what was demonstrated, under which conditions |
| Rapid scandal / horse-race framing | **Evidence gradation**: preprint vs peer-reviewed vs deployed system |
| Heavy location / actor graph | **Mechanism and dependency**: data, compute, instruments, regulation |

We still extract **events** where useful (trials, approvals, publications), but prompts and priorities de-emphasize political-style fragmentation and stress **only stating links that the text (or consensus public facts) support**.

---

## RSS breadth (migration 173)

New feeds are inserted into **`science_tech.rss_feeds`** (universities, major journals/agencies, research news). Apply with:

```bash
PYTHONPATH=api .venv/bin/python3 api/scripts/run_migration_173.py
```

Canonical ingestion path: **`collect_rss_feeds()`** (orchestrator + automation), same as other domains.

---

## Configuration (`domain_synthesis_config.yaml`)

Under **`domains.science-tech`**:

- **`focus_areas`** — cross-field influence, limits of methods, replication, convergence (AI + wet lab, etc.).
- **`macro_subject_axes`** — stable axes (AI/ML, medicine, genomics/DNA, energy, space, …) used as **hints** for topic extraction and storyline titles, not hard labels.
- **`event_type_priorities`** — research/publication/discovery/trial/approval ahead of generic “news beats”.
- **`storyline_patterns`** — capability arcs, cross-field influence, replication disputes, enabling stack.
- **`editorial_sections`** — “what was shown”, “limits”, “related methods”, “cross-domain connections”.
- **`clustering_similarity_threshold`** — slightly **higher** (0.68) than default to favour substantive technical similarity for storyline clustering.
- **`llm_context`** — long instruction block for synthesis, discovery, briefings: skeptical of vendor claims, no invented cross-field causality.

Reload: config is cached in-process; **restart the API** after editing YAML (or call `reload_config()` where supported).

---

## Code touchpoints

| Area | Behaviour |
|------|-----------|
| **`event_extraction_service`** | For **science-tech**, appends an addendum: prefer research-oriented event types; **no invented continuation_signals** from hype language. |
| **`topic_clustering_service`** | Science-tech gets **expanded topic categories** (genomics, neuroscience, …) and **macro_subject_axes** in the prompt. |
| **`ai_storyline_discovery`** | Storyline title/description generation includes **macro_subject_axes** when domain is set (optional alignment, no forced fit). |
| **Synthesis / editorial / deep_content_synthesis** | Already consume **`llm_context`** from the same YAML. |

---

## Operational rules (for editors and future automation)

1. **Capability hygiene** — If the article does not say it, do not claim general intelligence, clinical benefit, or production scale.
2. **Linking** — Connect pieces when they share **methods, benchmarks, hardware, datasets, regulatory path**, or explicit citations—not buzzword overlap.
3. **Axes are hints** — `macro_subject_axes` help clustering and headlines; they are not a taxonomy enforced in the DB.
4. **Consumer tech** — Remains filtered via **`topic_filter`** and **`briefing_filters.yaml`** for science-tech.

---

## Related docs

- [SOURCES_AND_EXPECTED_USAGE.md](./SOURCES_AND_EXPECTED_USAGE.md) — all ingest sources  
- [DATA_SOURCES_AND_COLLECTION.md](./DATA_SOURCES_AND_COLLECTION.md) — collection cadence  
- [FREE_OPEN_DATA_SOURCES.md](./FREE_OPEN_DATA_SOURCES.md) — future APIs (PubMed, BLS, …)  

---

*Strategy aligned with migration `173_science_tech_rss_and_strategy.sql` and config/code changes in the same delivery.*
