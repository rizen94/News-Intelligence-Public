# RSS Feed Management System

## Quick Start

1. **Start the API server:**
   ```bash
   cd api
   python main.py
   ```

2. **Start monitoring (optional):**
   ```bash
   ./scripts/manage-rss.sh monitoring
   ```

3. **Test the system:**
   ```bash
   python scripts/test-rss-system.py
   ```

## Management Commands

- `./scripts/manage-rss.sh start` - Start RSS feed fetching
- `./scripts/manage-rss.sh status` - Check system status
- `./scripts/manage-rss.sh feeds` - List all feeds
- `./scripts/manage-rss.sh articles` - Get recent articles
- `./scripts/manage-rss.sh dedupe` - Run duplicate detection
- `./scripts/manage-rss.sh enrich` - Run metadata enrichment

## Monitoring

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **API Health**: http://localhost:8000/api/rss/health

## API Endpoints

- `GET /api/rss/feeds` - List feeds
- `POST /api/rss/feeds` - Create feed
- `GET /api/rss/articles` - Query articles
- `POST /api/rss/feeds/fetch` - Trigger fetching
- `GET /api/rss/monitoring/metrics` - Get metrics

## Configuration

Edit `.env` file to configure:
- Database connection
- RSS settings
- ML features
- Monitoring options

## Documentation

See `docs/RSS_FEED_MANAGEMENT_SYSTEM.md` for detailed documentation.

