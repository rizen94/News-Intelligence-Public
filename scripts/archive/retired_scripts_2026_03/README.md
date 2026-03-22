# Retired scripts (March 2026)

These lived under `scripts/` (or `scripts/maintenance/`, `scripts/production/`) and were **moved here** because they are **not invoked by the running API or automation**. They remain in the repo for occasional operator or developer use.

**Active catalog:** [../SCRIPTS_INDEX.md](../SCRIPTS_INDEX.md)

## Contents

| Item | Notes |
|------|--------|
| `pi_*.sh` | Pi-hole / Pi disk summaries (optional homelab) |
| `migration_phase2_widow.sh`, `migration_phase3_nas_to_widow.sh` | Historical Widow/NAS migration helpers |
| `move_archive_external.sh` | One-off external archive relocation |
| `validate_finance_pipeline.py` | Manual Chroma/RAG sanity check |
| `review_last_12h_quality.py` | Ad hoc quality sampling |
| `export_*_to_csv.py`, `import_manual_commodity_history.py` | Manual commodity history CSV tools |
| `benchmark_inference.py` | Local GPU/LLM benchmark |
| `investigate_storyline_automation.py` | One-off investigation |
| `verify_environment.py` | Legacy optional-deps probe |
| `pre_testing_checklist.sh` | Pre-flight checklist (references may be stale) |
| `watch_collection.sh` | Watch RSS/collection status in a terminal |
| `resource_monitor.py`, `monitor_system.py`, `view_metrics.py` | Superseded by `full_system_status_check.py` / dashboard |
| `run_finance_tests.sh` | Wrapper for `pytest tests/unit/test_finance_*.py` |
| `check_widow_entity_status.*` | Remote entity diagnostic (see `.sh` for path on Widow) |
| `monitor_nas_mount.sh`, `monitor_llm_progress.sh` | Operator terminal helpers |
| `setup.sh` | Old v3 unified setup (prefer `docs/SETUP_ENV_AND_RUNTIME.md` + `uv sync`) |
| `setup_rss_cron_twice_daily.sh` | Alternate RSS cron installer (superseded by `setup_rss_cron_with_health_check.sh`) |
| `NAS_MOUNT_ON_WIDOW.md` | Legacy NAS mount notes |
| `maintenance/` | Local fix-permissions / port-conflicts / daily_audit helpers |
| `production/` | `enforce_methodology.sh`, `manage-service.sh` (referenced only from archived docs; `manage-service` expected a removed `setup-autostart.sh`) |

Run any script from **repo root** and adjust the path, e.g. `PYTHONPATH=api uv run python scripts/archive/retired_scripts_2026_03/validate_finance_pipeline.py`.
