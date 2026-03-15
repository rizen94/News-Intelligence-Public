# Release v5.0 — Stable (2026-02-21)

## Summary

v5.0 is the current stable release. Built on the Widow migration (v4.1): database on Widow, NAS storage-only, three-machine architecture.

**Next:** v6 development (planned).

---

## Version 5.0 Highlights

- Same architecture as v4.1 (Widow migration complete)
- Version strings updated project-wide to 5.0
- Documentation consolidated and indices simplified
- API uses **flat paths** — `/api/...` (no version segment; e.g. `/api/{domain}/finance/analyze`, `/api/orchestrator/status`). Previous docs referred to `/api/`; that has been retired.

---

## Reference

- [RELEASE_v4.1_WIDOW_MIGRATION.md](RELEASE_v4.1_WIDOW_MIGRATION.md) — Widow migration details, phases, scripts
- [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) — Operations and architecture
