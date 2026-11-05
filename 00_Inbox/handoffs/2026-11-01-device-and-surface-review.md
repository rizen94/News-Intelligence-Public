# Device & Surface Review: Standardization and Coordination

**Date:** 2026-11-01  
**Reviewer:** Agent (post-deploy commit review)  
**Scope:** All devices, services, surfaces for News Intelligence standardization  

---

## 1. DEPLOYMENT TOPOLOGY OVERVIEW

### 1.1 Infrastructure Map

| Host | LAN IP | OS Role | NI Relevance |
|------|--------|---------|-------------|
| **popos** | `192.168.93.99` | Primary GPU dev stack | Dev workspace, dockerized shared infra |
| **widow** | `192.168.93.101` | Production host | Main API, local DB, nginx, RSS worker |
| **nas** | `192.168.93.100` | NAS/backups | Cold storage (not directly queried) |

### 1.2 Services Per Machine

#### PopOS (192.168.93.99) - Dockerized Shared Infrastructure

| Service | Container | Image | Port | Status | Notes |
|---------|-----------|-------|------|--------|-------|
| Postgres | `ai-lab-postgres` | `postgres:16.6-alpine` | :15432 | healthy | Local dev DB only; NOT production NI data |
| Ollama | `ai-lab-ollama` | `ollama/ollama:latest` | :11434 | healthy | Embedding/LLM inference for PopOS side |
| Caddy | `ai-lab-caddy` | `caddy:2.11.4` | :80/:443 | healthy | Reverse proxy for docker services |
| Postgres MCP | `ai-lab-postgres-mcp` | N/A | internal | healthy | Connects to NI DB on Widow for queries |
| Ollama Proxy | `ai-lab-ollama-proxy` | local-build | :18xxx | healthy | Dual-host routing for PopOS/Widow ollama |
| PG Exporter | `ai-lab-postgres-exporter-widow` | Prometheus image | internal | healthy | Monitors Widow postgres |

**Missing on PopOS:** pgBouncer (not in docker-compose), Grafana/Prometheus exporters partially running.

#### Widow (192.168.93.101) - Production Host

| Service | Type | Config Location | Port | Status |
|---------|------|-----------------|------|--------|
| NI API (`nri-api`) | systemd | `infrastructure/news-intelligence-api-public.service` | :8000 (127.0.0.1) | managed by systemd |
| NI Secondary Worker | systemd | `infrastructure/newsplatform-secondary.service` | - | RSS collection |
| postgres (local) | native/apt | system package | :5432 | production NI data |
| pgBouncer (local) | native/apt | system package | :6432 | connection pooling |
| Ollama (local) | manual install | system path | :11434 | inference for NI pipeline |
| nginx | apt/managed | `nginx/nginx.conf` | :80/:443 | reverse proxy to :8000 |

### 1.3 Code Paths

| Surface | Dev Location | Production Target | Deploy Script |
|---------|-------------|-------------------|---------------|
| Python API code | `/home/pete/Documents/projects/News Intelligence` | `/opt/news-intelligence` on Widow | `scripts/deploy_to_widow.sh` |
| Frontend SPA (Vite) | `web/dist/` | `/var/www/news-intelligence/web/dist` on Widow | `scripts/deploy_public_demo_to_widow.sh` |
| Infrastructure configs | `infrastructure/` | copied to `/etc/systemd/` on Widow | manual install via rsync or systemd-copy |
| nginx config | `nginx/` | `/etc/nginx/conf.d/` on Widow | manual |

---

## 2. CODE VALIDATION STATUS (After Cleanup)

### 2.1 Pre-Commit Validation - DONE

| Check | Status | Details |
|-------|--------|---------|
| Docs `_archive/` -> `docs/archive/` migration | PASSED | 18 files, 777 valid links preserved, zero dead _archive/ links |
| Python AST parsing (`api/*.py`) | PASSED | All source files pass syntax validation |
| Git commit | PASSED | `53012c6` - "docs: migrate _archive/ references..." |

### 2.2 Post-Deploy Validation - NEEDS WORK

| Check | Status | Gap |
|-------|--------|-----|
| Pytest suite execution | PARTIAL | 26 warnings (`requires_api`, `asyncio` markers missing from config), 21 tests FAIL to collect due to DB connection timeout (tests need live DB) |
| System import validation | OK | FastAPI 0.136.1 confirmed on system python |
| Frontend build | NOT TESTED | No Vite build run after cleanup; should validate `npm run build` before deploying web |
| Widow systemd service health | NOT CHECKED | Cannot verify from PopOS without SSH - must check via SSHFS or direct access |

### 2.3 Known Test Suite Issues

1. **Missing pytest markers**: Tests use `@pytest.mark.requires_api` and `@pytest.mark.asyncio` but these are not registered in `api/pytest.ini`. This causes warnings (not errors) that mask real test failures.
2. **DB connection timeout**: Tests require a live Postgres at the URI specified in `.env`. PopOS local postgres is on :15432, tests may expect :5432 or different credentials.
3. **No CI pipeline**: All validation must be manual - no GitHub Actions, GitLab CI, or similar configured.

---

## 3. STANDARDIZATION GAPS (Ranked by Impact)

### HIGH PRIORITY

#### Gap 1: Docker Image Pinning Instability
**Issue:** `ollama/ollama:latest` uses the `latest` tag - no fixed pin. Other services (Grafana, Prometheus exporters) also use `latest`.  
**Risk:** Silent breaking changes from upstream updates.  
**Fix:** Pin all images to exact versions. Add a `VERSIONS.md` tracking document.

#### Gap 2: No Automated Deploy Pipeline
**Issue:** Two manual rsync scripts (`deploy_to_widow.sh`, `deploy_public_demo_to_widow.sh`) - no version comparison, no rollback, no atomic deployment.  
**Risk:** Stale code on Widow without detection.  
**Fix:** Add `git describe --tags` version to API startup; add deploy script that compares git SHA between local and remote before syncing.

#### Gap 3: Test Suite Non-Functional for CI
**Issue:** pytest cannot run tests (DB + marker issues) - no automated validation gate exists.  
**Risk:** Broken code can be deployed without detection.  
**Fix:** Register missing markers in `api/pytest.ini`; add `DATABASE_URL` fixture or docker-compose for test DB; aim for pre-deploy validation step.

### MEDIUM PRIORITY

#### Gap 4: Multiple `.env` Variants
**Issue:** Three separate env files exist:
- `.env` (shared/default)
- `.env.popos_worker` (PopOS GPU co-tenancy overlays)
- `.env.popos_worker.bak-pre-claim-burn` (old backup - should be cleaned up)

No mechanism to verify which vars are active on each machine.  
**Fix:** Consolidate variants, add `.env.example` documentation per-machine.

#### Gap 5: No Version Tracking at Runtime
**Issue:** API has no `GET /health` endpoint that returns git SHA or version. Frontend `web/package.json` says `"version": "9.0.0"` but no correlation to deployed build.  
**Fix:** Add `/health` endpoint returning `git_commit`, `deployed_at`, `api_version`; add frontend `build-info.json`.

#### Gap 6: PopOS Worker Services Not in Fleet Catalog
**Issue:** `.env.popos_worker` references `news-intelligence-popos-worker-*.service` but no systemd files exist for these on PopOS.  
**Fix:** Audit whether these services are needed, and if so, create them or remove the .env overlay.

### LOW PRIORITY

#### Gap 7: Missing Backup for `.env.popos_worker.bak-pre-claim-burn`
**Issue:** Old backup file exists with credentials data. Should be rotated out or verified safe.

#### Gap 8: Grafana Dashboard Config Not Version-Controlled
**Issue:** Infrastructure has `api/monitoring/grafana/alerts-embeddings-host.yaml` but no comprehensive dashboard management.

---

## 4. COORDINATION CHECKLIST (Per Deployment)

### Before Deploying to Widow (every time):

    [ ] 1. git diff --stat HEAD~1 - verify what changed
    [ ] 2. python3 -m py_compile on all modified .py files (syntax check)
    [ ] 3. python3 -m ast.parse on all modified .py files (import structure)
    [ ] 4. npm run build:bundle in web/ (frontend build test)
    [ ] 5. Check for new or dead markdown links in docs/ (grep _archive/)
    [ ] 6. Compare local git SHA vs widow /opt/news-intelligence git SHA (if widows has git repo)

### After Deploying to Widow:

    [ ] 1. SSH into Widow, verify systemd status: systemctl status news-intelligence-api-public
    [ ] 2. curl http://127.0.0.1:8000/health (or known endpoint) - check HTTP 200
    [ ] 3. Check nginx upstream logs for 502/504 errors
    [ ] 4. Verify DB connection via systemd_db_probe.py output in journal
    [ ] 5. Verify secondary worker is running: systemctl status newsplatform-secondary

---

## 5. RECOMMENDATIONS (Prioritized)

| # | Recommendation | Effort | Impact | Notes |
|---|---------------|--------|--------|-------|
| R1 | Add `GIT_COMMIT` version to `/health` endpoint | Low | High | Critical for debugging deployed versions |
| R2 | Pin `ollama:latest` -> exact SHA/version in docker-compose.yml | Low | Medium | Prevents silent breaking changes |
| R3 | Register pytest markers in api/pytest.ini | Low | High | Fixes 26 warnings immediately |
| R4 | Add pre-deploy validation gate (script) | Medium | High | Replace manual checklist with automated one |
| R5 | Archive `.env.popos_worker.bak-pre-claim-burn` | Low | Low | Security hygiene |
| R6 | Create PopOS worker systemd units or remove .env overlay | Medium | Medium | Clarify PopOS deployment model |

---

## 6. SERVICE DEPENDENCY MATRIX

    Widow API (:8000) --+--> Widow Postgres (:5432) [production NI data]
                        +--> PopOS Ollama (:11434) [dev QA inference]
    PopOS Docker Postgres (:15432) [local dev only, NOT used by prod]
                        +--> PopOS Ollama (:11434) [embedding for dev/QA]
    Widow Ollama (:11434) --+ [production inference - primary target]

    Frontend (nginx on Widow) --> Widow API (:8000 upstream)
                                  --> /var/www/news-intelligence/web/dist/ (Vite SPA)

**Key insight:** PopOS postgres and Ollama serve as local dev/QA proxies. Production always uses Widow's native services. The dual-host Ollama routing (`ollama-proxy`) manages which inference requests go to which host based on GPU load/cotenant rules.

---

*End of review. See also: `docs/ARCHITECTURE_AND_OPERATIONS.md`, `docs/WIDOW_BOOT_RESILIENCE.md`, `fleet/catalog.yaml` (Homelab).*
