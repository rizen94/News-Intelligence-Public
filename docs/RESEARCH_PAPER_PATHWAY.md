# Research-paper pathway (vs event news)

Scientific papers do **not** use news-style entity / claim / event / embedding storyline clustering.

## Flow

1. **Classify** at RSS insert / enrichment — [`api/services/research_paper_classifier.py`](../api/services/research_paper_classifier.py) stamps `metadata.content_kind=research_paper` (arXiv, bioRxiv, medRxiv, DOI article hosts, …) plus `pipeline_skip` for event/claim extraction.
2. **Profile** — [`api/services/research_paper_profile_service.py`](../api/services/research_paper_profile_service.py) writes axes into `intelligence.research_paper_profiles` (question, methods, findings, implications, subjects, `domain_facets`).
3. **Literature bridge** — [`api/services/research_literature_bridge_service.py`](../api/services/research_literature_bridge_service.py) upserts `intelligence.processed_documents` (`source_type=literature`, `metadata.article_id` / `domain_key`) so appraisal can see papers.
4. **Evidence appraisal** — [`api/services/claim_evidence_appraisal_service.py`](../api/services/claim_evidence_appraisal_service.py) grades findings (prompt: [`evidence_appraisal.md`](../api/config/prompts/research/evidence_appraisal.md)) into `intelligence.claim_evidence_appraisal`. Gated by `CLAIM_EVIDENCE_APPRAISAL_ENABLED=true`.
5. **Subject merge** — `auto_merge_from_appraisal` in [`knowledge_profile_service.py`](../api/services/knowledge_profile_service.py) merges into entity-rooted `knowledge_profiles` (is / is_not / open) and `research_claim_ledger` without overwriting prior assertions.
6. **Automation** — phases `research_paper_profiling` then `claim_evidence_appraisal` (bridge catchup + batch appraisal).
7. **Gate** — discovery and proactive exclude `content_kind=research_paper`; claim/event batches skip them.
8. **Reader** — `/research` is a **topic index** (curated subjects by domain) → subject **fact sheet** (`is` / `is_not` / `open`). Not a paper-headline feed. APIs: `GET /api/reader/research/subjects`, `GET /api/reader/research/subjects/{domain}/{entity_id}`. Dated papers may still appear on One-offs.

Product / lab-blog news in the same domain still uses the normal storyline pathway. Packages-as-binder stays parked; research accumulation hangs off entities/subjects + ledger.

Corpus domains: `neurodiversity`, `artificial-intelligence`, `medicine`.

Topic keywords under each domain on `/research` come from
[`api/config/research_subject_topics.yaml`](../api/config/research_subject_topics.yaml)
and are mirrored onto vault science topic notes
(`50_Science/40_Topics/…`) via `api/scripts/sync_research_topic_vault_notes.py`.

### Gap fill (sources)

Neurodiversity was configured in YAML but **had 0 `rss_feeds` rows** until seeded.
After adding high-evidence PubMed + journal feeds, seed with:

```bash
PYTHONPATH=api uv run python api/scripts/seed_domain_rss_from_yaml.py \
  --config api/config/domains/neurodiversity.yaml
```

Added literature sources (beyond original PubMed ASD/ADHD + bio/medRxiv + Molecular Autism + ClinicalTrials):

- PubMed autism high-evidence (meta-analysis / systematic review / RCT)
- PubMed autism genetics
- Journal of Neurodevelopmental Disorders (BMC)
- Frontiers in Psychiatry — Autism section
- Autism (SAGE) TOC

AI/medicine already have arXiv / PubMed / journal RSS; remaining gap is mostly
**profiling + appraisal drain**, not missing feeds.

### Subject routing (appraisal → board)

`auto_merge_from_appraisal` matches curated boards via paper
`subjects_studied` + article title + aliases. It does **not** fall back to the
domain’s first subject (that used to dump off-topic neuro papers onto Autism /
generic AI onto Artificial Intelligence). Unmatched appraisals skip merge
(`no_subject_entities`) until a curated subject matches.

### Feed reliability notes

- **Autism (SAGE) TOC** (`autism.sagepub.com` etoc RSS) — often fails DNS /
  TLS from the collector host; keep `is_active=false` unless the feed resolves.
- **PubMed “saved search” RSS** URLs under `/rss/create/saved_searches/` frequently
  return empty (+0) without a live PubMed saved-search cookie/session. Prefer
  journal RSS, ClinicalTrials.gov, bio/medRxiv subject feeds, or PubMed search
  URLs that are known-good for anonymous fetch.

```
Paper ingest → classify → fulltext → profile
  → literature processed_documents
  → claim_evidence_appraisal (finding + hypothesis + quotes + grade)
  → research_claim_ledger / knowledge_profile (is / is_not / open)
  → /research subject board
```

## Ops

```bash
# Seed Autism / ADHD / AI subject entities (idempotent)
PYTHONPATH=api uv run python api/scripts/seed_world_entities_from_yaml.py \
  --domain neurodiversity --domain artificial-intelligence --domain medicine

# Stamp + ensure pending profiles (all pipeline domains)
PYTHONPATH=api uv run python -c \
  'from services.research_paper_profile_service import backfill_stamp_research_papers as b; print(b(5000))'

# Drain LLM profiling (small batch)
PYTHONPATH=api uv run python -c \
  'import asyncio; from services.research_paper_profile_service import drain_research_paper_profiling as d; print(asyncio.run(d(8)))'

# Bridge done profiles → literature docs (no LLM)
PYTHONPATH=api uv run python -c \
  'from services.research_literature_bridge_service import backfill_literature_docs_from_profiles as b; print(b(limit=100))'

# Appraise due literature docs (requires CLAIM_EVIDENCE_APPRAISAL_ENABLED=true)
PYTHONPATH=api uv run python -c \
  'from services.claim_evidence_appraisal_service import run_claim_evidence_appraisal_batch as r; print(r(limit=5))'
```

Env: `CLAIM_EVIDENCE_APPRAISAL_ENABLED=true`, optional `CLAIM_EVIDENCE_APPRAISAL_BATCH=5`.

Migration: `api/database/migrations/235_research_paper_profiles.sql`. Appraisal / ledger / knowledge_profiles tables are live on Widow `intelligence` schema.
