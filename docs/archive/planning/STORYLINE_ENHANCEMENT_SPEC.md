# Comprehensive Storyline Enhancement with Quality Integration

**Status:** Phase 1 implemented (quality-aware discovery, living-by-default, migration).  
**Remaining:** Integration points (Report/Briefing/Event/Entity UI), editorial pipeline quality weighting, quality dashboard.  
**Related:** [STORYLINE_V6_ASSESSMENT.md](STORYLINE_V6_ASSESSMENT.md), [CONTENT_QUALITY_STANDARDS.md](CONTENT_QUALITY_STANDARDS.md), [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md).

---

## 1. Quality-Aware Storyline Discovery ✅

**Implemented** in `api/services/storyline_automation_service.py`:

- **Quality gates** (before scoring):
  - Filter out `quality_tier > storyline.min_quality_tier` (1=best, 4=worst).
  - Filter out `clickbait_probability > clickbait_threshold` (default 0.6).
  - Filter out `fact_density < min_fact_density` (default 0.15) when present.
  - Optional `require_named_sources` (not yet wired to article data).
- **Scoring:** `final_score = (relevance_score * 0.7) + (quality_score * 0.3)`; used for suggestions and auto-add.
- **Tracking:** `storyline.quality_metrics` updated each run with `filter_stats`, `articles_passed`, `avg_quality_tier`, `avg_fact_density`, `last_run`.

**Schema:** Migration `165_storyline_quality_integration.sql` adds `min_quality_tier`, `quality_metrics` to storylines and `suggest_only` to `automation_mode`.

---

## 2. Integration Points for Article→Storyline Flow

**Intended behavior:**

| Source | Action | Backend | Frontend |
|--------|--------|---------|----------|
| **Report / Briefing** | Each article card: "→ Storyline" | Use existing `POST /api/{domain}/storylines/{id}/articles/{article_id}` and `POST /api/{domain}/storylines` (create). | Add button; reuse or mirror ArticleReader "Add to Storyline" modal (choose existing or create new). |
| **Event detail** | "Create storyline from event" | New or extended: create storyline, add event’s articles that meet quality threshold, set automation from event entities/keywords, link event ↔ storyline. | Button on event detail page. |
| **Entity profile** | "Track this entity’s story" | Create storyline with entity name + related entities, set `min_quality_tier = 2`. | Button on entity profile. |
| **Intelligence analysis** | "Save as storyline" | Create storyline, attach analysis as initial `editorial_document`, link source articles. | Button on analysis result. |

**Done:** Backend supports quality filtering and living-by-default; storylines can be created and articles added via existing APIs.  
**To do:** Report/Briefing article card "→ Storyline" button and modal; Event/Entity/Intelligence actions and any new backend endpoints.

---

## 3. Make Storylines "Living" by Default ✅

**Implemented:**

- **On create** (in `api/domains/storyline_management/services/storyline_service.py`):
  - `automation_enabled = true`
  - `automation_mode = 'suggest_only'` (suggestions only, no auto-add).
  - `automation_frequency_hours = 6`
  - `automation_settings.min_quality_tier = 2`
  - If initial articles exist: `search_keywords` and `search_entities` derived from titles and `article_entities`.
- **Evolution signals (UI):**
  - Backend exposes `quality_metrics` (e.g. `last_run`, `filter_stats`, `articles_passed`) and `last_automation_run`.
  - **To do:** Badge "N new suggestions", last updated timestamp, "Live" indicator, suggestion queue UX (one-click approve/reject, "Why suggested", preview).

---

## 4. Quality-Driven Editorial Enrichment

**Not yet implemented.** Planned:

- When generating `editorial_document`: prioritize by article quality tier (lead from Tier 1; core narrative Tier 1–2; supporting Tier 3; ignore Tier 4).
- Fact-check integration: pull verified claims, highlight contradictions, source reliability.
- Evolution over time: track narrative changes, fact corrections, "what’s new since last view."

---

## 5. Cross-System Storyline Integration

**Planned:**

- **Events:** Events spawn or link to storylines; storylines can identify emerging events; shared quality settings.
- **Entity dossiers:** Entity profiles show related storylines; storylines contribute to entity positions; cross-links in both UIs.
- **Narrative threads:** Threads spanning storylines; suggest merges; meta-storylines.

---

## 6. Quality Monitoring Dashboard

**Planned:** Per-storyline and system-wide quality metrics (e.g. average article quality, tier distribution, clickbait rejection rate, fact density trend, source diversity). Backend already stores `quality_metrics` per storyline; dashboard UI and system-wide aggregates still to do.

---

## 7. Smart Defaults and Templates

**Planned:** Storyline templates (e.g. Breaking News, Investigation, Entity Tracking, Topic Monitoring) with different automation frequency, quality thresholds, and options (e.g. require named sources for Investigation). Can be implemented as presets in `automation_settings` and optional `storyline_type` or template selector in the UI.

---

## Implementation Summary

| Item | Status |
|------|--------|
| Migration 165 (min_quality_tier, quality_metrics, suggest_only) | ✅ |
| Quality gates in discovery (tier, clickbait, fact_density) | ✅ |
| final_score = 0.7*relevance + 0.3*quality | ✅ |
| quality_metrics and filter_stats persisted | ✅ |
| Living-by-default on create (automation on, suggest_only, 6h, min_tier 2) | ✅ |
| Extract keywords/entities from initial articles | ✅ |
| Report/Briefing "→ Storyline" button + modal | Pending |
| Event / Entity / Intelligence integration | Pending |
| Editorial pipeline quality weighting | Pending |
| Quality dashboard | Pending |
| Templates | Pending |
