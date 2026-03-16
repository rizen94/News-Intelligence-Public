# How Story Elements Are Assembled — And When Data Adds Up

**Purpose:** Clarify how contexts, entities, and pipelines feed into the **final product**; what **minimums and caps** apply; and whether we're storing **repetitive or low-value data** that never contributes to stories.

**Related:** [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md), [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md), [STORYLINE_ENHANCEMENT_SPEC.md](STORYLINE_ENHANCEMENT_SPEC.md).

---

## 1. The Big Picture: Where Your 18k Contexts and 16k Entities Go

| Layer | What you have | How it’s used in “story” products |
|-------|----------------|------------------------------------|
| **Contexts** (18,662) | One row per article in `intelligence.contexts` (1:1 via `article_to_context`). | **Not** dumped wholesale into any one story. Used in: (1) **Claim extraction** — batch of contexts → `extracted_claims`. (2) **Event discovery** — LLM groups unlinked contexts into `tracked_events` + `event_chronicles`. (3) **Investigation report** — only contexts **linked to that event** (via chronicle `developments`) are pulled; typically tens per event, not thousands. (4) **Entity profile builder** — contexts linked to entities via `context_entity_mentions` feed `entity_profiles.sections`. So each context *can* contribute to claims, one event, and/or entity dossiers, but **assembly always uses a bounded set** (by event, by entity, or by time + limit). |
| **Entities** (16,195) | Rows in `intelligence.entity_profiles` (from `entity_canonical` + sync). | **Domain synthesis** caps at **20 entities** per domain (top by mention count in the time window). **Storyline editorial** uses up to 10 entity names from the storyline’s articles. **Report/Briefing** don’t query entity_profiles for the lead; they use **articles + storylines + events**. So the 16k are a pool; any single “story” product only uses a small slice (e.g. top 20 by mentions, or entities attached to one storyline). |
| **Tracked events** | Rows in `intelligence.tracked_events` (+ chronicles). | **Report:** up to 8 events (list). **Briefing:** up to 5 events with briefings. **Investigation report:** one event + its chronicles + only the **contexts referenced in those chronicles**. So again, a small subset. |

So: **we do not need a minimum threshold of contexts or entities to get “good” story results.** The system is designed to **cap** how much goes into each product. Quality and recency determine *which* slice is used, not “do we have enough rows.”

---

## 2. How Each Final Product Is Picked and Assembled

### 2.1 Today’s Report (Report page)

- **Source:** Three independent API calls: `getArticles(limit: 12)`, `getStorylines()`, `getTrackedEvents(limit: 8)`.
- **Assembly:** No synthesis step. The UI takes:
  - **Lead:** First event (if any), else first storyline, else first article — by **list order** from the APIs.
  - **Secondary:** Next two items (same ordering).
  - **Digest:** Next articles/storylines/events from those lists.
- **Thresholds:** None. Whatever the APIs return (latest by default) is shown. So “good” results depend on **what’s in the list** (e.g. storylines with `editorial_document` filled, events with `editorial_briefing`), not on a minimum count of contexts or entities.

### 2.2 Briefings (daily / key developments)

- **Source:** `daily_briefing_service._extract_key_developments()`:
  - **Articles:** Last N days, **quality_tier 1–2 preferred**, then quality_score, then recency; **limit 15** → then **top 10** after filters.
  - **Storylines:** **Limit 8** (with editorial_document when present).
  - **Events:** **Limit 5** (with editorial_briefing).
- **Assembly:** Key developments = headlines + storyline titles/ledes + event briefings. Optional **LLM-generated lead** from that mix. Then **user feedback** (e.g. not_interested) and **priority sort** (e.g. demote sports/celebrity).
- **Thresholds:** No “minimum contexts.” Quality and recency and feedback determine which 10 headlines / 8 storylines / 5 events make it. So “good” briefings depend on (1) **quality_tier** and **editorial_document** / **editorial_briefing** being populated, and (2) not over-filtering so that the list is empty.

### 2.3 Domain synthesis (backend “everything for a domain”)

- **Source:** `content_synthesis_service.synthesize_domain_context(domain_key, hours, max_articles=30, max_storylines=10, max_events=10, max_entities=20)`.
- **Assembly:** Single block with:
  - **Articles:** Time window, **limit 30** (by recency).
  - **Storylines:** Active, **limit 10** (by updated_at).
  - **Events:** For domain, **limit 10** (by updated_at).
  - **Entities:** From **article_entities** for those articles, **limit 20** (by mention count).
  - **Claims:** From **extracted_claims** for domain contexts, **limit 20**.
  - **Patterns:** **limit 10**.
- **Used by:** Products that need “one big context block” for a domain (e.g. LLM briefing lead, or future editorial endpoints). So **synthesis never sees all 18k contexts or 16k entities** — it sees at most 30 articles, 10 storylines, 10 events, 20 entities, 20 claims, 10 patterns per call.

### 2.4 Storyline editorial document

- **Source:** `editorial_document_service.generate_storyline_editorial()`: for each storyline, **up to 12 articles** (from `storyline_articles`), ordered by published_at.
- **Assembly:** Build a text block from article titles, summaries/key_points, sentiment, and up to 10 entity names; then **LLM** produces `editorial_document` (lede, developments, analysis, outlook).
- **Threshold:** If a storyline has **fewer than 1 article**, it’s skipped. So **at least 1 article** is the only hard minimum; “good” results depend on article quality and having a few articles (e.g. 3–5+) for a coherent narrative.

### 2.5 Investigation report (event dossier)

- **Source:** `investigation_report_service`: one **tracked_event** + its **event_chronicles** + only the **contexts whose IDs appear in chronicle developments**.
- **Assembly:** Chronicle summaries + context excerpts → single markdown report (executive summary, timeline, entities, sources, what we know / uncertain).
- **Thresholds:** No minimum context count. If an event has zero chronicles or zero linked contexts, the report is thin. So “good” here depends on **event discovery** and **chronicle builder** having run so that the event has developments and linked contexts.

---

## 3. Do We Need a Minimum Threshold for “Good” Story Results?

- **No fixed “minimum contexts” or “minimum entities”** is required for the pipelines to run or for products to render. The design uses **caps and time windows**, not “require at least N.”
- **What actually improves “good” results:**
  - **Report:** Having at least a few **storylines** or **events** with **editorial_document** / **editorial_briefing** filled (so the lead isn’t just a raw article list).
  - **Briefings:** **quality_tier** and **editorial_document** / **editorial_briefing** populated; **user feedback** so the right items surface.
  - **Storyline editorial:** Storylines with **at least a few articles** (e.g. 3–5+) and articles with **ml_data** (summary, key_points) so the LLM has something to synthesize.
  - **Investigation reports:** **Tracked events** existing and **event_chronicles** populated so there are developments and linked contexts.

So “good” is about **quality and richness of the slice we pick**, not about hitting a global minimum count of contexts or entities.

---

## 4. Are We Filling the Database with Repetitive or Junk Data?

**Contexts**

- **Not repetitive by design:** One context per article (`article_to_context`). So 18k contexts ≈ 18k articles. We don’t create duplicate contexts for the same article.
- **“Junk” risk:** If many **articles** are low-value (e.g. clickbait, near-duplicates, or empty content), then we have many **low-value contexts**. They still only get used in assembly when they’re in the **capped subset** (e.g. by recency, or by event link). So we’re not “adding up” 18k into one story; we’re **selecting** a small subset. Quality gates (e.g. **quality_tier**, **storyline discovery** quality filters) apply when we **choose** articles for storylines or briefings; they don’t delete low-quality contexts from the DB. So the DB can contain many low-signal contexts; the **product** is protected by **limits and quality-aware selection**, not by deleting data.

**Entities**

- **Possible redundancy:** 16k **entity_profiles** can include duplicates (same person/org under different canonical ids) or very low-value names (e.g. one mention, noise). There is **entity resolution / merge** work in the codebase; how much is applied affects duplication.
- **Use in stories:** Only a **bounded set** (e.g. top 20 by mentions in domain synthesis, or entities attached to a storyline’s articles) is used in any one product. So again, “junk” entities can sit in the DB without being forced into every story.

**Summary**

- We’re **not** “filling the DB with repetitive junk that adds up into one story.” We’re **accumulating** contexts and entities that **can** be used; **assembly always picks a bounded subset** (by time, limit, event, or storyline).
- If you want **less** low-value data in the DB, that’s a separate concern: e.g. **stricter quality at ingestion**, **deduplication of articles** before context creation, or **entity merge** to reduce redundant profiles. The current design avoids “junk adding up” in the **final product** by **caps and selection**, not by refusing to store data.

---

## 5. End-to-End: From Pipelines to Final Product

```
RSS → articles (per domain)
  → ML processing (summary, key_points, sentiment, quality_tier)
  → entity extraction (article_entities, entity_canonical)
  → context_processor: 1 context per article (intelligence.contexts + article_to_context)
       → link_context_to_article_entities → context_entity_mentions
  → claim_extraction (batch of contexts → extracted_claims)
  → event_tracking (unlinked contexts → LLM → tracked_events + event_chronicles)
  → entity_profile_builder (contexts per entity → entity_profiles.sections)

Storylines (separate path):
  articles + storyline_articles (manual or discovery)
  → storyline_processing / editorial_document_service: up to 12 articles → editorial_document (lede, developments, …)

Final products:
  • Report page:     getArticles(12) + getStorylines() + getTrackedEvents(8) → lead + secondary + digest
  • Briefing:        key_developments (articles 15→10, storylines 8, events 5) + quality + feedback → optional LLM lead
  • Domain synthesis: synthesize_domain_context (30 articles, 10 storylines, 10 events, 20 entities, 20 claims, 10 patterns)
  • Storyline view:  storyline + 12 articles → editorial_document
  • Event report:   event + chronicles + linked contexts only → one markdown dossier
```

So: **pipelines fill the DB** (contexts, entities, claims, events, storylines, editorial_document). **Assembly layers** (Report, Briefing, synthesis, storyline editorial, investigation report) **read a bounded subset** of that data and, where applicable, apply **quality and feedback** before presenting. The “final product” is always a **curated slice**, not a dump of all 18k contexts or 16k entities.

---

## 6. Practical Takeaways

| Question | Answer |
|----------|--------|
| Do we need a minimum threshold of contexts/entities for good story results? | No. We use **caps and time windows**. Good results depend on **quality and richness** of the slice (editorial_document, editorial_briefing, quality_tier, a few articles per storyline). |
| Are we filling the DB with repetitive junk? | Contexts are 1:1 with articles (no duplicate contexts per article). Redundancy is possible in **entities** (duplicate canonicals). **Assembly never uses all data**; it uses limits (e.g. 30 articles, 20 entities, 10 storylines per domain). So junk can exist in the DB but doesn’t “add up” into one story. |
| What does the final product look like and how is it picked? | **Report:** latest 12 articles + storylines + 8 events; lead = first of event/storyline/article. **Briefing:** top 10 headlines + 8 storylines + 5 events (quality and feedback applied). **Storyline editorial:** up to 12 articles per storyline → LLM → lede/developments/analysis/outlook. **Event report:** one event + its chronicles + only contexts linked in those chronicles → one dossier. So each product is a **small, bounded set** chosen by recency, quality, and (where applicable) user feedback. |

If you want to tighten “what counts as good” or reduce low-value data in the DB, the levers are: **stricter quality at ingestion**, **quality_tier / briefing filters**, **entity resolution/merge**, and **optional cleanup** (e.g. archiving or dropping very old, never-linked contexts). The assembly logic is already designed so that **the final product is not a direct sum of all stored data**.
