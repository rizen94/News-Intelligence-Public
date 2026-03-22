# Content Quality Standards — Clickbait & Sensationalism Management

> **Purpose:** Classify and filter content so the system prioritizes factual, substantive reporting over clickbait and sensationalism.  
> **Last updated:** 2026-03-06.

---

## 1. Content Quality Tiers

We use a **4-tier** classification. Scores are 0–10 internally; tiers map as below.

| Tier | Name | Score | Use in product |
|------|------|--------|------------------|
| **1** | Intelligence-Grade | 8–10 | Lead briefings, events, storylines; highest trust. |
| **2** | Standard Reporting | 6–7 | Briefings, storylines; default for wire/major outlets. |
| **3** | Aggregated/Commentary | 4–5 | Can appear in lists; not preferred for lead. |
| **4** | Low-Value/Clickbait | 0–3 | Demoted or excluded from briefings and storyline discovery. |

### Tier 1: Intelligence-Grade (Score 8–10)

- Original reporting with **named sources**
- Data-driven analysis with **citations**
- Investigative journalism with documentation
- Expert commentary with credentials
- Government/institutional reports

**Characteristics:** High fact density, low emotional language, specific details, verifiable claims.

### Tier 2: Standard Reporting (Score 6–7)

- Wire service reports (AP, Reuters, Bloomberg)
- Major newspaper coverage with bylines
- Trade publication analysis

**Characteristics:** Factual but may lack depth, some analysis, reliable but not comprehensive.

### Tier 3: Aggregated/Commentary (Score 4–5)

- Opinion pieces with factual basis
- Aggregated news with attribution
- Blog posts from recognized experts

**Characteristics:** Mix of fact and interpretation; requires verification.

### Tier 4: Low-Value/Clickbait (Score 0–3)

- Sensational headlines with minimal content
- Emotional manipulation without facts
- Unattributed claims or rumors
- List-based filler content

**Characteristics:** High emotion, low facts, vague sources, inflammatory language.

---

## 2. Clickbait Indicators (Red Flags)

### Headline patterns

- **Excessive capitalization:** "BREAKING:", "SHOCKING:", "DESTROYED"
- **Curiosity gaps:** "You Won't Believe...", "What Happened Next..."
- **Emotional triggers:** "Outrage", "Furious", "Slams", "Blasts"
- **Vague pronouns:** "This One Thing...", "They Don't Want You to Know"
- **Hyperbolic claims:** "Changes Everything", "Game Changer", "Revolutionary"

### Content patterns

- Short articles (&lt;200 words) with heavy ad placement
- No named sources or citations
- Emotional language density &gt;30%
- Fact-to-opinion ratio &lt;0.3
- Missing key details (who, what, when, where, why)
- Slideshow/gallery format for text content

### Source reliability (reference)

- **Tier 1:** Wire services, major newspapers, academic journals (0.9–1.0)
- **Tier 2:** Regional papers, trade publications, think tanks (0.7–0.8)
- **Tier 3:** Blogs, partisan outlets, tabloids (0.4–0.6)
- **Tier 4:** Anonymous blogs, content farms, known misleading sources (0.0–0.3)

---

## 3. Implementation

- **Detection:** `api/services/content_quality_service.py` — `ContentQualityService.analyze_content_quality()` produces `quality_score`, `quality_tier`, and sub-scores (clickbait, fact_density, source_quality, etc.).
- **Storage:** Per-article fields (see migration 164): `quality_tier`, `quality_scores` (JSONB), `clickbait_probability`, `fact_density`, `source_reliability`, `quality_flags`. Optional: `public.content_quality_metrics` for source-level aggregates.
- **RSS ingest:** Existing `is_clickbait_title()` and `calculate_article_quality_score()` in `api/collectors/rss_collector.py` remain the first filter; content quality service can run later in the pipeline for stored articles.
- **Briefings:** Key developments and briefing feed prefer `quality_tier <= 2` when available; low-tier items are demoted or excluded.
- **Config:** `api/config/content_quality_config.py` (or YAML) defines thresholds: `min_tier_for_briefings`, `min_tier_for_storylines`, `auto_reject_clickbait_threshold`, etc.

---

## 4. Configuration (thresholds)

| Setting | Default | Meaning |
|---------|---------|--------|
| `min_tier_for_briefings` | 2 | Only Tier 1–2 in briefing lead/key developments. |
| `min_tier_for_storylines` | 3 | Tier 3+ eligible for storyline discovery. |
| `min_tier_for_events` | 2 | Tier 2+ for event extraction. |
| `auto_reject_clickbait_threshold` | 0.8 | Clickbait score ≥ this → treat as Tier 4. |
| `min_word_count_for_analysis` | 200 | Below this → quality penalty. |
| `emotion_word_density_threshold` | 0.3 | Above → emotional-manipulation penalty. |

---

## 5. LLM-assisted assessment (optional)

When the LLM is available, the service can use a structured prompt to refine:

- Fact count vs vague statements  
- Named vs anonymous sources  
- Emotional phrases  
- Missing story elements (who/what/when/where/why)  
- Primary value: reporting | analysis | opinion | entertainment  

The prompt and expected JSON shape are documented in `ContentQualityService` and in `docs/LLM_PROMPTS.md` (if present). Rule-based scoring runs without LLM.

---

## 6. Monitoring

- **System monitoring** can expose: daily quality distribution (Tier 1–4), sources ranked by average quality, clickbait rate by source, quality trends over time.
- **Source reputation:** `intelligence.source_reliability` (migration 155) and/or `content_quality_metrics` can drive auto-downgrade of consistently low-quality sources.

---

## 7. Implementation priority

1. **Week 1:** Content quality service + clickbait detection; migration 164; briefing ordering by quality_tier.
2. **Week 2:** Backfill quality_tier for existing articles; source reputation (content_quality_metrics).
3. **Week 3:** Frontend quality indicators; quality monitoring dashboard.

**Backfill:** Run `ContentQualityService.analyze_content_quality()` then `update_article_quality_in_db()` per article (script or automation). **ML pipeline:** Optional quality-assessment phase after ingestion to set quality_tier on new articles.

---

## 8. Related docs

- **Briefing filters / user feedback:** `docs/BRIEFING_FILTERS_AND_FEEDBACK.md`
- **RSS collection and filters:** `api/collectors/rss_collector.py` (`is_clickbait_title`, `is_excluded_content`, `calculate_article_quality_score`)
- **Coding style:** `docs/CODING_STYLE_GUIDE.md`
