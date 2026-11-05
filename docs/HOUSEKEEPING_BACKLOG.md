# News Intelligence Housekeeping Backlog

**Created**: October 24, 2026  
**Status**: In-progress (P0 TROUBLESHOOTING.md done)  
**Location**: `/home/pete/Documents/projects/News Intelligence/docs/HOUSEKEEPING_BACKLOG.md`

This document preserves the audit findings from the infrastructure path drift review so they don't need to be re-derived. Tasks are prioritized by impact.

---

## P0 -- Critical (Immediate)

### [DONE] TROUBLESHOOTING.md full rewrite
- **Status**: DONE (Oct 24, 2026)
- **What was done**: Complete rewrite from Docker-compose-era doc to bare-metal Widow reality
- **Removed**: All `./start_system.sh` / `./stop_system.sh` references, Vite dev server mentions, Docker compose resets, obsolete log paths
- **Added**: Systemd service management (news-intelligence-api-public.service), Caddy nginx proxy docs, Ollama routing troubleshooting, Quick Reference command table
- **File**: [`docs/TROUBLESHOOTING.md`](TROUBLESHOOTING.md)

---

## P1 -- Cleanup (Next Priority)

### Consolidate `archive/` structure
- **What**: Two separate archive layers (`_archive/` and `archive/`) with nested sub-archives create unnecessary complexity
- **Action**: Move all `_archive/` contents into `archive/` with date-ordered naming; delete empty `_archive/` directory
- **Risk**: Low -- links in docs will need updating, but content is preserved
- **Sub-tasks**:
  - [ ] Inventory `_archive/` contents and catalog what goes where in `archive/`
  - [ ] Move date-grouped items into `archive/2026_*/` subdirs for consistency with existing `News-Intelligence-Archive/` pattern
  - [ ] Update any cross-links in docs that reference `_archive/` paths
  - [ ] Delete empty `_archive/` directory

### Clean up `docs/generated/`
- **What**: Empty directory serving no purpose
- **Action**: Delete `docs/generated/`
- **Risk**: None (empty)

### Remove orphaned `=NN.N` files from `/opt/news-intelligence/`
- **What**: Orphaned version marker files (`=15.0`, `=4.0`, `=6.0`, etc.) scattered in `/opt/news-intelligence/` on Widow
- **Action**: Identify origin, remove if stale; update if they serve a deployment tracking purpose
- **Risk**: Medium -- need to verify none are used by deployment scripts

### Update remaining stale docs
- **What**: Several docs in `docs/` reference Docker Compose or start_system.sh patterns
- **Action**: Search for and replace all Docker/start_system references with bare-metal equivalents
- **Targets**:
  - [ ] Check any remaining docs that mention `docker compose`, `compose up`, `start_system.sh`
  - [ ] Update database connection sections that reference container networks instead of localhost/PgBouncer

---

## P2 -- Structure (Low Urgency)

### Draft initial ADR.md
- **What**: No Architecture Decision Records exist
- **Action**: Create `docs/ADR.md` with a template and initial entries for major decisions already made:
  - Bare-metal migration from Docker Compose
  - AutomationManager embedded in uvicorn vs. separate worker
  - Per-domain schema silo pattern
  - Caddy (PopOS) + nginx (Widow) public HTTPS architecture
- **Risk**: None

### Draft initial CHANGELOG.md
- **What**: No changelog exists for tracking releases/hotfixes
- **Action**: Create `docs/CHANGELOG.md` with a structured format (semver-compatible):
  - Unreleased section at top
  - Date-stamped entries grouped by category (Added, Changed, Fixed, Removed)
  - Initial section capturing pre-v3.0 migration changes

### Consolidate nested archives within `archive/`
- **What**: `archive/` contains nested sub-directories (`archive_20260221`, `docs_archive_20260221`, etc.) that add complexity
- **Action**: Flatten date-grouped items or establish a clear naming convention for dated archives
- **Risk**: Medium -- verify nothing is referenced by external tooling

---

## P3 -- Housekeeping (Nice to Have)

### Move Assembly Integrity and Quality Reader docs
- **What**: Some documentation may belong in `docs/` rather than the root or vice versa
- **Action**: Review doc placement conventions; move misplaced docs to `docs/`

### Dev/Prod path drift documentation
- **What**: Dev (PopOS) and Prod (Widow bare metal) paths are decoupled with no automated sync verification
- **Action**: Add a CI check or script that diffs the dev workspace against prod state
- **Current reality documented in**: `AGENTS.md` (HOST GUARDRAILS section), `PROJECT_STATUS.md`, `PROJECT_BOUNDARIES.md`

---

## Reference: Audit Context

The audit that generated this backlog identified these specific housekeeping items from reviewing `docs/`, `archive/`, and `/opt/news-intelligence/`:

1. **Stale TROUBLESHOOTING.md** -- Docker Compose references, outdated systemd info, obsolete commands
2. **Redundant archive layers** -- `_archive/` + `archive/` with nested sub-archives
3. **Empty `docs/generated/`** -- serves no purpose
4. **Orphaned prod files** (`=NN.N`) in `/opt/news-intelligence/`
5. **Missing ADRs** -- No architecture decision records
6. **Missing CHANGELOG** -- No version history tracking
7. **Assembly Integrity / Quality Reader docs** -- potentially misplaced
8. **Dev/prod path drift** -- no verification mechanism

Items 1-4 are P0/P1; items 5-8 are P2/P3. TROUBLESHOOTING.md (item 1) is done.

---

## How to Use This Doc

- Add checked-off items as you complete them
- When adding new tasks, include: status, scope, action steps, risk level
- Referenced from `PROJECT_STATUS.md` under housekeeping section if applicable
- Tasks can be split across multiple sessions -- this doc preserves the full context
