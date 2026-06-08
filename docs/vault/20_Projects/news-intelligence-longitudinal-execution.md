# News Intelligence — Longitudinal execution plan

**Status:** Phase 0 in progress (started 2026-05-26)  
**Progress log:** [[10_Runbooks/06-longitudinal-phase-progress]]  
**Repo:** `docs/LONGITUDINAL_INTELLIGENCE_EXECUTION.md` (full plan)  
**Doctrine:** [[40_Reference/news-intelligence-chronological-doctrine]] → `docs/CHRONOLOGICAL_ACCURACY_DOCTRINE.md`

---

## Mission

Slow-journalism engine: ingest → filter → accumulate durable facts → merge with **reference history** (decades) → **cited weekly arc reports**. Not real-time breaking news.

## MVP arcs (14 weeks)

| Arc | Span |
|-----|------|
| `resource_geopolitics` | 1973–present |
| `political_tensions_multipolar` | 1945–present |

## Dual-layer memory

- **Living corpus** — RSS/PDF forward from ingest (`versioned_facts`, storylines)
- **Reference corpus** — seeded events, FRED/ALFRED vintages, Wikipedia (Kiwix), ACLED/UCDP

## Phase timeline

| Weeks | Phase | Deliverables |
|-------|-------|--------------|
| 1–2 | 0 Foundation | Claim pipeline, backlog diagnosis, backup policy, provenance migration 221 |
| 2–4 | 1 Infrastructure | Wikidata QIDs, pgvector, reference_events, macro vintages, hard ingest exclude |
| 4–7 | 2 Data + 3 Curation | RSS, Kiwix, ACLED/UCDP, sanctions, trade; 25–30 reference events |
| 7–10 | 4 Synthesis | Arc catalog, slow reports, eval harness |
| 9–13 | 5 UI | Citation drawer, Arc Spine, Weekly Brief, Heatmap, Analogues |
| 12–14 | 6 Operator | Curation UI, feedback weighting |

## Definition of done

Sunday: open `resource_geopolitics`, read ~1000-word Weekly Brief, click any claim for source + three timestamps, view Arc Spine with macro + reference events, see prior analogues — every date/number from structured data.

## Deferred

Homelab MCP / Open WebUI; daily World Pulse ticker; pop culture/sports.
