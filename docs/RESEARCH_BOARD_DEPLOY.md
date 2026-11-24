# Research board — post-catch-up deploy (no mid-catch-up restart)

Use this **after** the overnight `run_major_backlog_catchup` / profiling drain finishes (or during a planned maintenance window).

## 1. Deploy code (includes `/research` list dedupe)

```bash
bash scripts/deploy_to_widow.sh
```

`api/domains/reader/routes/research_subjects.py` now:

- Picks **one** card per curated title when multiple `knowledge_profiles` share a label.
- Skips **entity_canonical fallback** placeholders when a profile already exists for that title.

## 2. Reconcile duplicate subject entities (DB)

Dry-run first:

```bash
cd /opt/news-intelligence && set -a && source .env && set +a
PYTHONPATH=api python3 api/scripts/reconcile_research_subject_entities.py
```

Apply merges / `old_entity_to_new` mappings:

```bash
PYTHONPATH=api python3 api/scripts/reconcile_research_subject_entities.py --apply
```

Then **restart API once** (or let `deploy_to_widow.sh` do it).

## 3. Steady-state research pipeline env (optional after backlog normalizes)

Already set during catch-up session on Widow; revert with `scripts/ops_end_catchup_session.sh` when appropriate.

For sustained throughput while `research_paper_profiles` backlog remains high:

```env
RESEARCH_PAPER_PROFILE_BATCH_LIMIT=8
RESEARCH_PAPER_PROFILE_BACKLOG_TRICKLE_THRESHOLD=5000
RESEARCH_PAPER_PROFILE_TRICKLE_BATCH=8

CLAIM_EVIDENCE_APPRAISAL_ENABLED=true
CLAIM_EVIDENCE_APPRAISAL_BATCH=12
CLAIM_EVIDENCE_APPRAISAL_BACKLOG_TRICKLE_THRESHOLD=500
CLAIM_EVIDENCE_APPRAISAL_TRICKLE_BATCH=6
```

Scheduling phases: `research_paper_profiling` → `claim_evidence_appraisal` (flat scheduler + continuous drain).

## 4. Verify

- `/research` — one card per curated subject; counts non-zero where appraisals merged.
- `GET /api/reader/research/subjects`
- `SELECT COUNT(*) FROM intelligence.claim_evidence_appraisal` trend over 24h.