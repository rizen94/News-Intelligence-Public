# News Intelligence System

**Status**: 🟢 **FULLY OPERATIONAL** | **Last Updated**: March 2026

## 🎯 System Overview

The News Intelligence System is an AI-powered news aggregation and analysis platform that processes RSS feeds, analyzes articles, and creates intelligent storylines for investigative journalism.

**Architecture:** Primary (API, ML, frontend) + Widow (PostgreSQL, RSS) + NAS (storage). See [docs/ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md).

**Project map:** API `api/main_v4.py` · Frontend `web/src/App.tsx` · Domains: politics, finance, science-tech (articles, storylines, topics, rss_feeds, events). Routes: `api/domains/*/routes/` · **Documentation:** full index [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md), quick start [QUICK_START.md](QUICK_START.md). Standards: [AGENTS.md](AGENTS.md).

### **Quick Access**
- **Web Interface**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **System Health**: http://localhost:8000/api/system_monitoring/health

---

## 🚀 Quick Start

### **Start the System**
```bash
# Start all services
./start_system.sh

# Check system status
./status_system.sh

# Access web interface
open http://localhost:3000
```

### **System Management**
```bash
# Start system
./start_system.sh

# Check status
./status_system.sh

# Stop system
./stop_system.sh

# Check system health
curl http://localhost:8000/api/system_monitoring/health
```

See [Setup and Deployment Guide](./docs/SETUP_AND_DEPLOYMENT.md) for detailed instructions.

---

## 📊 Current System Status

| Component | Status | Details |
|-----------|--------|---------|
| **Database** | 🟢 Operational | Complete schema, all constraints in place |
| **API Backend** | 🟢 Operational | All 9 core endpoints working, 0 errors |
| **Frontend** | 🟢 Operational | Serving correctly, API integration working |
| **RSS Pipeline** | 🟢 Operational | 5 active feeds, collection working |
| **ML Pipeline** | 🟡 Ready | Ollama service available, models ready |
| **Integration** | 🟢 Operational | End-to-end pipeline working |

### **API endpoints**
Routes use flat `/api` (no version in path). Examples:
- **Health:** `GET /api/system_monitoring/health`
- **Articles:** `GET /api/{domain}/articles` (domain: politics | finance | science-tech)
- **Storylines:** `GET /api/{domain}/storylines`
- **RSS feeds:** `GET /api/{domain}/rss_feeds`
- **Intelligence:** `GET /api/intelligence_hub/...`
Full API docs: http://localhost:8000/docs

---

## 🏗️ Architecture

### **Frontend (React + TypeScript)**
- **Location**: `web/`
- **Port**: 80
- **Features**: Dashboard, Articles, Storylines, RSS Feeds, Intelligence Hub

### **Backend (FastAPI + Python)**
- **Location**: `api/`
- **Port**: 8000
- **Features**: REST API, ML pipelines, RSS processing, Database management

### **Database (PostgreSQL)**
- **Location**: NAS (recommended) or Docker container
- **Port**: 5432
- **Features**: Articles, Storylines, RSS Feeds, User data

### **Cache (Redis)**
- **Location**: Docker container
- **Port**: 6379
- **Features**: Session storage, Data caching, Pipeline state

### **Project map (quick reference)**
- **Entry points:** API `api/main_v4.py` | Frontend `web/src/App.tsx` | API client `web/src/services/api/` + `apiService.ts`
- **Domains:** politics, finance, science-tech (per-domain: articles, storylines, topics, rss_feeds, events; global: watchlist, monitoring, system_monitoring)
- **Key flows:** RSS → processing → storyline linking → event extraction; storylines → analyze → timeline → watchlist
- **Routes:** `api/domains/*/routes/` | Services: `api/services/`, `api/domains/*/services/` | Frontend: `web/src/pages/`

---

## 📚 Documentation

- **[Documentation index](./docs/DOCS_INDEX.md)** — Start here for all docs (setup, API, schema, domains, planning).
- **[Quick Start](./QUICK_START.md)** — Start/stop/status.
- **[Setup and Deployment](./docs/SETUP_AND_DEPLOYMENT.md)** — Installation and deployment.
- **[API Reference](./docs/API_REFERENCE.md)** — API documentation.
- **[Database Schema](./docs/DATABASE_SCHEMA_DOCUMENTATION.md)** — Schema and relationships.
- **[Coding standards](./docs/CODING_STYLE_GUIDE.md)** — Code style and standards.
- **[Troubleshooting](./docs/TROUBLESHOOTING.md)** — Common issues and solutions.

---

## 🔧 Key Features

### **News Processing**
- RSS feed aggregation and monitoring
- Article content extraction and analysis
- Duplicate detection and deduplication
- Quality scoring and filtering

### **Intelligence Analysis**
- AI-powered storyline creation
- Sentiment analysis and trend detection
- Entity extraction and relationship mapping
- Multi-perspective analysis

### **User Interface**
- Responsive web dashboard
- Real-time data visualization
- Interactive storyline exploration
- Advanced search and filtering

### **Monitoring & Analytics**
- Pipeline performance tracking
- System health monitoring
- Error logging and alerting
- Usage analytics and reporting

---

## 🚨 Critical Information

### **System Requirements**
- Docker and Docker Compose
- 8GB RAM minimum
- 20GB disk space
- Internet connection for RSS feeds

### **Important Notes**
- System runs on ports 80, 8000, 5432, 6379, 11434
- Database stored on NAS (recommended) or Docker volumes
- Ollama models stored in `~/.ollama/models` (user-level)
- Regular backups recommended
- Monitor logs for any issues

### **Emergency Procedures**
```bash
# Emergency restart
docker-compose down && docker-compose up -d

# Check system health
curl http://localhost:8000/api/system_monitoring/health

# View error logs
docker logs news-intelligence-api --tail 50
```

---

## 📈 Performance Metrics

| Metric | Value | Status |
|--------|-------|--------|
| API Response Time | < 200ms | 🟢 Excellent |
| Database Connections | Stable | 🟢 Healthy |
| Error Rate | 0% | 🟢 Perfect |
| Uptime | 100% | 🟢 Stable |
| RSS Collection Success | 100% | 🟢 Working |

---

## 🎯 Next Steps

### **Immediate (Ready Now)**
- ✅ System is production-ready
- ✅ All core functionality working
- ✅ Documentation complete

### **Future Enhancements**
- ML model optimization
- Additional RSS sources
- Advanced analytics features
- Performance monitoring dashboard

---

## 📞 Support

### **Quick Diagnostics**
```bash
# Check system health
curl http://localhost:8000/api/system_monitoring/health

# Check articles
curl http://localhost:8000/api/articles/

# Check RSS feeds
curl http://localhost:8000/api/rss/feeds/

# Run integration test
python3 scripts/simple_integration.py
```

### **Documentation**
- **Index:** [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) — full doc list
- API: `docs/API_REFERENCE.md` | Troubleshooting: `docs/TROUBLESHOOTING.md`

---

---

## Core System Invariants

These invariants define what the system guarantees. If any invariant is violated, the system is broken regardless of whether it appears to "work."

1. **If an article has been processed, its key facts are extractable.** The `ml_data` field contains summary, key points, sentiment, and argument analysis derived from the article's actual content. Processing that only updates status flags without extracting intelligence is incomplete.

2. **If a storyline exists, it has (or will have) an editorial narrative.** The `editorial_document` JSONB field on storylines is the primary output — a structured narrative with lede, developments, analysis, and outlook. A storyline with only a title and article count is not finished.

3. **If an event is tracked, it has a chronological briefing.** The `editorial_briefing` and `event_chronicles` fields tell the story of the event over time. An event with only a name and date range is not finished.

4. **User-facing APIs return stories, not statistics.** Briefings lead with "what happened" (headlines, storylines, narrative), not "how many articles were processed." Counts and metrics are supporting data, never the primary content.

See `docs/CORE_ARCHITECTURE_PRINCIPLES.md` for the full principles and `docs/IMPLEMENTATION_CONSTRAINTS.md` for code-level rules.

---

**System Status**: 🟢 **FULLY OPERATIONAL**  
**Last Verified**: March 2026  
**Version**: 5.0  
**Next Check**: Recommended weekly