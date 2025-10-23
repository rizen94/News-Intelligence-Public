# Quick Reference Guide - News Intelligence System

## Essential Commands

### System Management
```bash
# Start system
docker compose up -d

# Stop system
docker compose down

# Check status
docker compose ps

# View logs
docker compose logs -f [service]
```

### Key Directories
- **Main Project**: `/home/pete/Documents/projects/Projects/News Intelligence`
- **API Backend**: `api/`
- **Web Frontend**: `web/`
- **Documentation**: `docs/consolidated/`
- **Scripts**: `scripts/consolidated/`

### Critical Files
- **Docker Compose**: `docker-compose.yml`
- **Environment**: `.env`
- **API Main**: `api/main.py`
- **Web App**: `web/src/App.tsx`
- **Nginx Config**: `web/nginx.conf`

## API Endpoints

### Core Endpoints
- `GET /api/health/` - System health
- `GET /api/articles/` - List articles
- `GET /api/rss-feeds/` - List RSS feeds
- `GET /api/storylines/` - List storylines
- `GET /api/ml-monitoring/status/` - ML status

### Search and Filtering
- `GET /api/articles/?search=term` - Search articles
- `GET /api/articles/?source=BBC` - Filter by source
- `GET /api/articles/?category=Politics` - Filter by category

## Frontend Pages
- **Dashboard**: `http://localhost/dashboard`
- **Articles**: `http://localhost/articles`
- **Storylines**: `http://localhost/storylines`
- **RSS Feeds**: `http://localhost/rss-feeds`
- **Monitoring**: `http://localhost/monitoring`
- **Intelligence**: `http://localhost/intelligence`

## Troubleshooting

### Common Issues
1. **500 Errors**: Check nginx configuration and React build
2. **API Timeouts**: Check API container logs
3. **Database Issues**: Check PostgreSQL container status
4. **Frontend Loading**: Check React build and static files

### Log Locations
- **API Logs**: `docker compose logs api`
- **Web Logs**: `docker compose logs web`
- **Database Logs**: `docker compose logs postgres`

## Development

### Adding New Features
1. Update API routes in `api/routes/`
2. Update frontend components in `web/src/pages/`
3. Update documentation in `docs/consolidated/`
4. Test with `docker compose up --build`

### Git Workflow
- **Branch**: `production-rtx5090-optimized`
- **Commit changes**: `git add . && git commit -m "description"`
- **Check status**: `git status`
