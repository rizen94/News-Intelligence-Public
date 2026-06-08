# Longitudinal intelligence — operator runbook (Phase 6)

Sunday ritual and day-to-day curation for MVP arcs `resource_geopolitics` and `political_tensions_multipolar`.

**Related:** [LONGITUDINAL_INTELLIGENCE_EXECUTION.md](LONGITUDINAL_INTELLIGENCE_EXECUTION.md) · [CHRONOLOGICAL_ACCURACY_DOCTRINE.md](CHRONOLOGICAL_ACCURACY_DOCTRINE.md)

---

## Weekly ritual (Sunday)

1. Open **Outputs → Arc: Resources** or **Arc: Geopolitics** spine view.
2. Read the **Weekly Brief** (`/{domain}/arcs/{arc_id}/brief`).
3. Click citation markers → **Citation Drawer** (event / ingestion / vintage dates).
4. Mark **Useful** on sections that should drive next week's synthesis depth.
5. Open **Operations → Arc curation** to add missed reference events or flag gaps.
6. Optional: **Regenerate** brief after major living-corpus changes (Monitor backlog idle).

Automation runs `arc_report_generation` weekly; manual regenerate uses the same `slow_report_service`.

---

## Reference event curation

- **UI:** `/{domain}/arcs/curation`
- **API:** `POST /api/intelligence/reference_events`
- **Corrections:** append-only — `POST /api/intelligence/reference_events/{id}/supersede` (audit row in `reference_event_corrections`)
- **Flags:** `POST /api/intelligence/reference_events/{id}/flag` for missed coverage notes

Required fields: `event_date`, `title`, `summary`, at least one `sources[]` entry with URL, `arc_ids[]`.

Never edit dates via LLM — only structured fields and approved importers.

---

## Arc report feedback

- **UI:** Useful buttons on Weekly Brief page
- **API:** `POST /api/intelligence/arc_report/{arc_id}/feedback`
- **Storage:** `intelligence.arc_report_feedback`
- **Effect:** high-rated sections appear in the next `slow_report_service` prompt as operator boost text

Section keys: `overall`, `what_changed`, `where_this_fits`, `the_numbers`, `prior_analogues`, `open_questions`.

---

## External data (optional env)

| Source | Env | Automation phase |
|--------|-----|------------------|
| FRED/ALFRED | `FRED_API_KEY` | `macro_series_refresh` |
| ACLED | `ACLED_API_KEY`, `ACLED_EMAIL` | `external_events_sync` |
| OFAC SDN | `SANCTIONS_INGEST_ENABLED=true` | `sanctions_refresh` |
| GPR/EPU CSV | `GPR_CSV_PATH`, `EPU_CSV_PATH` | `macro_series_refresh` |
| Kiwix Wikipedia | `KIWIX_WIKIPEDIA_REST_URL` | RAG + embeddings worker |

After external_events ingest, `longitudinal_matview_refresh` updates heatmap aggregates.

---

## Widow setup (one-time)

```bash
# pgvector (Postgres superuser once)
sudo -u postgres psql -d news_intel -c 'CREATE EXTENSION IF NOT EXISTS vector;'
PYTHONPATH=api .venv/bin/python api/scripts/run_migration_223.py
PYTHONPATH=api .venv/bin/python api/scripts/register_applied_migration.py 223 ...

PYTHONPATH=api .venv/bin/python api/scripts/run_migration_224.py
PYTHONPATH=api .venv/bin/python api/scripts/register_applied_migration.py 224 ...

# Politics RSS from spec
PYTHONPATH=api .venv/bin/python api/scripts/generate_domain_artifacts.py \
  --spec api/config/domains/specs/politics.domain.json --force
PYTHONPATH=api .venv/bin/python api/scripts/seed_domain_rss_from_yaml.py \
  --config api/config/domains/politics.yaml

# Weekly DB backup (Sundays 04:30 UTC)
./scripts/install_weekly_backup_cron.sh
```

Or run bundled: `./scripts/finish_longitudinal_widow_setup.sh`

**After Widow maintenance:** `./scripts/resume_longitudinal_widow.sh` (applies 221–225, verifies schema, seeds, matviews).

Migration **225** adds `quarantine` to `arc_reports.report_type` and creates `cross_domain_correlations` for analogue API — required before slow-report validation quarantine works.

---

## Evaluation

```bash
PYTHONPATH=api uv run python api/scripts/run_arc_report_eval.py
PYTHONPATH=api uv run python api/scripts/run_arc_report_eval.py --arc resource_geopolitics
```

Golden questions: `tests/eval/arc_report_golden_questions.yaml`

---

## Definition of done (MVP)

Operator can on Sunday morning: open an arc, read ~1000-word brief, click citations with three timestamps, view spine + analogues, and trust dates/numbers trace to structured data — with feedback and curation closing the loop.
