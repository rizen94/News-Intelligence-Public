# Available services and MCP (NI agents)

**Authoritative MCP wiring:** `HomeLab-AI-Stack/config/mcp-stack.coding.json` (daily) or `config/mcp-stack.json` (full).  
**Sync:** `MCP_STACK_CANON=.../mcp-stack.coding.json ./scripts/sync-agent-mcp.sh` (from HomeLab-AI-Stack).  
**Global rule:** `~/Documents/Cline/Rules/00-connected-mcp-server-ids.md`.

**Dev repo:** `/home/pete/Documents/projects/news_intelligence`  
**Prod runtime:** Widow `/opt/news-intelligence` (`192.168.93.101`, API `:8000`)

---

## Coding MCP profile (default for Cline NI)

| Server key | Tools (prefix) | When to use |
|------------|----------------|-------------|
| **`postgres-mcp`** | SQL via SSE | Spine/golden trace evidence — **read-only** on `news_intel` |
| **`obsidian-vault`** | `vault_*` | Handoffs `00_Inbox/handoffs/`, operator notes |
| **`homelab-env-manager`** | `hem_*` | Port conflicts, compose catalog — not NI code deploy |
| **`unified-search`** | `unified_search` | Cross-vault + MemPalace + repo docs search |
| **`graphify-ni-pipeline`** | graphify MCP | Call graph over pipeline slice — refresh `scripts/graphify_ni_pipeline_slice.sh` |
| **`serena-ni`** | symbol tools | Refactors only — toggle off when idle |

Toggle **off** when idle (per `CLINE_BASELINE.md`): `serena-ni`, `graphify-ni-pipeline`, `unified-search`, `homelab-env-manager`.

---

## Full stack extras (`mcp-stack.json`)

| Server key | Role |
|------------|------|
| **`mempalace`** | `mempalace_*` — long-lived decisions (wing News Intelligence) |
| **`obsidian-news-vault`** | NI-dedicated vault mirror if configured |
| **`agent-budget`** | `cfo_*` — session budget (optional) |
| **`crawl4ai`**, **`scrapy`**, **`curl-impersonate`** | Web fetch — rare for NI; respect robots |

**Never use:** `mempalace-server`, `news-intel-server`, legacy `query_memories` / `save_memory`.

---

## Homelab runtime services (NI-relevant)

| Service | Where | NI relationship |
|---------|-------|-----------------|
| **Caddy** | PopOS `192.168.93.99` | TLS → Widow nginx (`news-intelligence-ag.duckdns.org`) |
| **Prometheus** | PopOS | Scrapes Widow `/api/system_monitoring/prometheus` |
| **Grafana** | PopOS | Dashboards in `api/monitoring/grafana/*.json` |
| **Postgres MCP gateway** | PopOS `:18090` | DSN → Widow `news_intel` |
| **Ollama** | PopOS `:11434` | Shared inference; NI uses `OLLAMA_*` from Widow `.env` |
| **Open WebUI** | PopOS | Separate product — not NI Monitor |

Widow-only: `news-intelligence-api-public` systemd, local Postgres `news_intel`, nginx.

---

## NI workspace skills (Cline)

| Skill | Purpose |
|-------|---------|
| `ni-operating-principles` | Anti-drift policy — read before monitor/metrics/refactors |
| `ni-golden-trace` | Product closure |
| `ni-pipeline-debug` | Widow runtime evidence ladder |
| `ni-repomix-grep` | Search-before-edit |
| `ni-verify-change` | Definition of done |
| `ni-ship-widow` | Authorized deploy |
| `ni-plan-handoff` | Plan → Act boundary |
| `ni-migrations` | SQL ledger |
| `ni-db-golden-path` | Schema contract |
| `mempalace-tools` | MemPalace tool names |

Index: `.clinerules/ni-agent.md` · `docs/CLINE_BASELINE.md`.

---

## Host authority

| Path | Status |
|------|--------|
| `~/Documents/projects/news_intelligence` | Canonical git + edits |
| `News Intelligence` (Cursor sparse root) | May mirror; prefer `news_intelligence` for writes |
| `/opt/news-intelligence` on PopOS | **Cold** — do not treat as prod |
| `/opt/news-intelligence` on Widow | **Prod** |

See `PROJECT_STATUS.md`.