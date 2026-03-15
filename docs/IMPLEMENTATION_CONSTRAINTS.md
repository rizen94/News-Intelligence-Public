# Implementation Constraints

Hard rules for building features in the News Intelligence System. These are not guidelines — they are constraints. Code that violates them is architecturally wrong regardless of whether it "works."

See `docs/CORE_ARCHITECTURE_PRINCIPLES.md` for the reasoning behind each constraint.

---

## Constraint 1: Never Query Articles for User-Facing Content Using Only Metadata

User-facing endpoints (briefings, reports, dashboards) must work with content-derived intelligence, not raw metadata counts.

```python
# WRONG: metadata-only query for a briefing
def _generate_briefing(domain, start_date):
    cursor.execute(f"""
        SELECT COUNT(*), AVG(quality_score)
        FROM {schema}.articles
        WHERE created_at >= %s
    """, [start_date])
    count, quality = cursor.fetchone()
    return f"Processed {count} articles with {quality:.2f} avg quality"

# RIGHT: content-derived query for a briefing
def _generate_briefing(domain, start_date):
    cursor.execute(f"""
        SELECT title, summary, sentiment_label, source_domain
        FROM {schema}.articles
        WHERE created_at >= %s AND summary IS NOT NULL
        ORDER BY quality_score DESC LIMIT 10
    """, [start_date])
    headlines = cursor.fetchall()
    # Build narrative from actual developments
    return _build_narrative_from_headlines(headlines)
```

**Where counts ARE appropriate:** Supporting data, system monitoring, health checks, admin dashboards. Never as the lead content.

---

## Constraint 2: Always Use Editorial Documents as Narrative Source of Truth

When `editorial_document` (storylines), `editorial_briefing` (tracked_events), or `sections` (entity_profiles) are populated, they are the authoritative source for narrative content. Do not regenerate from scratch.

```python
# WRONG: ignoring existing editorial document
def get_storyline_narrative(storyline_id):
    articles = get_storyline_articles(storyline_id)
    return llm.generate(f"Summarize these {len(articles)} articles: {[a['title'] for a in articles]}")

# RIGHT: using editorial document, refining if needed
def get_storyline_narrative(storyline_id):
    storyline = get_storyline(storyline_id)  # must SELECT editorial_document
    ed = storyline.get('editorial_document') or {}
    if ed.get('lede'):
        return ed  # already has narrative
    # Only generate if editorial_document is empty
    articles = get_storyline_articles(storyline_id)
    narrative = llm.generate_editorial(articles)
    save_editorial_document(storyline_id, narrative)  # persist for next time
    return narrative
```

---

## Constraint 3: Never Generate Summaries from Metadata Alone

Any LLM call that produces a summary, narrative, or analysis must work with actual content — article text, extracted facts, entity descriptions, or event chronicles. Titles and counts are not sufficient input.

```python
# WRONG: LLM call with metadata only
prompt = f"Summarize the news: {article_count} articles about {', '.join(categories)}"

# RIGHT: LLM call with content
context_parts = []
for article in top_articles[:5]:
    context_parts.append(f"- {article['title']}: {article['summary'] or article['content'][:300]}")
prompt = f"Write a 2-3 sentence lead for today's briefing based on:\n" + "\n".join(context_parts)
```

---

## Constraint 4: Always Preserve Full Article Content Through the Pipeline

The `content` column must be populated at ingestion and remain accessible. Processing steps add to articles (via `ml_data`, `analysis_results`, `entities`), never remove content.

```python
# WRONG: clearing content after processing
cursor.execute("UPDATE articles SET content = NULL WHERE processing_status = 'completed'")

# WRONG: ingesting without content
def ingest_article(feed_item):
    cursor.execute("INSERT INTO articles (title, url, source_domain) VALUES (%s, %s, %s)",
                   [feed_item.title, feed_item.link, feed_item.source])

# RIGHT: ingesting with content
def ingest_article(feed_item):
    content = fetch_full_text(feed_item.link)  # or feed_item.description
    cursor.execute("""
        INSERT INTO articles (title, url, source_domain, content, excerpt)
        VALUES (%s, %s, %s, %s, %s)
    """, [feed_item.title, feed_item.link, feed_item.source, content, feed_item.description])
```

---

## Constraint 5: Every LLM Call Must Work with Actual Content

LLM calls are expensive and slow. If we're calling the LLM, we should be giving it real content to work with, not titles or counts.

```python
# WRONG: wasting an LLM call on metadata
result = await llm_service.generate_summary(
    f"There are {count} articles in the {domain} domain"
)

# RIGHT: giving the LLM real content to synthesize
headlines = [a['title'] for a in top_articles[:6]]
storylines = [s['title'] for s in active_storylines[:5]]
context = "Headlines:\n" + "\n".join(f"- {h}" for h in headlines)
if storylines:
    context += "\n\nActive storylines:\n" + "\n".join(f"- {s}" for s in storylines)
result = await llm_service.generate_briefing_lead(context, domain=domain)
```

---

## Constraint 6: API Endpoints Must Return Editorial Fields When They Exist

If a table has `editorial_document`, `editorial_briefing`, `sections`, or similar JSONB intelligence fields, the corresponding API GET endpoint must select and return them.

### Current violations (to fix)

**Storylines** — `get_domain_storyline` does not select `editorial_document`:

```python
# CURRENT (wrong): missing editorial fields
cursor.execute("""
    SELECT id, title, description, status, quality_score, ...
    FROM {schema}.storylines WHERE id = %s
""", [storyline_id])

# CORRECT: include editorial fields
cursor.execute("""
    SELECT id, title, description, status, quality_score, ...,
           editorial_document, document_version, document_status
    FROM {schema}.storylines WHERE id = %s
""", [storyline_id])
```

**Tracked events** — `_EVENT_COLS` does not include editorial briefing:

```python
# CURRENT (wrong): _EVENT_COLS missing editorial fields
_EVENT_COLS = "id, event_type, event_name, start_date, end_date, ..."

# CORRECT: include editorial briefing
_EVENT_COLS = "id, event_type, event_name, start_date, end_date, ..., editorial_briefing, editorial_briefing_json, briefing_version"
```

---

## Correct vs Incorrect Patterns: Quick Reference

| Pattern | Wrong | Right |
|---------|-------|-------|
| Briefing content | `f"{count} articles, {quality} quality"` | `f"Key developments: {headline}. Leading storylines: {storyline}"` |
| Storyline response | `{title, status, article_count}` | `{title, status, editorial_document, article_count}` |
| Event response | `{event_name, start_date}` | `{event_name, editorial_briefing, chronicles, start_date}` |
| LLM input | `f"Summarize {count} articles"` | Actual content: summaries, key points, headlines |
| ML pipeline output | `{"processed_at": now}` | `{"summary": ..., "key_points": ..., "sentiment": ..., "processed_at": now}` |
| Briefing hierarchy | Metrics first, narrative maybe | Narrative first, metrics as support |

---

## Common Mistakes

| Mistake | Example | Fix |
|---------|---------|-----|
| Feature works on counts only | "Show user how many articles per category" | Show top headlines per category instead |
| Skipping editorial fields in SELECT | `SELECT id, title FROM storylines` | Add `editorial_document, document_status` |
| Generating from scratch when editorial exists | `llm.generate("summarize...")` on every request | Check `editorial_document` first, refine if stale |
| Not populating editorial fields | Pipeline runs but `editorial_document` stays `{}` | Add pipeline phase to generate/refine editorial docs |
| Treating content as optional | `content = article.get('content', '')` silently | Log warning when content is missing; don't process empty |

---

## Verification Checklist (Pre-Merge)

Before merging any feature that touches articles, storylines, events, or briefings:

- [ ] Does the feature use article content or content-derived fields (not just metadata)?
- [ ] Are editorial document fields included in any new SELECT queries on storylines/events?
- [ ] Does any new LLM call receive actual content (not counts/titles only)?
- [ ] Does the API response lead with narrative content, with metrics as support?
- [ ] Does the feature preserve existing intelligence (no overwrites with less data)?
- [ ] If a new JSONB field is added, is there a pipeline phase that populates it?
