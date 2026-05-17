# Data quality audit — findings and action list

**Run date:** 2026-05-16  
**Artifacts:** `diagnostics/data_quality_report.json`, `diagnostics/DATA_QUALITY_AUDIT_REPORT.md`  
**SQL pack:** `scripts/diagnostics/data_quality_audit.sql`  
**Runner:** `scripts/diagnostics/run_data_quality_audit.py`

## Connectivity (read first)

| Target | Status |
|--------|--------|
| Widow `192.168.93.101:5432` / `news_intel` | **Unreachable** from audit host (no route / host down) |
| NAS tunnel `localhost:5433` / `news_intelligence` | **Used for this run** — legacy ~61 MB snapshot |

**Production baseline is not valid until re-run on Widow.** The numbers below describe the NAS backup (3 domains: `politics`, `finance`, `science-tech`), not the current `public.domains` registry (`politics-2`, `finance-2`, `legal`, etc.).

```bash
# When Widow is online (from repo root):
PYTHONPATH=api uv run python scripts/diagnostics/run_data_quality_audit.py

# Or via Postgres MCP: run sections from scripts/diagnostics/data_quality_audit.sql
```

---

## Short action list

| Priority | Area | Finding | Action |
|----------|------|---------|--------|
| **High** | Connectivity | Widow DB unavailable during audit | Restore/power Widow; confirm `pg_isready`; re-run full audit on `news_intel` |
| **High** | Schema | NAS DB lacks `intelligence.*` (contexts, claims, bridges) | Do not use NAS snapshot for pipeline KPIs; use Widow only |
| **Medium** | Dedupe | 187 URLs in 2+ silos on legacy DB (mostly politics + finance) | On production: review `RSS_INGEST_EXCLUDE_DOMAIN_KEYS` and `article_duplicate_sources` after Widow run |
| **Medium** | Narrative | Politics: 2/4 storylines missing `analysis_summary` (length &lt; 200) | Re-run storyline refinement when Widow is up |
| **Low** | Narrative | 1 duplicate storyline title group in politics | Merge or rename via storyline CRUD / consolidation service |
| **Info** | Baseline | Per-domain URL dup groups = 0 on NAS | Re-check on Widow (expect non-zero at scale) |

---

## Pack summaries (NAS run — indicative only)

### Pack 0 — Catalog

- Database size ~61 MB; largest tables `politics.articles` (~12 MB), topic keyword/cluster tables.
- Active domains on NAS: 3 legacy silos (not current production registry).

### Pack 1 — Inventory

| Domain | Articles | Storylines | RSS feeds | Article entities |
|--------|----------|------------|-----------|----------------|
| politics | 3,483 | 4 | 52 | 5,695 |
| finance | 199 | 0 | 4 | 34 |
| science-tech | 580 | 0 | 8 | 798 |

- No `enrichment_status` / `intelligence` bridge on NAS → enriched % and context coverage **not measurable** on this target.

### Pack 2 — Duplicates

- **Cross-domain URLs:** 187 shared between politics and finance (syndicated feeds / overlapping RSS seeds).
- **Per-domain URL duplicate extra rows:** 0 (groups may still exist on Widow at scale).
- **Storylines:** 2 missing summary; 1 duplicate title group (politics).
- Global intelligence duplicate queries **skipped** (schema missing).

### Pack 3 — Pipeline

- `automation_run_history` present but no runs in last 24h on NAS (stale backup).
- Enrichment / pass-marker stats require Widow schema.

### Pack 4 — Legal

- `legal` schema not in NAS active domains; run `pack_5d_legal_storylines_health` on Widow after fsck recovery.

### Pack 5 — Structure

- Core per-domain tables exist for all three NAS silos (`articles`, `storylines`, `rss_feeds`, etc.).
- `applied_migrations` ledger on NAS will lag Widow — compare after reconnect.

---

## Thresholds (from plan — apply on Widow)

| Metric | Healthy-ish | Investigate |
|--------|-------------|-------------|
| Articles with context / enriched | &gt; 85% | &lt; 70% |
| URL duplicate extra rows / articles | &lt; 1% | &gt; 3% |
| Enrichment pending, attempts ≥ 3 | ~0 | thousands |
| Automation success 24h | &gt; 90% | &lt; 75% |
| Storylines with summary | majority active | &gt; 30% empty |
| `pipeline_skip` rate | stable low | climbing weekly |

---

## Next operator steps

1. Bring Widow PostgreSQL online (`news_intel`).
2. `PYTHONPATH=api uv run python scripts/diagnostics/run_data_quality_audit.py`
3. Compare `audit_dashboard_summary` to Monitor **backlog_status** / **processing_progress**.
4. If `legal.storylines` errors persist: `REINDEX TABLE legal.storylines;` (already done once post-fsck).
5. Schedule weekly audit (cron or manual); store JSON dated snapshots under `diagnostics/`.
