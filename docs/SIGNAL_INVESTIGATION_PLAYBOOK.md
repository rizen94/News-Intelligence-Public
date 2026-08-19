# Signal pieces: investigation dossier + arc report (facts first)

Use this when a story matters (blockades, oil, Saudi / Gulf, major market shocks) instead of expecting every RSS card to be rewritten into think-tank prose.

**Order of work:** evidence hygiene → investigation dossier (facts) → arc brief (context / analogues) → optional prose polish later.

## Why not article summaries

Unified intake extracts entities/events/claims. Article Queue blurbs are usually publisher text or short fallbacks. Professional analysis lives on **tracked events** and **longitudinal arcs**.

## APIs

| Action | Method |
|--------|--------|
| Read dossier | `GET /api/tracked_events/{event_id}/report` |
| Generate dossier | `POST /api/tracked_events/{event_id}/report` |
| Latest arc brief | `GET /api/intelligence/arc_report/{arc_id}/latest` |
| Generate arc brief | `POST /api/intelligence/arc_report/{arc_id}/generate` |
| Citation drill-down | `GET /api/intelligence/citation/{citation_id}` |

Arc generate body (optional):

```json
{
  "report_type": "weekly_brief",
  "retrieval_query": "Houthi Saudi blockade oil shipping Red Sea Hormuz"
}
```

Relevant arc for energy / Gulf supply shocks: **`resource_geopolitics`** (`api/config/historical_arcs.yaml`).

## Operator checklist (facts first)

1. **Identify the signal article** (URL / article id / context id).
2. **Find the tracked event** it is attached to (`event_chronicle_contexts` ↔ context).
3. **Accuracy gate — reject conflation.** Example (2026-07-21): Atlantic Council “Houthis … blockade on Saudi Arabia” (`politics.articles` 353356 → context 327758) is linked to event **2479** “Iran Strait of Hormuz Blockade”. Those are different theaters; do **not** generate a dossier until the chronicle link is corrected or a dedicated Houthi/Red Sea–Saudi event exists.
4. **Confirm chronicles have real developments** (not empty `[]`). Thin chronicles → thin dossiers.
5. **`POST /api/tracked_events/{id}/report`** — dossier sections lead with **What We Know / What's Uncertain / Sources**, then timeline and a short executive summary. Tone is neutral and evidence-bound.
6. **`POST /api/intelligence/arc_report/resource_geopolitics/generate`** with a focused `retrieval_query` for oil / shipping / Gulf implications. Arc reports validate **citation density**; prefer passed validation over fluent uncited prose.
7. **Read citations** via `/api/intelligence/citation/{id}` before treating numbers/dates as established.
8. Optional later: storyline narrative finisher / desk promote for prose — only after facts stabilize.

## Accuracy failure modes to watch

| Symptom | Risk |
|---------|------|
| Many near-duplicate “Hormuz blockade” tracked events | Fragmented evidence; pick a canonical event or merge before reporting |
| Context attached to wrong theater | Confident but wrong dossier |
| Arc report `validation.passed=false` / quarantined | Do not publish; fix citations or regenerate |
| Empty or stub chronicles | Dossier will pad uncertainty — treat as incomplete |

## Example curls (after event hygiene)

```bash
# Dossier for a verified tracked event
curl -sS -X POST "https://news-intelligence-ag.duckdns.org/api/tracked_events/EVENT_ID/report"

# Energy-arc brief scoped to the signal
curl -sS -X POST "https://news-intelligence-ag.duckdns.org/api/intelligence/arc_report/resource_geopolitics/generate" \
  -H "Content-Type: application/json" \
  -d '{"report_type":"weekly_brief","retrieval_query":"Houthi Saudi Arabia blockade oil Red Sea"}'
```

## Related

- Tracked-event dossiers: `api/services/investigation_report_service.py`
- Arc briefs + citation gates: `api/services/slow_report_service.py`
- Signal-first ingest lanes: [SIGNAL_FIRST_OPS.md](SIGNAL_FIRST_OPS.md)
- FtM / mention investigation product: [INVESTIGATION.md](INVESTIGATION.md) (different surface — entity spine, not event dossiers)
