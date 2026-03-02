# News Intelligence System - File Structure

## **Core Production Files (Base Names)**

### **API Layer**
```
api/
├── main.py                    # Main API entry point
├── app.py                     # FastAPI application (if separate)
├── database.py                # Database configuration
├── routes/
│   ├── articles.py            # Articles API routes
│   ├── rss_feeds.py           # RSS feeds API routes
│   ├── health.py              # Health check routes
│   ├── dashboard.py           # Dashboard routes
│   └── admin.py               # Admin routes
├── schemas/
│   ├── models.py              # Pydantic models
│   └── responses.py           # Response schemas
├── services/
│   ├── article_service.py     # Article business logic
│   ├── rss_service.py         # RSS business logic
│   └── health_service.py      # Health check logic
└── database/
    ├── connection.py          # Database connection
    └── migrations/            # Database migrations
```

### **Frontend Layer**
```
web/
├── index.html                 # Main production frontend
├── api.html                   # API documentation page
├── admin.html                 # Admin interface
└── assets/                    # Static assets
```

### **Configuration Layer**
```
├── docker-compose.yml         # Production Docker setup
├── docker-compose.dev.yml     # Development Docker setup
├── start.sh                   # Production startup script
├── stop.sh                    # Production stop script
├── test.py                    # System test script
└── schema/
    └── unified_schema.json    # Unified schema definition
```

## **Naming Conventions**

### **Core Files (Production Ready)**
- Use simple, clear base names
- No version numbers or descriptive suffixes
- Each file represents the single production version

### **Supporting Files**
- Use descriptive names with purpose
- Include version numbers for documentation
- Clearly indicate development vs production

### **Generated Files**
- Prefix with `generated_` for auto-generated content
- Include timestamp or version in filename
- Clearly marked as temporary/regeneratable

## **File Purpose Matrix**

| File | Purpose | Status |
|------|---------|--------|
| `api/main.py` | API entry point | ✅ Production |
| `api/routes/articles.py` | Articles API | ✅ Production |
| `api/routes/rss_feeds.py` | RSS API | ✅ Production |
| `api/routes/health.py` | Health checks | ✅ Production |
| `web/index.html` | Main frontend | ✅ Production |
| `web/api.html` | API docs | ✅ Production |
| `web/admin.html` | Admin interface | ✅ Production |
| `docker-compose.yml` | Production setup | ✅ Production |
| `start.sh` | System startup | ✅ Production |
| `stop.sh` | System shutdown | ✅ Production |
| `test.py` | System testing | ✅ Production |

## **Development Workflow**

1. **Core Changes**: Edit base files directly
2. **Schema Changes**: Update `schema/unified_schema.json`
3. **Regeneration**: Run `python3 scripts/generate_from_schema.py`
4. **Testing**: Run `python3 test.py`
5. **Deployment**: Run `./start.sh`

## **File Dependencies**

```
schema/unified_schema.json
    ↓ (generates)
api/schemas/generated_models.py
    ↓ (imported by)
api/routes/articles.py
    ↓ (serves)
web/index.html
```

This structure ensures:
- Clear, unambiguous file names
- Single source of truth for each component
- Easy maintenance and debugging
- Production-ready clarity
