# Database Data Quality Audit — June 2026

**Database:** `news_intel` on Widow (`:5432` / PgBouncer `:6432`)  
**Domains audited:** `politics`, `finance` (pipeline-active)  
**Repair run:** 2026-06-19 on Widow production

---

## Executive summary

Core relational data (articles, storylines, topic assignments, storyline links) is **sound**. Denormalized counter columns were **systemically broken**: never written (`word_count`, `topics.article_count`, storyline derived metrics) or corrupted by mega-storyline consolidation summing stale `article_count` values.

**Remediation shipped:**

- Code: pipeline writers, API subquery counts, consolidation fix ([`api/shared/storyline_article_counts.py`](../api/shared/storyline_article_counts.py), [`api/shared/article_text_metrics.py`](../api/shared/article_text_metrics.py))
- Operator scripts: [`api/scripts/repair_duplicate_mega_storylines.py`](../api/scripts/repair_duplicate_mega_storylines.py), [`api/scripts/repair_denormalized_metrics.py`](../api/scripts/repair_denormalized_metrics.py)
- Widow repair applied 2026-06-19 (see [Repair results](#repair-results-2026-06-19))

**Overall reliability after repair:** ~7/10 for analytics queries; use JOIN-derived counts when in doubt.

---

## Reliability matrix

| Table / column | Trust level | Authoritative source | Notes |
|----------------|-------------|----------------------|-------|
| `articles.title`, `content`, `url` | High | Row itself | ~26k politics articles with content >100 chars |
| `articles.word_count` | High (post-repair) | `content` word split | Was 100% zero; now backfilled + wired on RSS/enrichment |
| `articles.quality_score` | Medium–High | Pipeline scoring | Avg ~0.42 politics; usable for filters |
| `articles.entities` JSONB | Partial | `article_entities` table | ~47% empty on politics; prefer normalized entity tables |
| `storyline_articles` | High | Join table | Ground truth for storyline membership |
| `storylines.article_count` / `total_articles` | High (post-repair) | `COUNT(storyline_articles)` | API list/detail uses subquery; column synced on writes |
| `storylines.total_entities` | Medium | `story_entity_index` | Backfilled 202 storylines politics; synced on link/unlink |
| `storylines.time_span_days` | Medium | Min/max `published_at` of linked articles | Backfilled with repair script |
| `storylines.completeness_score`, `coherence_score` | Low | On-demand only | No batch writer; `assess_storyline_quality` writes other scores |
| `topics` names, keywords | High | Row itself | Legacy topic table; 6,235 politics rows |
| `topics.article_count` | High (post-repair) | `article_topic_assignments` | Was all zero; topic_management API already used JOIN counts |
| `topic_clusters.article_count` | High | `article_topic_clusters` | Primary clustering path; was already healthy |
| `article_topic_assignments` | High | Join table | 6,690 politics assignments |
| `entity_canonical` | High | Row itself | ~10k politics entities |

### topics vs topic_clusters

Two parallel topic systems exist:

| | `topics` + `article_topic_assignments` | `topic_clusters` + `article_topic_clusters` |
|---|--------------------------------------|---------------------------------------------|
| Used by | Topic management UI, `topic_clustering_service` | Advanced extractor, clustering dashboards |
| `article_count` before repair | All zero (column) | ~90k rows with count > 0 |
| After repair | Column synced from assignments | Unchanged (already correct) |

Prefer **`topic_clusters`** for clustering analytics; use **`topics`** for managed topic CRUD.

---

## Root causes

1. **`word_count` never persisted** — computed in `article_processing_service` in memory only; RSS INSERT and enrichment UPDATE omitted the column.
2. **`topics.article_count` never updated** — assignments wrote to `article_topic_assignments` but not the denormalized column (unlike `topic_clusters`).
3. **Storyline count inflation** — mega-storyline consolidation summed stale `article_count` columns instead of `COUNT(DISTINCT storyline_articles)`.
4. **Derived storyline fields unwired** — `total_entities`, `time_span_days` had no pipeline writers until June 2026 repair.

---

## Safe SQL patterns

### Storyline article counts (always works)

```sql
SELECT s.id, s.title, s.status,
       COUNT(sa.article_id) AS real_article_count
FROM politics.storylines s
LEFT JOIN politics.storyline_articles sa ON sa.storyline_id = s.id
WHERE s.merged_into_id IS NULL AND s.status = 'active'
GROUP BY s.id, s.title, s.status
ORDER BY real_article_count DESC
LIMIT 20;
```

### Topic counts (prefer JOIN over column for ad-hoc queries)

```sql
SELECT t.id, t.name, COUNT(DISTINCT ata.article_id) AS real_count
FROM politics.topics t
LEFT JOIN politics.article_topic_assignments ata ON ata.topic_id = t.id
GROUP BY t.id, t.name
ORDER BY real_count DESC;
```

### Word count filter

```sql
-- After backfill, column is reliable; fallback for empty content:
SELECT id, title, word_count
FROM politics.articles
WHERE word_count > 500;
```

### Avoid (pre-repair; column may drift again if repair not re-run)

```sql
-- Fragile if denormalized columns stale:
SELECT * FROM politics.storylines WHERE article_count > 100;
SELECT * FROM politics.articles WHERE word_count > 500;  -- was always empty before repair
```

---

## Operator runbook

Run from **`/opt/news-intelligence/api`** on Widow with `.env` loaded.

### 1. Storyline mega repair + count reconcile

```bash
set -a && . /opt/news-intelligence/.env && set +a
cd /opt/news-intelligence/api

# Dry-run
PYTHONPATH=. python3 scripts/repair_duplicate_mega_storylines.py \
  --domain politics --domain finance \
  --reconcile-all-counts --refresh-counts --dry-run

# Apply
PYTHONPATH=. python3 scripts/repair_duplicate_mega_storylines.py \
  --domain politics --domain finance \
  --reconcile-all-counts --refresh-counts
```

### 2. Denormalized metrics (word_count, topics, derived storyline fields)

```bash
PYTHONPATH=. python3 scripts/repair_denormalized_metrics.py \
  --domain politics --domain finance --all --dry-run

PYTHONPATH=. python3 scripts/repair_denormalized_metrics.py \
  --domain politics --domain finance --all
```

Flags: `--word-count`, `--topics`, `--storyline-counts`, `--storyline-derived`, or `--all`.

### 3. Purge folded archived storylines (hard delete)

Deletes rows with `merged_into_id IS NOT NULL` after moving articles to the canonical storyline and reparenting children.

```bash
PYTHONPATH=. python3 scripts/purge_merged_archived_storylines.py --dry-run
PYTHONPATH=. python3 scripts/purge_merged_archived_storylines.py --domain politics --domain finance
```

Optional: `--ongoing-megas-only` limits delete to `Ongoing: *` titles.

**Applied 2026-06-19:** politics 340 deleted, finance 183 deleted; 0 merged rows remain.

### 4. Verification

```bash
PYTHONPATH=. python3 scripts/verify_database_health.py
PYTHONPATH=. python3 scripts/verify_database_health.py --json
```

```sql
-- Expect 0 mismatches
SELECT COUNT(*) FROM politics.storylines s
WHERE merged_into_id IS NULL
  AND article_count IS DISTINCT FROM (
    SELECT COUNT(*)::int FROM politics.storyline_articles sa WHERE sa.storyline_id = s.id
  );

-- Spot-check word counts
SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY word_count)
FROM politics.articles WHERE length(content) > 500;
```

---

## Repair results (2026-06-19)

| Step | politics | finance |
|------|----------|---------|
| Storylines reconciled | 314 total (both domains) | (combined run) |
| Mega counts refreshed | 65 | — |
| `articles.word_count` updated | 27,852 | 23,762 |
| `topics.article_count` updated | 6,134 | 4,747 |
| Storyline derived (`total_entities`, `time_span_days`) | 202 | 52 |

**Post-repair checks:**

| Check | Result |
|-------|--------|
| Politics storyline count mismatches (active only) | **0** after first repair |
| Politics storyline count mismatches (all rows) | **0** after full reconcile (includes archived/merged megas) |
| Politics max `article_count` on active storylines | **62** |
| Politics max `article_count` all rows (incl. archived) | **62** (was billions on folded `Ongoing:*` megas) |

**Note:** The first repair only reconciled `merged_into_id IS NULL` rows. Inflated billions lived on **archived folded megas** (`merged_into_id IS NOT NULL`, 0 `storyline_articles` links). Re-run with updated `reconcile_all_storyline_counts(include_merged=True)` or full-table UPDATE.

---

## Schema matrix (queryable vs legacy)

| Schema | Role | Query for live data? |
|--------|------|----------------------|
| `politics`, `finance` | Domain silos (articles, storylines, topics, entities) | **Yes** — primary API/pipeline |
| `science_tech` | Registered domain; pipeline inactive until enabled | Only if domain activated |
| `intelligence` | Context-centric hub (contexts, claims, facts, relationships) | **Yes** |
| `investigation` | FtM resolver / NRI spine (merged from `nri`) | **Yes** for investigation routes |
| `public` | Pre-silo legacy tables | **No** — mostly empty; use domain silos |

Never use `public.articles` for backlog or analytics. Automation history (`public.automation_run_history`, `automation_state`) remains live.

---

## Empty-table register (June 2026)

| Table / area | Rows (est.) | Wired? | Action |
|--------------|-------------|--------|--------|
| `intelligence.entity_relationships` | ~56M (pre-dedupe) | Yes — organizer upsert | Dedupe + migration 241; cap via `ENTITY_RELATIONSHIPS_MAX_ROWS` |
| `intelligence.arc_definitions` | 0 | YAML only | Skip arc/matview phases until populated |
| `intelligence.embedding_chunks` | 0 | Worker exists | Skip bulk embed unless `EMBEDDINGS_WORKER_FORCE_BACKFILL=true` |
| `intelligence.pattern_discoveries` | low | Writer exists | `pattern_recognition: false` in context_centric until baseline |
| `public.chronological_events` | 0 | Legacy | Not required; event extraction uses domain articles |
| 33 empty `intelligence.*` | 0 | Mixed | See [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md) |

---

## Pipeline integrity operator runbook

Run from **`/opt/news-intelligence/api`** on Widow with `.env` loaded.

### 5. Entity relationships dedupe + unique index

**Order:** deploy code → dedupe → migration 241 → restart API.

```bash
set -a && . /opt/news-intelligence/.env && set +a
cd /opt/news-intelligence/api

PYTHONPATH=. python3 scripts/dedupe_entity_relationships.py --dry-run
# Preferred for 10M+ rows: one-pass DISTINCT ON + table swap
PYTHONPATH=. python3 scripts/dedupe_entity_relationships.py --rebuild-table
# Or batched deletes:
PYTHONPATH=. python3 scripts/dedupe_entity_relationships.py --batch-size 50000

# Apply migration (via migration runner or psql)
PYTHONPATH=. python3 -c "
from shared.migration_sql_runner import apply_pending_migrations
apply_pending_migrations()
"
```

Upsert writers: [`api/shared/entity_relationships_store.py`](../api/shared/entity_relationships_store.py). Organizer skips extraction when row estimate ≥ `ENTITY_RELATIONSHIPS_MAX_ROWS` (default 5M). Contexts record `metadata.pipeline.relationship_extraction.last_pass_at` after each scan so the organizer does not re-process the same context (disable via `RELATIONSHIP_EXTRACTION_BACKLOG_USE_PASS_MARKER=false`).

Drop archived dedupe table after verification:

```bash
psql -h 127.0.0.1 -p 6432 -U newsapp -d news_intel -c "DROP TABLE IF EXISTS intelligence.entity_relationships_pre_dedup;"
```

### 6. Context sync catchup

```bash
PYTHONPATH=. python3 scripts/catchup_context_sync.py --dry-run
PYTHONPATH=. python3 scripts/catchup_context_sync.py --domain politics --domain finance --batch-size 500
```

### 7. Claims → facts catchup

```bash
PYTHONPATH=. python3 scripts/catchup_entity_profiles_claim_resolution.py --promote-limit 5000
```

Tune env: `CLAIMS_TO_FACTS_BATCH_LIMIT`, nightly sequential drain caps. Monitor `data_quality.claims_to_facts_ratio` on `/api/system_monitoring/backlog_status`.

### 8. Empty storyline GC (optional)

```bash
PYTHONPATH=. python3 scripts/prune_empty_storylines.py --dry-run --min-age-days 30
PYTHONPATH=. python3 scripts/prune_empty_storylines.py --domain politics --domain finance
```

---

## Code references

| Concern | Module |
|---------|--------|
| Storyline count helpers | [`api/shared/storyline_article_counts.py`](../api/shared/storyline_article_counts.py) |
| Word count helper | [`api/shared/article_text_metrics.py`](../api/shared/article_text_metrics.py) |
| RSS / enrichment writers | [`api/collectors/rss_collector.py`](../api/collectors/rss_collector.py), [`api/services/article_content_enrichment_service.py`](../api/services/article_content_enrichment_service.py) |
| Topic count sync | [`api/domains/content_analysis/services/topic_clustering_service.py`](../api/domains/content_analysis/services/topic_clustering_service.py) |
| API subquery counts | [`api/domains/storyline_management/routes/storyline_crud.py`](../api/domains/storyline_management/routes/storyline_crud.py), `storyline_management.py`, `storyline_consolidation.py` |

---

## Related docs

- [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md) — operator checklist
- [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md) — broader system audit
- [pipeline_repair/ROOT_CAUSE_REPORT.md](pipeline_repair/ROOT_CAUSE_REPORT.md) — June 2026 pipeline repair
