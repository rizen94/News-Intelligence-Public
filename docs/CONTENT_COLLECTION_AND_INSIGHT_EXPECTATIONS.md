# Content Collection and Insight Expectations

What to expect from the system now that it is stable and running: how fast content flows, how backlogs behave, and when you can expect useful insights.

**Audience:** Operators and product owners.  
**Related:** [AUTOMATION_AND_LAST_24H_ACTIVITY.md](AUTOMATION_AND_LAST_24H_ACTIVITY.md), [CONTROLLER_ARCHITECTURE.md](CONTROLLER_ARCHITECTURE.md).

---

## 1. How collection and processing run

### Collection (ingestion)

| What | Typical interval | What happens per run |
|------|------------------|----------------------|
| **RSS** | 30 minutes | Fetches all configured feeds; new articles inserted per domain. Volume depends on feeds (often tens to low hundreds of new items per run across all domains). |
| **Context sync** | 15 minutes | Syncs articles → `intelligence.contexts` (100 per batch per domain). |
| **Orchestrator** | ~60 s loop | Decides when to run RSS (or gold/EDGAR for finance); does not run every cycle. |

RSS is the main content source. If you have few feeds or low-update feeds, new-article volume will be low; add or tune feeds to increase it.

### Processing (enrichment and intelligence)

The **AutomationManager** runs many phases on schedules. When **backlog is high** (e.g. >200 pending items for a phase), the scheduler shortens the effective interval to about **5 minutes** for batch phases so work drains faster.

| Phase type | Base interval | Batch / cap per run | Notes |
|------------|---------------|---------------------|--------|
| Article processing | 20 min | Batch (continuous until empty) | Raw → content, status |
| ML processing | 20 min | Batch | Summary, key points, sentiment (Ollama) |
| Topic clustering | 20 min | 20 articles/cycle, 3 domains | LLM; balanced new/low/medium confidence |
| Entity extraction | 20 min | Batch | People, orgs, etc. (Ollama) |
| Entity organizer | 20 min | Resolution batch | Aliases, merge, cross-domain link |
| Context sync | 15 min | 100 contexts/batch per domain | Articles → contexts |
| Claim extraction | 30 min | Max 50 contexts/run | LLM; rate-limited |
| Event tracking | 15 min | 300 contexts/run | Link contexts to tracked events |
| Entity profile build | 30 min | 15 profiles/run | Compile dossiers |
| Entity enrichment | 2 hours | 20 entities/run | Wikipedia + LLM |
| Editorial document | 30 min | 5 storylines/run | LLM narrative per storyline |
| Editorial briefing | 30 min | 5 events/run | LLM narrative per event |
| Data cleanup | 24 hours | — | e.g. articles older than 30 days |

So: **collection** adds new articles every 30 min (RSS); **processing** runs every 15–30 min (or 5 min when backlog is high) and works through articles, contexts, entities, storylines, and events in batches.

---

## 2. Backlogs: what to expect

- **Backlog = pending work** for a phase (e.g. articles not yet in contexts, contexts not yet claim-extracted, storylines without editorial_document).
- The scheduler **skips** a phase when there is **no** pending work (for phases that are “skip when empty”).
- When backlog is **above threshold** (e.g. 200), the system runs that phase **more often** (about every 5 minutes) until the backlog shrinks.
- So: **backlogs drain over time**; they do not require manual clearing. A large initial backlog (e.g. thousands of articles) may take **several hours to a day or two** to work through, depending on:
  - Number of articles / contexts / entities
  - Ollama/LLM speed (CPU vs GPU, model size)
  - Batch sizes and rate limits (claim extraction, entity enrichment are intentionally capped).

**Reasonable expectation:** Let the system run. After 24–48 hours of continuous operation, most “first pass” backlogs should be reduced; ongoing backlog should reflect **new** work (new articles) rather than old buildup.

---

## 3. When to expect “good” insights

Insights (briefings, storylines, entity dossiers, event chronicles) depend on:

1. **Enough raw content** — Articles in the DB from RSS (and optionally other sources).
2. **Enough processing passes** — Articles → ML → entities → contexts → claims → storylines/events → editorial.
3. **Enough time** — So that storylines have multiple articles, events have multiple chronicle entries, and entities have multiple mentions.

Rough timeline:

| Timeframe | What you can expect |
|-----------|----------------------|
| **First 24 hours** | New articles appearing; article processing and ML starting to fill `ml_data`; some entities and topics; backlogs may be high. |
| **24–48 hours** | Contexts and claims building; entity resolution and profiles starting; some storylines and tracked events getting first editorial or briefing content. |
| **3–7 days** | More stable: daily briefings and “Today’s Report” have enough storylines and events to be useful; entity dossiers and positions start to be meaningful where you have multiple articles per entity. |
| **1–2 weeks** | Richer storylines, better entity resolution and cross-domain links, more complete event chronicles and editorial briefings. |

So: **plan on at least a few days of continuous operation** before judging insight quality. The first day or two are mostly fill-up and backlog drain.

---

## 4. What “stable and running” means day to day

- **RSS** runs on schedule (e.g. every 30 min when the API is up); **orchestrator** can also trigger collection. Check **Monitor** and (if you use it) the last-24h report to confirm recent collection.
- **Processing** runs in the background; no need to “trigger pipeline” for normal operation. Use **Monitor** for health and pipeline status.
- **Briefings / Report** pull from storylines and tracked events; they improve as more storylines have `editorial_document` and more events have `editorial_briefing` (both generated by the 30-min editorial phases).
- **Entity resolution and dossiers** improve over time as more articles are processed and the entity organizer and profile builder run (20 min and 30 min intervals).
- **Fact verification and content synthesis** are available via API; they are more useful once you have a body of claims and multiple sources (again, a few days of content helps).

If the API is up and the database is healthy, the system will keep collecting and processing; **consistency (uptime) matters more than tuning in the first week.**

---

## 5. Optional checks

- **Last-24h report** — Run `./scripts/run_last_24h_report.sh` to see articles collected per domain, RSS fetch status, and any gaps.
- **Monitor page** — Use it to confirm health, pipeline status, and (if exposed) backlog or last-run info.
- **Feed configuration** — If you see very few new articles, add or adjust RSS feeds and ensure they’re active and not failing.

---

## Summary

- **No need to clear the DB for v6;** the system is additive and will backfill.
- **Backlogs drain automatically**; allow **several hours to a day or two** for a large initial backlog.
- **Useful insights** (briefings, storylines, entity/event intelligence) typically need **at least 3–7 days** of steady collection and processing.
- **Stable and running** means: keep the API up, ensure DB and Ollama are available, and let the automation run; then check again after a few days.
