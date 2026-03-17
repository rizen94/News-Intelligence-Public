# News Intelligence System

**Status**: Active development | **Version**: 7.0 | **Last Updated**: March 2026

## Overview

News Intelligence is an AI-powered news aggregation and analysis platform. It collects RSS feeds, extracts entities and claims, resolves entities across domains, tracks storylines and events over time, verifies facts against multiple sources, and delivers editorial intelligence. All LLM processing runs locally via Ollama.

**Architecture:** Primary (API, ML, frontend) + Widow (PostgreSQL, RSS) + NAS (storage). See [docs/ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md).

**Project map:** API `api/main_v4.py` · Frontend `web/src/App.tsx` · Domains: politics, finance, science-tech · Routes: `api/domains/*/routes/` · Intelligence: `api/services/` · Full index: [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) · Standards: [AGENTS.md](AGENTS.md).

### Quick Access
- **Web Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **System Health**: http://localhost:8000/api/system_monitoring/health

---

## Quick Start

```bash
./start_system.sh        # Start all services
./status_system.sh       # Check system status
open http://localhost:3000
```

See [Setup and Deployment Guide](./docs/SETUP_AND_DEPLOYMENT.md) for detailed instructions.

---

## What's Built (v7)

### Intelligence Pipeline
- **RSS collection** with full content capture; **v7: full-text enrichment** (trafilatura) for articles with short excerpts
- **v7: Document collection** — government (CRS, GAO, CBO) and academic (arXiv) PDF discovery; **document processing** (pdfplumber) → contexts
- **v7: Auto synthesis** — storyline synthesis and daily briefing synthesis run on schedule
- **v7: Storyline discovery** — AI clusters recent articles and auto-creates storylines (every 4 h)
- **v7: Entity dossiers** — biographic view per entity (narrative, positions, articles, relationships); Top Entities tab by mention count
- ML enrichment (summarization, key points, sentiment, entities); **v7: higher content limits** for entity/topic extraction
- **v7: Backlog logic** — true backlog = work exceeding one batch; interval shortening only when backlog > 0
- **Entity resolution:** disambiguation, alias management, cross-domain linking, auto-merge
- **Context-centric processing:** contexts, claims extraction, pattern discovery, entity profiles/dossiers
- **Event tracking:** tracked events with chronicle builder and editorial briefings
- **Storyline management:** CRUD, RAG discovery, editorial documents, timeline with narrative
- **Fact verification:** multi-source corroboration, contradiction detection, source reliability scoring
- **PDF document processing:** download, parse (pdfplumber), section/entity/findings extraction
- **Content synthesis:** domain/storyline/event/entity scoped intelligence aggregation
- **Briefings:** editorial-first daily/weekly briefings with LLM lead generation

### Finance Domain
- **Analysis orchestrator:** Gold/FRED/EDGAR refresh, LLM analysis with evidence provenance
- **Market data:** Commodity dashboard, market patterns, corporate announcements
- **Evidence collection:** RSS-derived news context integrated into analysis prompts

### Frontend
- **Domain routing:** `/:domain/dashboard`, articles, storylines, topics, RSS feeds
- **Investigate:** Entity profiles, canonical entity management, event detail, processed documents, narrative threads
- **Monitor:** System health, pipeline status, orchestrator dashboard, realtime activity
- **Briefings:** Editorial-first sections with intelligence narrative
- **Finance:** Analysis submission/results, evidence explorer, commodity dashboard

---

## Architecture

| Layer | Technology | Location |
|-------|------------|----------|
| Frontend | React 18, TypeScript, Vite, MUI v5 | `web/` (port 3000) |
| Backend | Python 3, FastAPI, uvicorn | `api/` (port 8000) |
| Database | PostgreSQL (per-domain + intelligence schemas) | Widow (port 5432) |
| Finance DB | SQLite (market, evidence, state) + ChromaDB | `data/finance/` |
| Cache | Redis | Docker (port 6379) |
| LLM | Ollama (Llama 3.1 8B, Mistral 7B) | Local (port 11434) |

### API Structure

Routes use flat `/api` prefix (no version in path):

| Area | Pattern | Examples |
|------|---------|----------|
| Domain content | `/api/{domain}/...` | articles, feeds, storylines, topics |
| Intelligence | `/api/entities/...`, `/api/tracked_events/...` | resolve, canonical, positions |
| Synthesis | `/api/synthesis/...` | domain, storyline, event, entity |
| Verification | `/api/verification/...` | corroborate, contradictions, batch |
| Finance | `/api/{domain}/finance/...` | analyze, tasks, evidence, gold |
| Monitoring | `/api/system_monitoring/...` | health, pipeline, metrics |
| Orchestrator | `/api/orchestrator/...` | status, dashboard, decision_log |

---

## Core System Invariants

These invariants define what the system guarantees. If any invariant is violated, the system is broken regardless of whether it appears to "work."

1. **If an article has been processed, its key facts are extractable.** The `ml_data` field contains summary, key points, sentiment, and argument analysis derived from the article's actual content.

2. **If a storyline exists, it has (or will have) an editorial narrative.** The `editorial_document` JSONB field is the primary output — a structured narrative with lede, developments, analysis, and outlook.

3. **If an event is tracked, it has a chronological briefing.** The `editorial_briefing` and `event_chronicles` fields tell the story of the event over time.

4. **User-facing APIs return stories, not statistics.** Briefings lead with "what happened" (headlines, storylines, narrative), not "how many articles were processed."

See `docs/CORE_ARCHITECTURE_PRINCIPLES.md` for the full principles and `docs/IMPLEMENTATION_CONSTRAINTS.md` for code-level rules.

---

## Documentation

- **[Documentation index](./docs/DOCS_INDEX.md)** — Start here for all docs
- **[Project scope & status](./docs/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md)** — Full scope view with v7 status
- **[Capabilities brief](./docs/PROJECT_CAPABILITIES_BRIEF.md)** — Quick technical orientation
- **[Setup and Deployment](./docs/SETUP_AND_DEPLOYMENT.md)** — Installation and deployment
- **[Coding standards](./docs/CODING_STYLE_GUIDE.md)** — Code style and conventions
- **[Architecture principles](./docs/CORE_ARCHITECTURE_PRINCIPLES.md)** — Intelligence-first design
- **[Troubleshooting](./docs/TROUBLESHOOTING.md)** — Common issues and solutions

---

## System Requirements
- Docker and Docker Compose
- 8GB RAM minimum (16GB recommended for LLM)
- 20GB disk space
- Internet connection for RSS feeds
- Ollama with Llama 3.1 8B model

## Ports
- Frontend: 3000
- API: 8000
- PostgreSQL: 5432 (Widow) or 5433 (NAS tunnel)
- Redis: 6379
- Ollama: 11434

---

**Version**: 7.0.0 — v7 complete (full-text enrichment, document pipeline, auto synthesis, storyline discovery, entity dossiers, batch-size-aware backlog)
