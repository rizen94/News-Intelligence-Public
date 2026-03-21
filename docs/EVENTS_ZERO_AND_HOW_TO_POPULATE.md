# Why "Events" Can Be 0 and How to Populate Them

> **Different from “Extracted Events” on the domain `/events` page**  
> That page lists **`public.chronological_events`** (LLM + `event_extraction` automation).  
> This doc is about **`intelligence.tracked_events`** (investigation / dashboard).  
> See [EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md](./EXTRACTED_EVENTS_AND_ENTITY_PIPELINE.md) and run `scripts/poll_extracted_events_and_pipeline.py` to audit chronological events.

The status bar shows **Contexts**, **Entities**, and **Events**:

- **Contexts** — Rows in `intelligence.contexts` (created from articles by the context processor). Your 18,662 means the pipeline is running.
- **Entities** — Rows in `intelligence.entity_profiles` (from entity sync + profile builder). Your 16,195 means that pipeline is running.
- **Events** — Rows in `intelligence.tracked_events`. These are **tracked events** (e.g. "2026 Midterms", "Fed rate decision March 2026"), not raw article counts.

**Events: 0** means no tracked events exist yet. They can be created in two ways.

---

## 1. Automatic discovery (LLM)

The **event_tracking** automation task (every ~15 min) runs `event_tracking_service.run_event_tracking_batch()`:

1. Fetches "unlinked" contexts (contexts not yet in any event chronicle).
2. Sends batches to the LLM (Ollama) to group them into real-world **events** (e.g. conflict, election, legislation).
3. Only creates an event when **at least 2 contexts** are grouped as the same event.
4. Inserts into `intelligence.tracked_events` and `intelligence.event_chronicles`.

**So Events can stay 0 if:**

- **Ollama is not running** — discovery uses the LLM; if the call fails, no events are created.
- **LLM returns no valid events** — e.g. empty array, or every proposed event has &lt; 2 valid context IDs, or JSON parse fails.
- **Task is disabled** — in `api/config/context_centric.yaml` under `tasks.event_tracking: false` (default is true).
- **Automation hasn’t run yet** — e.g. API just started; give it a few cycles (15–30 min) or trigger manually (below).

---

## 2. Manual creation (UI or API)

You can create events yourself; they don’t depend on the LLM.

- **UI:** **Investigate → Events** (or Tracked Events). Use “Create event” to add one (e.g. event type, name, dates, domain).
- **API:**  
  `POST /api/context_centric/tracked_events`  
  with body e.g.  
  `{"event_type": "election", "event_name": "2026 Midterms", "start_date": "2026-01-01", "domain_keys": ["politics"]}`  
  (see API docs or `context_centric.py` for full schema).

---

## 3. Trigger discovery manually

To run event discovery once (e.g. to seed events from existing contexts):

```bash
curl -X POST "http://localhost:8000/api/context_centric/discover_events?domain_key=politics&limit=100"
```

Repeat for `domain_key=finance` and `domain_key=science-tech` if you want. The response includes `events_created` and any `error` or `message` (e.g. "No unlinked contexts", "LLM returned no valid events").

**Check:**

- Ollama is running (`curl http://localhost:11434/api/tags` or your Ollama URL).
- API logs after the POST for `discover_events` or `event_tracking` (e.g. "LLM proposed N events", "created N events", or an error).

---

## Summary

| Source        | How events get created                          |
|---------------|---------------------------------------------------|
| Automation    | Every ~15 min, LLM groups unlinked contexts → new `tracked_events`. |
| Manual        | Investigate → Events, or `POST /api/context_centric/tracked_events`. |
| Manual trigger| `POST /api/context_centric/discover_events?domain_key=...&limit=100`. |

If you want **Events** to increase automatically, keep Ollama up and ensure `event_tracking` is enabled; if you’re fine with a few hand-picked events, create them via the UI or API and the count will reflect that.
