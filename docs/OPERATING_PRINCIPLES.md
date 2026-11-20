# News Intelligence — operating principles (agent SSOT)

How humans and agents (Cline Plan/Act, Cursor) ship **durable** fixes without technical drift. This doc is the **policy** layer; mechanics live in linked runbooks.

**Cline:** always-on `.clinerules/ni-agent.md` + skill **`ni-operating-principles`**.  
**Cursor:** `AGENTS.md` + `.cursor/rules/ni-golden-trace-root-cause.mdc`.

---

## 1. Done means product or contract — not green dashboards

| Claim | Required evidence |
|-------|-------------------|
| **Reader / feed / RSS / briefs** | Golden trace: one `article_id` from RSS through the **first broken stage** → reader when in scope (`docs/GOLDEN_RSS_TO_READER.md`). |
| **Pipeline / spine / automation** | Stage moves for that trace **or** phase runs + pending down for the named phase (SQL + `automation_run_history`). |
| **Monitoring / Grafana only** | Metric or panel proves the **same SSOT** the Monitor uses — not a new COUNT on scrape. |
| **Healthy API** | Necessary, not sufficient. `/health` green with silent spine + stale reader = **not done**. |

**Forbidden “done”:** INSERT theater, Grafana-only patches on product tickets, “fixed” without command output.

---

## 2. Write once, read many (observability)

| Layer | Writers | Readers (no heavy SQL on request path) |
|-------|---------|----------------------------------------|
| **Backlog / queue depth** | `monitor_backlog_snapshot_service.refresh_*` → `infrastructure.automation_state` | Monitor fast paths, Prometheus `ni_*`, Grafana |
| **Phase runs / throughput** | `persist_automation_run_history`, `monitor_run_vocabulary` | Monitor pulse, `process_run_summary`, Grafana |
| **Spine health (target)** | `metrics_materializer` (MVP) → `pipeline.spine_health`, `pipeline.pipeline_metrics` (migration 270) | Monitor product lane, alerts |
| **Pool pressure** | `pool_pressure_advisory` | Monitor chips, admission shedding |

**Agent rule:** When changing backlog or metrics, update the **writer** and **readers** together. Do not add a third COUNT path “for Grafana.”

SSOT map: `docs/MONITOR_REPORTING_AND_METRICS.md` · homelab crosswalk: `docs/monitor_alignment/CROSSWALK.md`.

---

## 3. Minimal scope (code habits)

1. **One sentence what + why** before edits (Cline `workflow.md`).
2. **Grep / repomix / graphify** before opening megabyte services (`ni-repomix-grep`, `repomix-output.xml`).
3. **Smallest correct diff** — fix the first broken stage, not adjacent refactors.
4. **Match existing conventions** — `docs/CODING_STYLE_GUIDE.md`, local patterns in the file you touch.
5. **Contracts:** backlog predicates live in `shared/backlog_selection_contracts.py` with tests; keep counters aligned with runners.
6. **Schema:** `{domain}.articles` / storylines — `docs/GOLDEN_PATH_DATABASE.md`; not `public.*` stubs for domain content.
7. **Commits:** `type(scope): description` — only when the user asks to commit.

**Blocked without explicit approval:** delete outside `archive/`, edit `api/shared/database/connection.py`, ad-hoc prod steps (use `deploy_to_widow.sh` + `ni-ship-widow`).

---

## 4. Plan vs Act (Cline)

| Mode | Output |
|------|--------|
| **Plan** | Evidence + **`ni-plan-handoff`** with `golden_article_id`, stage table, numbered approved steps. No writes/shell. |
| **Act** | Execute approved steps; **`ni-verify-change`** before “fixed”; **`ni-ship-widow`** when prod is in scope. |

Hooks bind `NI_CLINE_MODE` — see `docs/CLINE_BASELINE.md`.

---

## 5. Continuity (anti amnesia)

- **Vault handoff:** `00_Inbox/handoffs/YYYY-MM-DD-<slug>.md` on every non-trivial Plan end and after major Act sessions.
- **Resume Act:** `vault_read_note` handoff first — execute **Approved plan**, no full re-triage.
- **MemPalace / unified-search:** for decisions that span sessions — not a substitute for vault handoffs on NI work.
- **Runtime SoT:** `docs/RUNTIME_PIPELINE_TROUBLESHOOTING.md` §2 for Widow checks after deploy.

---

## 6. Silent spine = outage

If a spine phase has **pending > 0** and **no measurable runs** in the expected window, treat as **P0** (not “low priority backlog”). Typical spine: `entity_extraction`, `event_extraction`, `topic_clustering`, `collection_cycle`, `rss_fetch` intake chain.

Admission should respect **pool pressure** (`defer_new_work`) — shed intake before burning connection waiters.

---

## 7. Deploy gate (Widow)

Before calling prod stable:

1. `web`: `npm run build` when UI touched.
2. `uv run ruff check` / targeted `pytest` on touched paths.
3. `BUILD_INFO` on Widow matches intended SHA after `deploy_to_widow.sh`.
4. Re-check: health, golden stage SQL (if product), backlog snapshot age, pool pressure not pegged.

---

## See also

| Doc | Role |
|-----|------|
| `docs/NI_REPAIR_PLAN.md` | Prioritized repair backlog (platform) |
| `docs/AVAILABLE_SERVICES_AND_MCP.md` | MCP + homelab services agents may use |
| `docs/GOLDEN_RSS_TO_READER.md` | Product closure trace |
| `docs/MONITOR_REPORTING_AND_METRICS.md` | Metrics inventory |