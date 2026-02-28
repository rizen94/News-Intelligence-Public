# Migration TODO — Three-Machine Architecture

Pre-migration items (can run now, without new PC) are marked **[NOW]**.
Phases requiring the new secondary machine are marked **[NEW PC]**.

---

## Pre-Migration (Do First)

- [ ] **[NOW]** Archive current state and commit stable rollback point
- [ ] **[NOW]** Run Phase 4.1 config audit (DB, Ollama, controllers)
- [ ] **[NOW]** Add migration plan doc to repo
- [ ] **[NOW]** Create infrastructure/ folder + migration-state.json
- [ ] **[NOW]** Document current DB credentials in infrastructure/ (exclude from git)

---

## Migration Phases (Sequential)

- [ ] **[NEW PC]** Phase 1: Secondary machine discovery (SSH, record specs in infrastructure/secondary-machine-info.txt)
- [ ] **[NEW PC]** Phase 2: PostgreSQL 16 setup on secondary
- [ ] **[NEW PC]** Phase 3: Database migration from NAS to secondary
- [ ] Phase 4: Application code changes (multi-machine config, role-based startup)
- [ ] **[NEW PC]** Phase 5: Deploy app to secondary + systemd + backup cron
- [ ] **[NEW PC]** Phase 6: Integration validation (both machines)
- [ ] **[NEW PC]** Phase 7: Go live, decommission NAS PostgreSQL
- [ ] **[NEW PC]** Phase 8: Monitoring and maintenance setup

---

## Rollback

- **Before Phase 7.5:** Revert `DB_HOST` to NAS (192.168.93.100), restart app.
- **After Phase 7.5:** Re-enable PostgreSQL on NAS, restore from backup, revert config.

Tag for rollback: `git checkout pre-migration-rollback`
