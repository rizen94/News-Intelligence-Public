# API Design Principles

Rules for how API endpoints must behave in the News Intelligence System. Every endpoint that returns content to a user must return narrative intelligence, not database statistics.

See `docs/CORE_ARCHITECTURE_PRINCIPLES.md` for the principles behind these rules.

---

## Rule 1: Briefing Endpoints Must Return Narrative Content

Briefing endpoints exist to answer "what happened and why it matters." They must lead with editorial content.

### Required response hierarchy

```
1. Narrative lead     — LLM-generated or from editorial documents
2. Key developments   — actual headlines and storyline titles
3. Supporting metrics  — article counts, quality scores, source diversity
```

### Example: POST /{domain}/intelligence/briefings/daily

```json
{
  "success": true,
  "data": {
    "content": "Lead: The Federal Reserve signaled a pause on rate hikes as inflation data showed cooling across key sectors...\n\nKey developments: Fed signals rate pause as inflation cools; Treasury yields drop on soft jobs data\n\nLeading storylines: Federal Reserve monetary policy; Commercial real estate exposure\n\nSystem overview (last 3 days): 47 new articles, 12 updated.\nQuality: 0.68 avg score.",
    "article_count": 47,
    "sections": {
      "key_developments": {
        "top_headlines": [
          {"title": "Fed signals rate pause as inflation cools", "source": "Reuters"},
          {"title": "Treasury yields drop on soft jobs data", "source": "Bloomberg"}
        ],
        "top_storylines": [
          {"id": 42, "title": "Federal Reserve monetary policy", "article_count": 8},
          {"id": 55, "title": "Commercial real estate exposure", "article_count": 5}
        ],
        "has_content": true
      },
      "system_overview": {"today_new_articles": 47, "today_updated_articles": 12},
      "quality_metrics": {"overall_quality_score": 0.68}
    }
  }
}
```

### What NOT to return as primary content

```json
{
  "content": "System overview (last 3 days): 47 new articles, 12 updated. Content (last 3 days): 5 categories, 47 articles analyzed. Quality: 0.68 avg score."
}
```

This tells the user nothing about what happened in the world.

---

## Rule 2: Storyline Endpoints Must Include Editorial Documents

When `editorial_document` is populated, it must be returned. When it's empty, the response should indicate that editorial content is pending.

### Example: GET /{domain}/storylines/{id}

```json
{
  "success": true,
  "data": {
    "storyline": {
      "id": 42,
      "title": "Federal Reserve monetary policy",
      "status": "active",
      "description": "Tracking Fed rate decisions and monetary policy signals",
      "editorial_document": {
        "lede": "The Federal Reserve is navigating a delicate balance between controlling inflation and avoiding recession...",
        "developments": [
          "March FOMC meeting maintained rates at 5.25-5.50%",
          "February CPI came in at 3.1%, above expectations"
        ],
        "analysis": "The Fed's dot plot suggests...",
        "outlook": "Markets are pricing in..."
      },
      "document_version": 3,
      "document_status": "refined",
      "quality_score": 0.82,
      "total_articles": 8,
      "key_entities": {"people": ["Jerome Powell"], "organizations": ["Federal Reserve"]},
      "updated_at": "2026-03-06T14:30:00Z"
    },
    "articles": [...]
  }
}
```

### Current gap

The `get_domain_storyline` endpoint does not SELECT `editorial_document`, `document_version`, or `document_status`. These columns exist (migration 158) but are not returned.

---

## Rule 3: Event Endpoints Must Include Editorial Briefings

Tracked events must return their editorial briefing and chronicles. These tell the story of the event over time.

### Example: GET /api/tracked_events/{id}

```json
{
  "id": 15,
  "event_type": "policy_change",
  "event_name": "Federal Reserve March 2026 Rate Decision",
  "start_date": "2026-03-01",
  "editorial_briefing": "The Federal Reserve held rates steady at its March meeting, signaling patience as inflation data remains mixed...",
  "editorial_briefing_json": {
    "headline": "Fed holds rates steady, signals patience",
    "summary": "...",
    "impact": "Markets rallied on the decision...",
    "what_next": "Next FOMC meeting in May..."
  },
  "briefing_version": 2,
  "chronicles": [
    {
      "update_date": "2026-03-06",
      "developments": "New jobs data released...",
      "analysis": "The labor market cooling supports...",
      "predictions": "Rate cut probability now at 60%...",
      "momentum_score": 0.7
    }
  ],
  "domain_keys": ["finance", "politics"]
}
```

### Current gap

`_EVENT_COLS` in `context_centric.py` does not include `editorial_briefing` or `editorial_briefing_json`. These columns exist (migration 158) but are not returned.

---

## Rule 4: No Endpoint Should Return Counts as Primary Content

Counts belong in `supporting_data` or `metadata`, never as the main response payload for user-facing endpoints.

### Where counts ARE the right answer

- `GET /api/system_monitoring/fast_stats` — system health dashboard
- `GET /api/statistics` — aggregation statistics for admin
- `GET /api/rss_feeds/duplicates/stats` — dedup monitoring
- `GET /api/system_monitoring/process_run_summary` — automation monitoring

### Where counts are NOT the right answer

- Briefings — users want to know what happened
- Storyline views — users want the narrative
- Event views — users want the chronology
- Intelligence dashboard — users want insights

---

## Rule 5: List Endpoints Should Include Enough for Preview

List endpoints (articles, storylines, events) should return enough content for the UI to show meaningful previews, not just IDs and titles.

### Articles list: include summary

```python
# Minimum fields for article list preview
SELECT id, title, LEFT(summary, 200) as summary, source_domain,
       published_at, quality_score, sentiment_label, category
FROM {schema}.articles
```

### Storylines list: include description and editorial status

```python
# Minimum fields for storyline list preview
SELECT id, title, description, status, total_articles, quality_score,
       document_status, updated_at
FROM {schema}.storylines
```

### Events list: include editorial briefing excerpt

```python
# Minimum fields for event list preview
SELECT id, event_name, event_type, start_date, end_date,
       LEFT(editorial_briefing, 200) as briefing_excerpt,
       briefing_status, domain_keys
FROM intelligence.tracked_events
```

---

## Response Shape Standards

All API responses follow the `APIResponse` pattern:

```python
{"success": True, "data": {...}, "message": None}
{"success": False, "data": None, "message": "Error description"}
```

For content-rich endpoints, `data` should include:

```json
{
  "content": "...",
  "editorial": { ... },
  "supporting_data": { "counts": ..., "metrics": ... },
  "metadata": { "generated_at": "...", "version": ... }
}
```

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Returning `{"articles_count": 23}` as briefing content | Return narrative lead + headlines + storylines |
| Omitting `editorial_document` from storyline response | Add to SELECT and response |
| Omitting `editorial_briefing` from event response | Add to `_EVENT_COLS` and response |
| Article list with only `id, title, url` | Add `summary`, `quality_score`, `sentiment_label` |
| Generating narrative on every request | Cache in editorial_document; refine when stale |

---

## Verification Checklist

For any new or modified endpoint:

- [ ] Does the response include narrative/editorial content when available?
- [ ] Are editorial fields (editorial_document, editorial_briefing, sections) SELECTed and returned?
- [ ] Is the primary content narrative, with counts/metrics as secondary?
- [ ] Do list endpoints include enough for meaningful previews?
- [ ] Does the response follow the `APIResponse(success, data, message)` pattern?
