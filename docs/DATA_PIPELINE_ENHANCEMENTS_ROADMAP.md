# Data Pipeline Enhancements — Roadmap

**Purpose:** Catalog missing pipeline components (feedback loops, cross-domain synthesis, source quality, real-time, relationships, predictive, enrichment, deduplication, intelligence products, anomaly detection) with proposed routes, schema, integration points, and implementation order. Use with [DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md](DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md).

**Status:** Proposed; implement incrementally. Where existing partial implementations exist, they are referenced.

---

## 1. Feedback loops and quality control

**Gap:** No structured feedback from downstream (claims, events, entity profiles) back to extraction and collection to improve quality over time.

### Proposed

| Item | Description |
|------|-------------|
| **claim_feedback** | Accept validation/correction on claims; feed into extraction pattern tuning. |
| **event_validation** | Accept validation/corrections on events; improve event detection. |
| **extraction_metrics** | Per-source (and per-phase) quality scores to guide collection and processing priorities. |

### Routes to add

```text
POST /api/quality/claim_feedback
  Body: { claim_id, accuracy_score, correction?, validated_by? }
  Effect: Persist validation; optionally update extraction patterns / confidence

POST /api/quality/event_validation
  Body: { event_id, validation_status, corrections? }
  Effect: Persist; feed into event_tracking / detection tuning

GET /api/quality/extraction_metrics
  Query: source?, phase?, since?
  Response: Per-source (and per-phase) quality scores, sample sizes
```

### Schema (intelligence)

```sql
-- claim_validations: feedback on extracted claims
CREATE TABLE IF NOT EXISTS intelligence.claim_validations (
    id SERIAL PRIMARY KEY,
    claim_id UUID NOT NULL,  -- references extracted_claims or equivalent
    validation_status TEXT NOT NULL,  -- 'accurate' | 'corrected' | 'rejected'
    accuracy_score FLOAT,
    corrected_text TEXT,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    validated_by TEXT
);

-- event_validations: feedback on tracked events
CREATE TABLE IF NOT EXISTS intelligence.event_validations (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL,
    validation_status TEXT NOT NULL,
    corrections JSONB,
    validated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Integration

- **Processing Governor:** When recommending phases, consider `extraction_metrics` (e.g. prefer sources with higher validated quality).
- **Claim / event services:** Read validations when scoring or filtering; optional retrain/tune step from validated data.

### Existing

- **IntelligenceAnalysisService** has quality assessment and anomaly detection; no persistent feedback tables or claim/event-specific validation APIs yet.

---

## 2. Cross-domain intelligence synthesis

**Gap:** Limited correlation of events/claims across politics, finance, science-tech; no unified timeline or meta-storylines.

### Proposed

| Item | Description |
|------|-------------|
| **CrossDomainCorrelator** | Periodic job (e.g. every 30 min) to find relationships across domains (shared entities, temporal overlap, thematic links). |
| **Unified event timeline** | Single view of events across domains with optional filters. |
| **Meta-storylines** | Storylines that span or correlate multiple domains. |

### Routes to add

```text
POST /api/intelligence/cross_domain_synthesis
  Body: { domains?: ["politics","finance"], time_window_days?: 7, correlation_threshold?: 0.8 }
  Response: { correlation_id, correlations: [...], meta_storylines?: [...] }

GET /api/intelligence/cross_domain_correlations
  Query: domain_1, domain_2, since, limit

GET /api/intelligence/unified_timeline
  Query: domains?, since?, limit
  Response: Chronological events across domains with domain_key, event_type, entity links
```

### Schema (intelligence)

```sql
CREATE TABLE IF NOT EXISTS intelligence.cross_domain_correlations (
    correlation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_1 TEXT NOT NULL,
    domain_2 TEXT NOT NULL,
    entity_profile_ids INT[],
    event_ids INT[],
    correlation_strength FLOAT,
    correlation_type TEXT,  -- 'entity_overlap' | 'temporal' | 'thematic'
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

### Integration

- **Automation Manager:** New phase `cross_domain_synthesis` (e.g. interval 30 min); calls CrossDomainCorrelator.
- **Orchestrator Coordinator:** Optional post-processing step after a cycle (e.g. run synthesis when collection + key phases have run).

### Existing

- **Chronological timeline / event services** are domain-aware; no cross-domain correlation table or API yet.

---

## 3. Source quality and reliability tracking

**Gap:** Collection does not adjust by source reputation (claim accuracy, exclusive/first-reporting, correction rates).

### Proposed

| Item | Description |
|------|-------------|
| **SourceReliabilityTracker** | Track per-source metrics: claim accuracy (from claim_feedback), exclusive/first-reporting, correction rate. |
| **Dynamic priority** | Collection Governor (or scheduler) uses source_reliability_scores to adjust fetch order or frequency. |
| **Source health** | Monitor source availability and freshness. |

### Schema (intelligence)

```sql
CREATE TABLE IF NOT EXISTS intelligence.source_reliability (
    source_name TEXT PRIMARY KEY,  -- feed name, domain+feed, or "rss:politics:feed_1"
    accuracy_score FLOAT,
    exclusive_stories_count INT DEFAULT 0,
    correction_rate FLOAT,
    last_collection_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);
```

### Routes to add

```text
GET /api/quality/source_rankings
  Query: domain?, limit
  Response: Ranked sources by reliability / accuracy

POST /api/quality/source_feedback
  Body: { source_name, metric: "accuracy"|"exclusive"|"correction", value }
  Effect: Update source_reliability
```

### Integration

- **Collection Governor:** Read `source_reliability` (or a cached view); use in `recommend_fetch` to prefer higher-reliability sources when intervals allow.
- **Orchestrator governance:** Optional `collection.source_priority_weights` or use scores as tie-breaker.

### Existing

- **Collection Governor** uses last_collection_times and intervals only; no source_reliability yet.

---

## 4. Real-time / streaming event detection

**Gap:** No dedicated path for high-velocity or breaking content (WebSocket feeds, urgent ingest) that bypasses batch cadence.

### Proposed

| Item | Description |
|------|-------------|
| **StreamingEventDetector** | Consume high-velocity sources; create contexts and run event detection with minimal delay. |
| **Urgent ingest API** | Accept “urgent” payloads that skip or prioritize queue. |
| **Bypass queue** | Optional path: urgent → context → event detection → alerts without waiting for scheduled phases. |

### Routes to add

```text
POST /api/realtime/process_urgent
  Body: { source: "streaming"|"webhook", payload: {...}, priority: "immediate", bypass_queue?: true }
  Response: { context_id?, event_ids?, alert_ids? }

GET /api/realtime/streaming_status
  Response: { active_streams, last_urgent_at, queue_depth? }
```

### Integration

- **Automation Manager:** Optional “urgent” queue consumed by a dedicated worker; or call event_tracking/event_extraction inline for urgent context.
- **Route:** Keep request time-bound (e.g. 30s) to avoid blocking.

### Existing

- No streaming or urgent path; all ingestion goes through RSS batch or API-triggered collect.

---

## 5. Relationship and network analysis

**Gap:** No dedicated relationship extraction from contexts or entity co-occurrence → network graph / influence analysis.

### Proposed

| Item | Description |
|------|-------------|
| **Relationship extraction** | From contexts: entity A ↔ entity B (relationship type, strength, temporal). |
| **Network graph** | Per-entity or global graph of entity_profiles and relationships. |
| **Influence analysis** | Centrality, influence propagation, or “who influences whom” from graph. |

### Routes to add

```text
POST /api/intelligence/extract_relationships
  Body: { context_ids?: [], domain?: "politics", limit?: 50 }
  Response: { extracted: N, relationship_ids: [...] }

GET /api/intelligence/network_graph/{entity_id}
  Query: depth?, relationship_types?
  Response: Subgraph around entity (nodes = entity_profiles, edges = relationships)

GET /api/intelligence/influence_analysis
  Query: entity_id?, domain?, limit
  Response: Ranked influence scores or key influencers
```

### Integration

- **Automation Manager:** New phase `relationship_extraction` (e.g. every 15 min); writes to `entity_relationships` or new `relationship_edges` table.
- **Existing:** `intelligence.entity_relationships` and entity_profiles exist; extend with extraction pipeline and graph API.

### Existing

- **Entity profiles and context_entity_mentions** support entity-centric views; **pattern_recognition** has network pattern type. No dedicated relationship extraction API or graph endpoint.

---

## 6. Predictive and trend analysis

**Gap:** No forward-looking pipeline (trend detection, predictions) fed by historical patterns or event sequences.

### Proposed

| Item | Description |
|------|-------------|
| **Trend detection** | From fact_change_log, story_update_queue, or event sequences: identify trends and leading indicators. |
| **Predictions** | Per-domain or per-entity: “likely next events” or “narrative direction” (with confidence). |
| **Learning Governor** | Already has pattern analysis; extend to predictive signals. |

### Routes to add

```text
POST /api/intelligence/trend_analysis
  Body: { domain?, time_window_days?, indicators?: [] }
  Response: { trends: [...], leading_indicators: [...] }

GET /api/intelligence/predictions/{domain}
  Query: entity_id?, horizon_days?
  Response: { predictions: [...], confidence, based_on: [...] }
```

### Integration

- **Processing Governor:** New decision factor “prediction_demand” or “trend_alerts” to prioritize phases that feed predictions.
- **Learning Governor:** Consume decision_history and performance_metrics; write to a `predictions` or `trend_signals` table for API exposure.

### Existing

- **Learning Governor** does pattern analysis and writes learned_patterns; **orchestrator** has `get_predictions()` (next source updates, placeholder). No trend_analysis or predictions API yet.

---

## 7. Data enrichment pipeline (beyond entity)

**Gap:** Entity enrichment exists (Wikipedia); no generic “enrich entity” / “verify claim” APIs or orchestration for external fact-check/enrichment.

### Proposed

| Item | Description |
|------|-------------|
| **Enrich entity** | Single-entity enrichment (Wikipedia/Wikidata, financial APIs, etc.) with optional priority. |
| **Verify claim** | Call-out to fact-check or external APIs; store verification result and confidence delta. |
| **EnrichmentOrchestrator** | Batch enrichment jobs with backpressure (already partially present in entity_enrichment). |

### Routes to add

```text
POST /api/enrichment/enrich_entity
  Body: { entity_profile_id, sources?: ["wikipedia","wikidata"], priority?: "high" }
  Response: { updated: true, sections_added?, facts_added? }

POST /api/enrichment/verify_claim
  Body: { claim_id, provider?: "internal"|"external" }
  Response: { status, confidence_delta?, verified_at }
```

### Integration

- **Entity enrichment service** already runs Wikipedia enrichment; expose single-entity and batch via these routes. **Claim verification** can write to `claim_validations` and optionally call external APIs later.

### Existing

- **Entity enrichment:** `entity_enrichment_service.run_enrichment_batch`, `POST /api/context_centric/run_entity_enrichment`. No `/api/enrichment/*` namespace or claim verification API.

---

## 8. Deduplication and consolidation (cross-stage)

**Gap:** Article-level deduplication exists; no cross-stage semantic dedupe (claims, events) or consolidation APIs.

### Proposed

| Item | Description |
|------|-------------|
| **Consolidate articles** | Fuzzy/semantic match across sources; merge duplicates with source attribution. |
| **Merge claims** | Semantic similarity → unified claim with multiple source_context_ids. |
| **Merge events** | Temporal + entity overlap → merged event with chronicles from all. |
| **DeduplicationService** | Run after collection or on-demand; maintain source attribution. |

### Routes to add

```text
POST /api/deduplication/consolidate_articles
  Body: { domain?, limit?, dry_run?: false }
  Response: { merged: N, clusters: [...] }

POST /api/deduplication/merge_claims
  Body: { claim_ids?: [], similarity_threshold?: 0.9 }
  Response: { merged: N, unified_claim_ids: [...] }
```

### Integration

- **Automation Manager:** Optional phase `claim_deduplication` or `event_merge` after claim_extraction / event_tracking.
- **Collection:** Existing article dedupe in RSS collector; consolidate_articles can run as a separate cleanup phase.

### Existing

- **Article deduplication:** `article_deduplication` routes, `DeduplicationManager` in `rss_collector`, `advanced_deduplication_service`. **Event deduplication:** `event_deduplication_service.deduplicate_recent`. No claim merge or consolidate_articles API.

---

## 9. Intelligence product generation

**Gap:** No standardized “products” (daily briefs, thematic reports, alert digests) exposed as subscribable APIs.

### Proposed

| Item | Description |
|------|-------------|
| **Daily brief** | Storylines + top events + anomalies; generated on schedule or on-demand. |
| **Thematic report** | Topic or domain report over a time window. |
| **Alert digest** | Watchlist alerts + event alerts bundled. |
| **IntelligenceProductService** | Generate, store, and serve products; optional subscription by type. |

### Routes to add

```text
POST /api/products/generate_brief
  Body: { date?, domain?, include_anomalies?: true }
  Response: { brief_id, sections, generated_at }

POST /api/products/create_report
  Body: { report_type: "thematic"|"domain", title, time_window_days, params? }
  Response: { report_id, status }

GET /api/products/daily_brief
  Query: date?
  Response: Latest or specified daily brief

GET /api/products/alert_digest
  Query: since?
  Response: Alert digest for watchlist + events

GET /api/products/subscribe/{product_type}
  Query: format? (e.g. json, email placeholder)
  Response: Subscription info or delivery config
```

### Integration

- **Automation Manager:** New phase `intelligence_products` (e.g. every 6 h) to generate daily_brief and optional report.
- **Watchlist/events:** Alert digest can aggregate from existing watchlist_alerts and event alerts.

### Existing

- **DailyBriefingService** (`modules/ml/daily_briefing_service.py`) generates daily briefings; **digest_generation** phase exists. No unified `/api/products/*` or subscribe API.

---

## 10. Anomaly detection in data flows

**Gap:** Anomaly detection exists for analysis (intelligence_analysis_service, advanced_monitoring_service); no pipeline-level anomaly API or “investigate” workflow.

### Proposed

| Item | Description |
|------|-------------|
| **Pipeline anomalies** | Collection volume, claim rate, narrative shift, unusual entity activity. |
| **AnomalyDetector** | Monitor metrics (per source, per domain, per phase); deviation from baseline → alert. |
| **Investigate** | Endpoint to attach notes or trigger follow-up (e.g. run extraction on anomaly window). |

### Routes to add

```text
GET /api/monitoring/anomalies
  Query: since?, type?, domain?
  Response: { anomalies: [...], baselines: {...} }

POST /api/monitoring/investigate_anomaly
  Body: { anomaly_id, action?: "dismiss"|"investigate", note?, run_analysis?: true }
  Response: { status, analysis_job_id? }
```

### Integration

- **Orchestrator Coordinator:** Optional “anomaly check” in loop (e.g. call AnomalyDetector; if critical, log or pause collection).
- **Processing Governor:** New factor “anomaly_flags” to prioritize phases that explain or drill into anomalies.

### Existing

- **IntelligenceAnalysisService** has anomaly detection (AnomalyReport, sudden_spike, etc.). **AdvancedMonitoringService** has _anomaly_detection_task for system metrics. No `/api/monitoring/anomalies` or investigate endpoint.

---

## 11. Recommended integration points (summary)

### Orchestrator Coordinator (main loop)

- **Before collection:** Optionally read `source_reliability` and adjust which source to fetch (or leave as-is and only use for tie-break).
- **After processing:** Optionally run cross-domain synthesis or anomaly check.
- **State:** Add optional `last_anomaly_check`, `last_cross_domain_synthesis` if those run from coordinator.

### Automation Manager (new phases)

| Phase | Interval (min) | Purpose |
|-------|----------------|---------|
| relationship_extraction | 15 | Extract entity relationships from contexts; update graph |
| cross_domain_synthesis | 30 | Run CrossDomainCorrelator; persist correlations |
| source_quality_update | 60 | Recompute source_reliability from claim_validations / feedback |
| intelligence_products | 360 (6 h) | Generate daily brief, optional thematic report, alert digest |

Add to `schedules` in `automation_manager.py` and implement `_execute_*` stubs that call the new services.

### Processing Governor

- **New decision factors (optional):** `source_reliability_scores` (prefer processing from higher-quality sources), `cross_domain_opportunities` (prefer synthesis when correlations pending), `anomaly_flags` (prefer phases that explain anomalies), `user_demand_signals` (from watchlist or subscriptions).

### New API namespaces

- `/api/quality/*` — claim_feedback, event_validation, extraction_metrics, source_rankings, source_feedback.
- `/api/intelligence/*` — cross_domain_synthesis, cross_domain_correlations, unified_timeline, extract_relationships, network_graph, influence_analysis, trend_analysis, predictions.
- `/api/realtime/*` — process_urgent, streaming_status.
- `/api/enrichment/*` — enrich_entity, verify_claim.
- `/api/deduplication/*` — consolidate_articles, merge_claims (event merge can live here or under intelligence).
- `/api/products/*` — generate_brief, create_report, daily_brief, alert_digest, subscribe.
- `/api/monitoring/anomalies`, `/api/monitoring/investigate_anomaly` (under existing system_monitoring).

---

## 12. Schema additions (consolidated)

```sql
-- intelligence schema

-- Feedback and quality
CREATE TABLE IF NOT EXISTS intelligence.claim_validations (
    id SERIAL PRIMARY KEY,
    claim_id UUID NOT NULL,
    validation_status TEXT NOT NULL,
    accuracy_score FLOAT,
    corrected_text TEXT,
    validated_at TIMESTAMPTZ DEFAULT NOW(),
    validated_by TEXT
);

CREATE TABLE IF NOT EXISTS intelligence.event_validations (
    id SERIAL PRIMARY KEY,
    event_id INT NOT NULL,
    validation_status TEXT NOT NULL,
    corrections JSONB,
    validated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS intelligence.source_reliability (
    source_name TEXT PRIMARY KEY,
    accuracy_score FLOAT,
    exclusive_stories_count INT DEFAULT 0,
    correction_rate FLOAT,
    last_collection_at TIMESTAMPTZ,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Cross-domain
CREATE TABLE IF NOT EXISTS intelligence.cross_domain_correlations (
    correlation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_1 TEXT NOT NULL,
    domain_2 TEXT NOT NULL,
    entity_profile_ids INT[],
    event_ids INT[],
    correlation_strength FLOAT,
    correlation_type TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Optional: intelligence_products (briefs, reports)
-- Optional: anomaly_investigations (anomaly_id, action, note, run_analysis)
```

---

## 13. Implementation priority

| Priority | Component | Rationale |
|----------|-----------|-----------|
| P0 | Feedback tables + claim_feedback / event_validation APIs | Enables quality loop and source_reliability over time. |
| P0 | source_reliability table + source_rankings API | Enables Collection Governor to use quality. |
| P1 | GET /api/quality/extraction_metrics | Surfaces quality for UI and governor. |
| P1 | Cross-domain correlations table + synthesis phase + GET/POST cross_domain APIs | High value for intelligence. |
| P1 | GET /api/intelligence/unified_timeline | Simple aggregation over existing events. |
| P2 | relationship_extraction phase + extract_relationships + network_graph | Builds on entity_profiles. |
| P2 | POST /api/realtime/process_urgent | Unblocks breaking-news use cases. |
| P2 | /api/products/* (generate_brief, daily_brief, alert_digest) | Unify DailyBriefingService and digest behind one API. |
| P2 | GET /api/monitoring/anomalies + investigate | Expose existing anomaly logic. |
| P3 | trend_analysis, predictions APIs | Depends on Learning Governor and possibly new models. |
| P3 | consolidate_articles, merge_claims | Dedupe beyond articles. |
| P3 | enrich_entity / verify_claim under /api/enrichment | Clarify enrichment API surface. |

---

## 14. References

- [DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md](DATA_PIPELINES_AND_ORCHESTRATION_ROADMAP.md) — Current orchestrators, governors, and API stack.
- [BATCH_PROCESSING_DESIGN.md](BATCH_PROCESSING_DESIGN.md) — Production timings and backpressure.
- [CONTEXT_CENTRIC_UPGRADE_PLAN.md](CONTEXT_CENTRIC_UPGRADE_PLAN.md) — Context and entity model.
- Existing: `intelligence_analysis_service.py` (anomaly, quality), `daily_briefing_service.py`, `event_deduplication_service.py`, `entity_enrichment_service.py`, `article_deduplication` routes.

This roadmap closes the main gaps: feedback loops, cross-domain synthesis, source quality, real-time path, relationship/predictive/product APIs, and anomaly investigation, with a clear place for each in the pipeline and API stack.
