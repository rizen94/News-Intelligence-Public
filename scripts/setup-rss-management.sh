#!/bin/bash

# =============================================================================
# RSS Feed Management System Setup Script
# =============================================================================
# 
# This script sets up the RSS Feed Management System for News Intelligence v3.0
# It includes database migrations, dependency installation, and configuration
#
# Usage: ./scripts/setup-rss-management.sh
#
# =============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root"
   exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

log_info "Setting up RSS Feed Management System..."
log_info "Project root: $PROJECT_ROOT"

# Change to project directory
cd "$PROJECT_ROOT"

# =============================================================================
# 1. Install Python Dependencies
# =============================================================================
log_info "Installing Python dependencies..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install core dependencies
log_info "Installing core dependencies..."
pip install -r api/requirements.txt

# Install optional ML dependencies
log_info "Installing optional ML dependencies..."
pip install transformers torch spacy langdetect googletrans || log_warning "Some ML dependencies failed to install - continuing with basic features"

# Download spaCy model
log_info "Downloading spaCy English model..."
python -m spacy download en_core_web_sm || log_warning "spaCy model download failed - continuing without advanced NLP features"

log_success "Dependencies installed successfully"

# =============================================================================
# 2. Database Setup
# =============================================================================
log_info "Setting up database..."

# Check if PostgreSQL is running
if ! pg_isready -q; then
    log_error "PostgreSQL is not running. Please start PostgreSQL and try again."
    exit 1
fi

# Run database migrations
log_info "Running database migrations..."
if [ -f "api/database/migrations/013_enhanced_rss_feed_registry.sql" ]; then
    psql -U newsapp -d news_system -f api/database/migrations/013_enhanced_rss_feed_registry.sql
    log_success "Database migration completed"
else
    log_error "Migration file not found: api/database/migrations/013_enhanced_rss_feed_registry.sql"
    exit 1
fi

# =============================================================================
# 3. Configuration Setup
# =============================================================================
log_info "Setting up configuration..."

# Create configuration directory if it doesn't exist
mkdir -p config

# Create environment file if it doesn't exist
if [ ! -f ".env" ]; then
    log_info "Creating .env file..."
    cat > .env << EOF
# Database Configuration
DB_HOST=localhost
DB_NAME=news_system
DB_USER=newsapp
DB_PASSWORD=your_password_here

# RSS Management Configuration
RSS_MAX_CONCURRENT_FETCHERS=5
RSS_DEFAULT_UPDATE_FREQUENCY=30
RSS_DEFAULT_MAX_ARTICLES=50

# ML Configuration
ENABLE_NLP_CLASSIFICATION=true
ENABLE_SENTENCE_TRANSFORMERS=true
ENABLE_LANGUAGE_DETECTION=true
ENABLE_TRANSLATION=true

# Monitoring Configuration
ENABLE_PROMETHEUS_METRICS=true
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
EOF
    log_warning "Please update .env file with your actual database password"
fi

# =============================================================================
# 4. Create Sample Feeds
# =============================================================================
log_info "Creating sample RSS feeds..."

# Create a Python script to add sample feeds
cat > setup_sample_feeds.py << 'EOF'
#!/usr/bin/env python3
"""
Setup sample RSS feeds for the News Intelligence System
"""

import asyncio
import sys
import os

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from services.enhanced_rss_service import EnhancedRSSService, FeedConfig

async def setup_sample_feeds():
    """Setup sample RSS feeds"""
    rss_service = EnhancedRSSService()
    
    # Sample feeds
    sample_feeds = [
        FeedConfig(
            name="BBC World News",
            url="https://feeds.bbci.co.uk/news/world/rss.xml",
            description="BBC World News RSS Feed",
            tier=2,  # Institution
            priority=1,  # High priority
            category="world",
            language="en",
            country="UK",
            update_frequency=30,
            max_articles=50,
            tags=["international", "breaking", "world"]
        ),
        FeedConfig(
            name="Reuters World News",
            url="https://feeds.reuters.com/reuters/worldNews",
            description="Reuters World News RSS Feed",
            tier=1,  # Wire service
            priority=1,  # High priority
            category="world",
            language="en",
            country="UK",
            update_frequency=15,
            max_articles=100,
            tags=["wire", "international", "breaking"]
        ),
        FeedConfig(
            name="TechCrunch",
            url="https://techcrunch.com/feed/",
            description="TechCrunch Technology News",
            tier=3,  # Specialized
            priority=3,  # Medium priority
            category="technology",
            language="en",
            country="US",
            update_frequency=60,
            max_articles=30,
            tags=["technology", "startups", "innovation"]
        ),
        FeedConfig(
            name="Financial Times",
            url="https://www.ft.com/rss/home",
            description="Financial Times Business News",
            tier=2,  # Institution
            priority=2,  # High priority
            category="business",
            language="en",
            country="UK",
            update_frequency=45,
            max_articles=40,
            tags=["business", "finance", "economy"]
        )
    ]
    
    print("Adding sample RSS feeds...")
    
    for feed_config in sample_feeds:
        try:
            result = await rss_service.create_feed(feed_config)
            if "error" in result:
                print(f"Error adding {feed_config.name}: {result['error']}")
            else:
                print(f"Added feed: {feed_config.name}")
        except Exception as e:
            print(f"Error adding {feed_config.name}: {e}")
    
    print("Sample feeds setup completed!")

if __name__ == "__main__":
    asyncio.run(setup_sample_feeds())
EOF

# Run the sample feeds setup
python setup_sample_feeds.py
rm setup_sample_feeds.py

log_success "Sample feeds created successfully"

# =============================================================================
# 5. Create Monitoring Setup
# =============================================================================
log_info "Setting up monitoring..."

# Create Prometheus configuration
mkdir -p monitoring/prometheus
cat > monitoring/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  # - "first_rules.yml"
  # - "second_rules.yml"

scrape_configs:
  - job_name: 'news-intelligence'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/api/rss/monitoring/prometheus'
    scrape_interval: 30s
EOF

# Create Grafana configuration
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/provisioning/datasources

# Create datasource configuration
cat > monitoring/grafana/provisioning/datasources/prometheus.yml << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

# Create dashboard provisioning
cat > monitoring/grafana/provisioning/dashboards/dashboard.yml << 'EOF'
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
EOF

log_success "Monitoring configuration created"

# =============================================================================
# 6. Create Docker Compose for Monitoring
# =============================================================================
log_info "Creating Docker Compose for monitoring..."

cat > docker-compose.monitoring.yml << 'EOF'
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: news-intelligence-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana:latest
    container_name: news-intelligence-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
      - ./api/monitoring/grafana:/var/lib/grafana/dashboards
    depends_on:
      - prometheus

volumes:
  grafana-storage:
EOF

log_success "Docker Compose for monitoring created"

# =============================================================================
# 7. Create Management Scripts
# =============================================================================
log_info "Creating management scripts..."

# Create RSS management script
cat > scripts/manage-rss.sh << 'EOF'
#!/bin/bash

# RSS Management Script for News Intelligence System

case "$1" in
    "start")
        echo "Starting RSS feed fetching..."
        curl -X POST "http://localhost:8000/api/rss/feeds/fetch"
        ;;
    "status")
        echo "Checking RSS feed status..."
        curl -s "http://localhost:8000/api/rss/feeds/stats/overview" | jq .
        ;;
    "feeds")
        echo "Listing RSS feeds..."
        curl -s "http://localhost:8000/api/rss/feeds" | jq .
        ;;
    "articles")
        echo "Getting recent articles..."
        curl -s "http://localhost:8000/api/rss/articles?limit=10" | jq .
        ;;
    "dedupe")
        echo "Running duplicate detection..."
        curl -X POST "http://localhost:8000/api/rss/deduplication/detect"
        ;;
    "enrich")
        echo "Running metadata enrichment..."
        curl -X POST "http://localhost:8000/api/rss/enrichment/batch" -H "Content-Type: application/json" -d '{"article_ids": []}'
        ;;
    "monitoring")
        echo "Starting monitoring services..."
        docker-compose -f docker-compose.monitoring.yml up -d
        ;;
    "stop-monitoring")
        echo "Stopping monitoring services..."
        docker-compose -f docker-compose.monitoring.yml down
        ;;
    *)
        echo "Usage: $0 {start|status|feeds|articles|dedupe|enrich|monitoring|stop-monitoring}"
        exit 1
        ;;
esac
EOF

chmod +x scripts/manage-rss.sh

log_success "Management scripts created"

# =============================================================================
# 8. Create Test Script
# =============================================================================
log_info "Creating test script..."

cat > scripts/test-rss-system.py << 'EOF'
#!/usr/bin/env python3
"""
Test script for RSS Feed Management System
"""

import asyncio
import sys
import os
import json

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'api'))

from services.enhanced_rss_service import EnhancedRSSService
from services.rss_fetcher_service import fetch_all_rss_feeds
from services.deduplication_service import get_deduplication_service
from services.monitoring_service import get_monitoring_service

async def test_rss_system():
    """Test the RSS system components"""
    print("Testing RSS Feed Management System...")
    
    # Test RSS service
    print("\n1. Testing RSS Service...")
    rss_service = EnhancedRSSService()
    
    # Get feeds
    feeds_result = await rss_service.get_feeds(active_only=True)
    print(f"Active feeds: {len(feeds_result.get('feeds', []))}")
    
    # Get stats
    stats_result = await rss_service.get_feed_stats()
    print(f"Total feeds: {stats_result.get('total_feeds', 0)}")
    print(f"Active feeds: {stats_result.get('active_feeds', 0)}")
    
    # Test monitoring service
    print("\n2. Testing Monitoring Service...")
    monitoring_service = await get_monitoring_service()
    metrics = await monitoring_service.get_metrics_summary()
    print(f"Database status: {metrics.get('database', {}).get('active_connections', 'unknown')}")
    
    # Test deduplication service
    print("\n3. Testing Deduplication Service...")
    dedup_service = await get_deduplication_service()
    dedup_stats = await dedup_service.get_deduplication_stats()
    print(f"Total articles: {dedup_stats.get('total_articles', 0)}")
    print(f"Duplicate articles: {dedup_stats.get('duplicate_articles', 0)}")
    
    print("\nRSS system test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_rss_system())
EOF

chmod +x scripts/test-rss-system.py

log_success "Test script created"

# =============================================================================
# 9. Final Setup
# =============================================================================
log_info "Finalizing setup..."

# Create README for RSS management
cat > RSS_MANAGEMENT_README.md << 'EOF'
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
EOF

log_success "Setup completed successfully!"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================================="
echo "RSS FEED MANAGEMENT SYSTEM SETUP COMPLETED"
echo "============================================================================="
echo ""
echo "✅ Dependencies installed"
echo "✅ Database migrated"
echo "✅ Sample feeds created"
echo "✅ Monitoring configured"
echo "✅ Management scripts created"
echo "✅ Test script created"
echo ""
echo "Next steps:"
echo "1. Update .env file with your database password"
echo "2. Start the API server: cd api && python main.py"
echo "3. Test the system: python scripts/test-rss-system.py"
echo "4. Start monitoring: ./scripts/manage-rss.sh monitoring"
echo ""
echo "Documentation: docs/RSS_FEED_MANAGEMENT_SYSTEM.md"
echo "Quick reference: RSS_MANAGEMENT_README.md"
echo ""
echo "============================================================================="


