# Briefing Filters and User Feedback

> **Purpose:** Teach the system what you like and demote sports/celebrity/entertainment so politics (and other domains) stay on-topic.  
> **Last updated:** 2026-03-06.

---

## 1. User feedback (Briefings UI)

On the **Briefings** page you can:

- **Not interested** — Mark an article or storyline as not interesting. It is excluded from future briefing feed and from key developments in generated briefings.
- **Useful 1–5** — Rate how useful an item or the whole briefing was. Stored for future ordering/learning.

Feedback is stored in `public.content_feedback` and applied when:

- Loading the **Today's Briefing** tab (articles and storylines come from `/api/{domain}/intelligence/briefing_feed`, which excludes “not interested” and demotes low-priority).
- Generating the **daily briefing** text (key developments exclude “not interested” and demote sports/celebrity).

---

## 2. Low-priority / blocklist (sports, celebrity, entertainment)

Content that matches the **low-priority** list is **demoted** (moved to the end of the list), not dropped. That keeps the lead story on-topic (e.g. politics) while still allowing off-topic items to appear lower.

- **Config file:** `api/config/briefing_filters.yaml`
  - `low_priority_entities`: Names (e.g. “Kobe Bryant”, “Taylor Swift”) — substring match on title/lede/summary.
  - `low_priority_keywords`: Phrases (e.g. “super bowl”, “celebrity gossip”, “box office”) — word-boundary match.

- **RSS ingest:** Unchanged. `api/collectors/rss_collector.py` still uses `is_excluded_content()` to **drop** articles at collection time (sports/entertainment keywords). The briefing filter is an extra layer for **ranking** what already made it in (e.g. a politics feed that sometimes carries a celebrity story).

**To add more names or keywords:** Edit `api/config/briefing_filters.yaml` and restart the API (or rely on the next load of the config when generating a briefing).

---

## 3. API

| Endpoint | Method | Description |
|----------|--------|--------------|
| `/api/{domain}/intelligence/feedback` | POST | Submit feedback: `item_type` (article \| storyline \| briefing), `item_id` (optional for briefing), `rating` (1–5), `not_interested` (boolean). |
| `/api/{domain}/intelligence/briefing_feed` | GET | Articles and storylines for the Briefings page, reordered: not interested excluded, low-priority demoted. Params: `articles_limit`, `storylines_limit`. |

---

## 4. Database

- **Migration 163:** `public.content_feedback` table (domain, item_type, item_id, rating, not_interested, created_at).

Run migrations so the table exists; the YAML config does not require DB changes.
