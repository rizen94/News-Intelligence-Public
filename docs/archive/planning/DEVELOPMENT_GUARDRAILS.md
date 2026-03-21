# Development Guardrails

Pre-implementation checklists and rules to prevent architectural intent drift. Use these before writing code, during review, and before merging.

See `docs/CORE_ARCHITECTURE_PRINCIPLES.md` for the principles these guardrails enforce.

---

## Pre-Implementation Checklist

Before writing any feature that touches articles, storylines, events, briefings, or intelligence:

### Content vs Metadata

- [ ] Does this feature work with article **content** (text, summaries, entities) or just **metadata** (counts, status flags, timestamps)?
- [ ] If metadata only: is there a reason content isn't needed? (Admin/monitoring features are OK; user-facing features are not.)

### Intelligence Preservation

- [ ] Does this feature **preserve** existing intelligence through the pipeline?
- [ ] Does it **add** intelligence (new fields, enrichment, narrative) or just **read** existing data?
- [ ] If it modifies JSONB fields (ml_data, editorial_document, etc.): does it **merge** with existing data or **overwrite**?

### Narrative Quality

- [ ] Does the user-facing output tell a **story** ("what happened") or report **statistics** ("how many")?
- [ ] Could a non-technical user understand the output without knowing the database schema?
- [ ] Is there a narrative lead before any metrics?

### Editorial Documents

- [ ] If the feature queries storylines: does it SELECT `editorial_document`, `document_version`, `document_status`?
- [ ] If the feature queries tracked_events: does it SELECT `editorial_briefing`, `editorial_briefing_json`?
- [ ] If the feature queries entity_profiles: does it SELECT `sections`, `relationships_summary`?
- [ ] If editorial fields are empty: does the feature indicate "pending" rather than silently omitting?

### LLM Usage

- [ ] If the feature calls the LLM: does it pass **actual content** (article text, summaries, key points)?
- [ ] Is the LLM input more than just titles and counts?
- [ ] Is the LLM output stored for reuse (in editorial_document, editorial_briefing, etc.) rather than discarded?

---

## Anti-Patterns: What NOT to Build

### The Counting Feature

```python
# DON'T: feature that counts articles and calls it intelligence
def get_domain_intelligence(domain):
    count = db.query(f"SELECT COUNT(*) FROM {schema}.articles")
    return {"intelligence": f"There are {count} articles in {domain}"}
```

Why it's wrong: counting rows is not intelligence. Intelligence is "what those articles say."

### The Metadata Mirror

```python
# DON'T: API that returns the same data the DB stores, without enrichment
def get_storyline(id):
    return db.query("SELECT id, title, status, created_at FROM storylines WHERE id = %s", [id])
```

Why it's wrong: returns the minimum possible data. Should include `editorial_document`, `key_entities`, and enough for a meaningful display.

### The Fresh-Start Generator

```python
# DON'T: regenerate narrative from scratch every time
def get_briefing(domain):
    articles = get_all_articles(domain)
    return llm.generate(f"Summarize {len(articles)} articles about {domain}")
```

Why it's wrong: ignores accumulated intelligence in editorial_document, event_chronicles, entity_profiles. Expensive, inconsistent, and loses refinement history.

### The Silent Omitter

```python
# DON'T: silently skip editorial fields
storyline = get_storyline(id)  # doesn't SELECT editorial_document
if 'editorial_document' not in storyline:
    pass  # just don't show it, no big deal
```

Why it's wrong: hides the fact that editorial content exists (or should exist). The feature should either display it or indicate it's pending.

### The Overwriter

```python
# DON'T: overwrite accumulated intelligence
article['ml_data'] = {"quality_score": new_score, "processed_at": now}
# Lost: summary, key_points, sentiment, argument_analysis
```

Why it's wrong: destroys intelligence from prior pipeline runs. Must merge, not replace.

---

## Decision Framework

When building a new feature, ask:

```
Is this feature user-facing?
├── YES: It must produce narrative content
│   ├── Does editorial_document/editorial_briefing exist for this data?
│   │   ├── YES: Use it as the primary source
│   │   └── NO: Generate it, store it, then use it
│   └── Does the output answer "what happened"?
│       ├── YES: Good — add supporting metrics below the narrative
│       └── NO: Rethink — metrics alone are not intelligence
└── NO: It's admin/monitoring/pipeline
    ├── Metrics and counts are appropriate
    └── But still: preserve content at every step
```

---

## Code Review Checklist

For reviewers checking PRs that touch the intelligence pipeline:

### Data Layer

- [ ] Any new SELECT on storylines includes `editorial_document` fields
- [ ] Any new SELECT on tracked_events includes `editorial_briefing` fields
- [ ] Any new SELECT on entity_profiles includes `sections` and `relationships_summary`
- [ ] Any UPDATE to JSONB fields merges with existing data
- [ ] No DELETE on event_chronicles (append-only)

### API Layer

- [ ] New endpoints follow `APIResponse(success, data, message)` pattern
- [ ] User-facing responses lead with narrative, metrics as support
- [ ] Response includes enough content for UI preview (not just id + title)
- [ ] Editorial fields are exposed when available

### Pipeline Layer

- [ ] New pipeline phases read from content fields, not just metadata
- [ ] Phase output adds intelligence (not just status flags)
- [ ] Phase has a health check query to verify output
- [ ] Existing intelligence is preserved (merge, not overwrite)

### Frontend Layer

- [ ] New views display editorial content prominently
- [ ] Metrics/counts are secondary to narrative
- [ ] Empty editorial fields show "pending" state, not blank space
- [ ] Views link to source articles for provenance

---

## The Transition We're Making

| From | To |
|------|-----|
| System that counts articles | System that understands events |
| Metadata processing | Intelligence extraction |
| Statistical summaries | Editorial narratives |
| `"23 articles processed"` | `"Fed signals rate pause as inflation cools"` |
| Quality score averages | "What happened and why it matters" |
| Processing status dashboards | Intelligence briefings |

Every new feature should move us further along this transition. Every feature that moves us backward (more counting, more metadata, less narrative) is architectural drift.

---

## Related Documentation

| Document | Purpose |
|----------|---------|
| `docs/CORE_ARCHITECTURE_PRINCIPLES.md` | The four principles (Content is King, Intelligence Accumulates, Narratives Over Metrics, Editorial Documents are Primary) |
| `docs/IMPLEMENTATION_CONSTRAINTS.md` | Hard rules with correct vs incorrect code patterns |
| `docs/DATA_FLOW_ARCHITECTURE.md` | The intelligence cascade with content preservation warnings |
| `docs/API_DESIGN_PRINCIPLES.md` | API response standards (narrative-first) |
| `docs/DATABASE_DESIGN_PHILOSOPHY.md` | JSONB field structures and design rules |
| `docs/ORCHESTRATION_REQUIREMENTS.md` | Pipeline phase requirements and health checks |
| `docs/SYSTEM_OVERVIEW.md` | Full system map (routes, components, data flow) |
