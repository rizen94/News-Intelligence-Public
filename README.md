# News Intelligence System

**Status:** Active | **Version:** 8.0.0 **(stable)** | **Last updated:** March 2026

---

## What It Is

News Intelligence is an **AI-powered news aggregation and analysis platform** that turns many sources into one coherent intelligence view. It:

- **Collects** news from RSS feeds (and optional PDF/document sources).
- **Processes** content with local AI (summaries, entities, topics, sentiment, quality).
- **Builds intelligence** over time: storylines, entity profiles, tracked events, claims, and cross-domain patterns.
- **Delivers** editorial-style output: daily briefings, storyline narratives, entity dossiers, and fact-checked insights.

All AI runs **locally via Ollama** — no cloud LLM required. The system is designed for a small footprint: Primary (API + frontend + ML), Widow (PostgreSQL + RSS), and optional NAS for storage.

---

## For code reviewers (start here)

**Goal:** Understand the architecture and pipelines without assuming a turnkey local run.

| Step | Doc / file |
|------|------------|
| 1 | **[docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md)** — where code lives, high-interest files. |
| 2 | **[docs/CODE_REVIEW_AND_RUN_CAVEATS.md](docs/CODE_REVIEW_AND_RUN_CAVEATS.md)** — honest requirements; **why casual clone-and-run is not recommended** without Postgres/Ollama/env work. |
| 3 | **[docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md](docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md)** — v8 **collect-then-analyze**, phase map, link into `automation_manager.py`. |
| 4 | **[AGENTS.md](AGENTS.md)** — terminology and canonical entry points. |
| 5 | **[docs/DOCS_INDEX.md](docs/DOCS_INDEX.md)** — full doc catalog. |

**Architecture and data flow (read next):**

- [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) — what the system is and how pieces connect; extended narrative (archived): [docs/_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md](docs/_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md).
- [docs/DATA_FLOW_ARCHITECTURE.md](docs/DATA_FLOW_ARCHITECTURE.md) — intelligence cascade (ingestion → editorial).
- [docs/SYSTEM_OVERVIEW.md](docs/SYSTEM_OVERVIEW.md) — routes, UI map, services (long reference).

**If you try to run it:** [docs/SETUP_ENV_AND_RUNTIME.md](docs/SETUP_ENV_AND_RUNTIME.md) + caveats doc above. **Security:** [docs/SECURITY_OPERATIONS.md](docs/SECURITY_OPERATIONS.md).

---

## Features

### For readers and analysts

- **Domain dashboards** — Politics, Finance, Science & Technology with articles, storylines, and topics.
- **Storylines** — Evolving clusters of coverage with editorial narratives, timelines, and automation.
- **Entity dossiers** — One place per person or organization: who they are, positions, and related claims.
- **Tracked events** — Time-bounded happenings with chronicles and editorial briefings.
- **Daily and weekly briefings** — Editorial-first summaries and digests.
- **Finance** — Market data, commodity views, analysis tasks with evidence provenance, and research topics.

### For operators

- **RSS management** — Add, edit, and trigger collection per domain.
- **Pipeline and health** — Monitor system health, pipeline status, orchestrator, and alerts.
- **Entity resolution** — Canonical entities, aliases, merge/split, cross-domain linking.
- **Processed documents** — Ingest and process PDFs (e.g. CRS, GAO, arXiv) into the intelligence layer.

### Technical highlights

- **v8 collect-then-analyze** — Collection runs on an interval; between cycles an ordered analysis pipeline runs (context sync → extraction → intelligence → synthesis → editorial) with time budgets.
- **Full-history awareness** — Storyline discovery and synthesis use 7–30 day windows and combine articles, PDFs, topics, claims, and dossiers with source diversity.
- **Entity resolution** — Disambiguation, alias population, auto-merge, role-word decouple, cross-domain linking.
- **Fact verification** — Multi-source corroboration, contradiction detection, scheduled verification.
- **Data cleanliness** — Routine intelligence cleanup and entity decouple as part of the pipeline.

---

## How to Use

### Quick start

```bash
./start_system.sh        # Start API, frontend, Redis
./status_system.sh       # Check all services
# Open http://localhost:3000
```

- **Web UI:** http://localhost:3000  
- **API docs:** http://localhost:8000/docs (may be disabled when `NEWS_INTEL_ENV=production` — see [docs/SECURITY_OPERATIONS.md](docs/SECURITY_OPERATIONS.md))  
- **Health:** http://localhost:8000/api/system_monitoring/health  

See [Setup, environment, and runtime](docs/SETUP_ENV_AND_RUNTIME.md) for installation and configuration.

### Using the web interface

1. **Choose a domain** — Politics, Finance, or Science & Technology from the top navigation.
2. **Dashboard** — Overview of recent activity, storylines, and top entities for that domain.
3. **Articles** — Browse and search articles; view analysis and entities.
4. **Storylines** — Open a storyline for timeline, narrative, and editorial document.
5. **Investigate** — Entity dossiers (by name or ID), tracked events, processed documents, narrative threads.
6. **Monitor** — System health, pipeline status, phase timeline (including claims_to_facts), domain synthesis & enrichment card, orchestrator dashboard, realtime activity.
7. **Briefings** — Daily and weekly briefings and feedback.

### Using the API

All endpoints use the `/api` prefix (no version in path). Domain-scoped routes use `{domain}` = `politics`, `finance`, or `science-tech`.

Examples:

- `GET /api/{domain}/articles` — List articles.
- `GET /api/{domain}/storylines` — List storylines.
- `GET /api/entity_profiles` — List entity profiles.
- `GET /api/tracked_events` — List tracked events.
- `GET /api/system_monitoring/health` — System health.

Full reference: [API Reference](docs/API_REFERENCE.md). Interactive docs: http://localhost:8000/docs .

---

## Architecture

| Layer     | Technology                    | Location / port  |
|----------|-------------------------------|------------------|
| Frontend | React 18, TypeScript, Vite, MUI v5 | `web/` (3000)    |
| Backend  | Python 3, FastAPI, uvicorn    | `api/` (8000)    |
| Database | PostgreSQL (domain + intelligence schemas) | Widow (5432)  |
| Finance  | SQLite + ChromaDB            | `data/finance/`  |
| Cache    | Redis (optional)             | Local / systemd if enabled |
| LLM      | Ollama (Llama 3.1 8B, Mistral 7B) | Local (11434) |

**Three-machine layout (typical):** Primary (API, frontend, Ollama, Redis) · Widow (PostgreSQL, RSS worker, backups) · NAS (optional storage).

---

## Project documentation

**Reviewers:** [docs/CODEBASE_MAP.md](docs/CODEBASE_MAP.md), [docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md](docs/PIPELINE_AND_ORDER_OF_OPERATIONS.md), [docs/CODE_REVIEW_AND_RUN_CAVEATS.md](docs/CODE_REVIEW_AND_RUN_CAVEATS.md).

**Start here**

- **[Documentation index](docs/DOCS_INDEX.md)** — Full list of docs.
- **[System overview](docs/SYSTEM_OVERVIEW.md)** — What the system is and how it works (high level); archived deep narrative: [PROJECT_OVERVIEW (archive)](docs/_archive/retired_root_docs_2026_03/PROJECT_OVERVIEW.md).
- **[Architecture and operations](docs/ARCHITECTURE_AND_OPERATIONS.md)** — Deployment, DB, Widow, troubleshooting.

**Reference**

- **[Database](docs/DATABASE.md)** — Schema and data I/O.
- **[API reference](docs/API_REFERENCE.md)** — Endpoints and integrations.
- **[Setup and runtime](docs/SETUP_ENV_AND_RUNTIME.md)** — Installation, Ollama, GPU, `.env`.
- **[Security operations](docs/SECURITY_OPERATIONS.md)** — Exposure, CORS, secrets, hardening.
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** — Common issues and fixes.

**Standards and design**

- **[Coding style](docs/CODING_STYLE_GUIDE.md)** — Code conventions.
- **[Core architecture principles](docs/CORE_ARCHITECTURE_PRINCIPLES.md)** — Design invariants.
- **[AGENTS.md](AGENTS.md)** — Terminology and entry points for AI assistants.

**Planning and development history** are in [docs/archive/planning/](docs/archive/planning/) for historic reference.

---

## System requirements

- **PostgreSQL** reachable from the app (typically Widow; see [ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md))  
- **Python 3.10+** with `uv` (see [SETUP_ENV_AND_RUNTIME.md](docs/SETUP_ENV_AND_RUNTIME.md))  
- **Node.js** for the Vite frontend  
- 8 GB RAM minimum (16 GB recommended for LLM)  
- 20 GB disk space  
- Internet for RSS feeds  
- Ollama with Llama 3.1 8B (or configured model)  

Docker is **not** part of the default stack; an old Compose bundle lives under [`docs/archive/docker_stack/`](docs/archive/docker_stack/) for reference only.

---

## Version

8.0 — Collect-then-analyze pipeline, full-history awareness, entity resolution and decouple, data-cleanliness integration, shareholder-ready documentation.
