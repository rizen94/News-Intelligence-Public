# Data Flow Architecture

How content flows from RSS ingestion through intelligence extraction to editorial output. Every step must preserve and enrich content, never reduce it to counts.

See [CORE_ARCHITECTURE_PRINCIPLES.md](_archive/retired_root_docs_2026_03/CORE_ARCHITECTURE_PRINCIPLES.md) for the principles behind this design (archived).

**Related:** [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) (where services live) · [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) · [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md) (when each automation phase runs) · stakeholder overview (archived): [_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md](_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md)

---

## The Intelligence Cascade

```
RSS Sources / External APIs
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1: INGESTION                                             │
│  rss_collector.py → {domain}.articles                          │
│  Fields populated: title, content, url, source_domain,         │
│                    published_at, excerpt                        │
│                                                                 │
│  ⚠️  WARNING: If content is empty here, ALL downstream         │
│     intelligence is lost. RSS feed may provide only title+link. │
│     Full-text fetch is critical.                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2: ML PROCESSING                                        │
│  ml_pipeline.py → articles.ml_data (JSONB)                     │
│  Extracts from content:                                        │
│    • summary (LLM-generated article summary)                   │
│    • key_points (structured key takeaways)                     │
│    • sentiment (sentiment analysis)                            │
│    • argument_analysis (argument structure)                    │
│    • quality_score (content quality assessment)                │
│                                                                 │
│  Also populates: articles.quality_score, articles.summary,     │
│                  articles.sentiment_label                       │
│                                                                 │
│  ⚠️  WARNING: ml_data must MERGE with existing data, never     │
│     overwrite. Multiple pipeline runs must accumulate.          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3: ENTITY & TOPIC EXTRACTION                            │
│  article_entity_extraction_service.py                          │
│    → article_entities (people, orgs, locations)                │
│    → article_extracted_dates, article_keywords                 │
│    → articles.entities (JSONB)                                 │
│  topic_clustering                                              │
│    → {domain}.topic_clusters, article_topic_clusters           │
│    → articles.topics, articles.categories (JSONB)              │
│                                                                 │
│  ⚠️  WARNING: Entity extraction must use article content,      │
│     not just titles. Title-only extraction misses most entities.│
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 4: CONTEXT CREATION                                     │
│  context_processor_service.py (context_sync phase)             │
│    → intelligence.contexts (canonical content units)           │
│    → intelligence.article_to_context (links back to articles)  │
│                                                                 │
│  Contexts are the bridge between domain articles and           │
│  cross-domain intelligence. Each context preserves:            │
│    • title, content, raw_content from source article           │
│    • domain_key, metadata                                      │
│                                                                 │
│  ⚠️  WARNING: If article content is empty, the context is      │
│     empty. All downstream extraction (claims, events) fails.   │
└────────────────────────┬────────────────────────────────────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────────────┐
│ STAGE 5a:    │ │ STAGE 5b:    │ │ STAGE 5c:            │
│ CLAIMS       │ │ EVENTS       │ │ ENTITY PROFILES      │
│              │ │              │ │                      │
│ claim_       │ │ event_       │ │ entity_profile_      │
│ extraction_  │ │ tracking_    │ │ builder_service.py   │
│ service.py   │ │ service.py   │ │                      │
│              │ │              │ │   → entity_profiles   │
│ → extracted_ │ │ → tracked_   │ │     .sections        │
│   claims     │ │   events     │ │     .relationships_  │
│ (subject,    │ │ → event_     │ │      summary         │
│  predicate,  │ │   chronicles │ │                      │
│  object)     │ │ (develop-    │ │ ⚠️  sections is the  │
│              │ │  ments,      │ │ entity dossier.      │
│ ⚠️  Claims   │ │  analysis,   │ │ Must be populated    │
│ must ref     │ │  predictions)│ │ from context content │
│ source       │ │              │ │ not just entity name │
│ context      │ │ ⚠️  Events   │ │                      │
│              │ │ group        │ └──────────────────────┘
│              │ │ contexts;    │
│              │ │ chronicles   │
│              │ │ ACCUMULATE   │
└──────────────┘ └──────┬───────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 6: STORYLINE MANAGEMENT                                  │
│  domains/storyline_management/services/storyline_service.py,      │
│  storyline_automation_service.py                                 │
│    → {domain}.storylines (grouping of related articles)        │
│    → {domain}.storyline_articles (article-storyline links)     │
│                                                                 │
│  Storylines have:                                               │
│    • title, description, summary (basic metadata)              │
│    • key_entities, timeline_events, topic_clusters (JSONB)     │
│    • editorial_document (JSONB) — THE PRIMARY OUTPUT           │
│    • analysis_results (JSONB)                                  │
│                                                                 │
│  ⚠️  WARNING: editorial_document MUST be populated.            │
│     Currently empty in production. This is the gap that        │
│     makes briefings metrics-only instead of narrative.         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 7: EDITORIAL OUTPUT                                      │
│  products.py (briefings), synthesis endpoints, report page     │
│                                                                 │
│  Should draw from:                                              │
│    • storylines.editorial_document (storyline narratives)       │
│    • tracked_events.editorial_briefing (event briefings)       │
│    • entity_profiles.sections (entity dossiers)                │
│    • articles (headlines, summaries for key developments)      │
│                                                                 │
│  Currently draws from:                                          │
│    • Article counts and quality metrics                        │
│    • Key developments (headlines + storyline titles)            │
│    • Optional LLM lead paragraph                               │
│                                                                 │
│  ⚠️  WARNING: Until editorial_document and editorial_briefing  │
│     are populated by the pipeline, briefings will be thin.     │
│     The LLM lead is a bridge, not the solution.                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Content Preservation Points

At each stage, specific content must be preserved. If any point fails, downstream outputs degrade.

| Stage | Input | Must Preserve | Output Location | Failure Mode |
|-------|-------|--------------|----------------|-------------|
| 1. Ingestion | RSS feed item | Full article text | `articles.content` | Empty content → empty everything downstream |
| 2. ML Processing | `articles.content` | Summary, key points, sentiment | `articles.ml_data` | No ml_data → no intelligence in topic cloud |
| 3. Entity Extraction | `articles.content` | People, orgs, locations, keywords | `article_entities`, `articles.entities` | Missing entities → weak profiles |
| 4. Context Creation | `articles.content` + metadata | Content preserved as canonical unit | `intelligence.contexts.content` | Empty context → no claims or events extracted |
| 5a. Claim Extraction | `contexts.content` | Subject-predicate-object facts | `intelligence.extracted_claims` | No claims → no fact verification |
| 5b. Event Tracking | `contexts` (grouped) | Developments, analysis, predictions | `tracked_events` + `event_chronicles` | No events → no event briefings |
| 5c. Entity Profiles | `contexts` by entity | Sections, relationships | `entity_profiles.sections` | Empty sections → no entity dossiers |
| 6. Storylines | Articles + entities + events | Editorial narrative | `storylines.editorial_document` | Empty editorial_document → metrics-only briefings |
| 7. Editorial Output | Editorial documents + headlines | Narrative briefing | API response `content` field | No editorial docs → falls back to counts |

---

## The Content Loss Chain

When content is lost at any stage, everything downstream is affected:

```
If article.content is empty:
  → ml_data has nothing to summarize → empty
  → entities can't be extracted from title alone → sparse
  → context.content is empty → claim extraction finds nothing
  → event tracking has no developments to group → weak events
  → storyline editorial_document has nothing to synthesize → empty
  → briefing falls back to "23 articles processed" → useless
```

This is why Principle 1 ("Content is King") is first. Everything depends on it.

---

## Automation Pipeline Phases (Mapped to Stages)

| Phase | Pipeline Phase Name | Stage | What it does | Content requirement |
|-------|-------------------|-------|-------------|-------------------|
| 1 | `rss_processing` | 1 | Fetch RSS feeds → articles | Must fetch full text |
| 1 | `context_sync` | 4 | Articles → contexts | Needs article.content |
| 1 | `entity_profile_sync` | 5c | canonical → profiles | Needs context.content |
| 1 | `entity_profile_build` | 5c | Build profiles from contexts | Needs context.content |
| 2 | `claim_extraction` | 5a | Contexts → claims | Needs context.content |
| 2 | `event_tracking` | 5b | Contexts → events | Needs context.content |
| 2 | `event_coherence_review` | 5b | LLM review of events | Needs context.content |
| 3 | `ml_processing` | 2 | ML pipeline on articles | Needs article.content |
| 4 | `entity_extraction` | 3 | Extract entities | Needs article.content |
| 4 | `quality_scoring` | 2 | Quality assessment | Needs article.content |
| 5 | `topic_clustering` | 3 | Topic clustering | Needs ml_data |
| 7 | `storyline_processing` | 6 | Storyline summaries | Needs article summaries |
| 7 | `storyline_automation` | 6 | RAG discovery | Needs article content |
| 11 | `digest_generation` | 7 | Generate digests | Needs storyline data |
| — | **MISSING** | 6→7 | **editorial_document generation** | Needs article content + entities + events |
| — | **MISSING** | 5b→7 | **editorial_briefing generation** | Needs event chronicles |

The two MISSING phases are the critical gap: no automation phase currently populates `editorial_document` or `editorial_briefing`.

---

## Intelligence Cascade — Implementation Status

The following gaps have been **closed** (see `docs/CODE_AUDIT_REPORT.md` for full audit):

```
IMPLEMENTED (2026-03-06):
  1. editorial_document_service.py generates/refines storyline editorial_document
     using article content + ml_data + entities (not just titles)
  2. editorial_document_service.py generates/refines event editorial_briefing
     from chronicles with accumulated analysis
  3. Event creation populates editorial_briefing on INSERT (draft status)
  4. Event chronicles build on prior analysis instead of starting empty
  5. RSS collector captures content:encoded full article body
  6. Briefing endpoint: editorial ledes → headlines → storylines → events → metrics
  7. Optional LLM lead paragraph prepended to briefings
  8. All API endpoints return editorial_document/editorial_briefing fields
  9. RAG analysis writes to editorial_document (not just analysis_summary)
  10. Storyline/basic summary generation seeds editorial_document when empty
  11. Digest generation pulls editorial ledes into story_suggestions
  12. Entity extraction stores contextual excerpts alongside entity names
  13. Storyline tracker uses article content + ml_data (not just title word counting)
```

Remaining architectural goal: a centralized content synthesis service that aggregates
all intelligence phases into a unified context before editorial generation.
