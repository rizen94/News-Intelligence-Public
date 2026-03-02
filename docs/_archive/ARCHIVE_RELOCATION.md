# Archive Relocation

**Date:** 2026-02-21

## Root archive/

The project's `archive/` folder (27GB, ~508k files) was moved outside the project to reduce disk usage and improve indexing.

**New location:** `../News-Intelligence-Archive/archive_20260221/`

**Contents:** v3 backups, pre-consolidation copies, duplicate production configs.

**To restore:** Copy or symlink back if needed. The folder is listed in `.gitignore`.

**Script:** `scripts/move_archive_external.sh` — can be used to relocate future archives.

## docs/archive/

Historical documentation (migration logs, reports, v3 docs) was moved to:

**New location:** `../News-Intelligence-Archive/docs_archive_20260221/`

Essential docs remain in `docs/` — see `docs/DOCS_INDEX.md`.
