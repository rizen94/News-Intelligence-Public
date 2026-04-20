# Archived ni_review shell copies (2026-04-17)

## `restart_api_with_db.sh.deprecated-pre-2026-04-17`

Obsolete duplicate of `scripts/restart_api_with_db.sh`. It used NAS-tunnel–first DB, a broad `pkill` that could hit other uvicorn apps (e.g. Open WebUI), and hard-coded port 8000. **Do not run** — kept for history only.

`scripts/ni_review/scripts/restart_api_with_db.sh` is now a **wrapper** that `exec`s the canonical script at repo `scripts/restart_api_with_db.sh`.

## `identical_shell_snapshots_2026_04_17/`

Byte-identical copies of scripts that also exist at `scripts/<name>.sh`. Those paths are now **symlinks** to the repo-root `scripts/` versions so the review bundle does not drift. Snapshots remain here for diff archaeology.
