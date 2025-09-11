# RSS Feed Management System v3.0

## Overview

The RSS Feed Management System is a comprehensive solution for curating, filtering, and managing news content from RSS feeds. It ensures only high-quality political, economic, global, and technical events are included while filtering out pop culture, sports, and entertainment content.

## Features

### 1. Feed Registry
- **Tier-based Management**: Feeds are categorized into tiers (1=wire services, 2=institutions, 3=specialized)
- **Priority System**: Processing priority from 1 (highest) to 10 (lowest)
- **Category Organization**: Feeds organized by categories (politics, economy, tech, climate, etc.)
- **Comprehensive Metadata**: Language, country, description, custom headers, and filtering rules

### 2. Feed Fetcher
- **Async Processing**: High-performance async RSS fetching with concurrency control
- **Configurable Intervals**: Customizable update frequencies per feed
- **Error Handling**: Robust error handling with retry mechanisms
- **Rate Limiting**: Respectful fetching with configurable delays

### 3. Multi-Layer Filtering Pipeline
- **Category Filtering**: Whitelist-based category filtering
- **Keyword Blacklisting**: Configurable keyword blacklists for different content types
- **URL Pattern Matching**: Include/exclude patterns for URL filtering
- **NLP Classification**: Local zero-shot classification using HuggingFace transformers
- **Content Quality Scoring**: Automated quality assessment

### 4. Advanced Deduplication
- **Similarity Detection**: Multiple algorithms for detecting duplicate content
- **Clustering**: Groups similar articles into clusters
- **Canonical Management**: Maintains canonical versions of articles
- **Algorithm Support**: Content similarity, title similarity, URL similarity

### 5. Metadata Enrichment
- **Language Detection**: Automatic language detection and translation
- **Entity Extraction**: Named entity recognition for people, organizations, locations
- **Geography Tagging**: Automatic geographical entity extraction
- **Sentiment Analysis**: Basic sentiment scoring
- **Quality Assessment**: Automated quality scoring based on multiple factors

### 6. Monitoring & Metrics
- **Prometheus Integration**: Comprehensive metrics collection
- **Grafana Dashboards**: Real-time monitoring dashboards
- **Performance Tracking**: Response times, success rates, error tracking
- **Health Monitoring**: System health scores and alerts

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   RSS Feeds     │───▶│  Feed Fetcher    │───▶│  Filtering      │
│   Registry      │    │  Service         │    │  Pipeline       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Monitoring    │◀───│  Deduplication   │◀───│  Metadata       │
│   & Metrics     │    │  Service         │    │  Enrichment     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   Articles       │
                       │   Database       │
                       └──────────────────┘
```

## API Endpoints

### Feed Management
- `GET /api/rss/feeds` - List feeds with filtering
- `POST /api/rss/feeds` - Create new feed
- `PUT /api/rss/feeds/{id}` - Update feed
- `DELETE /api/rss/feeds/{id}` - Delete feed
- `GET /api/rss/feeds/{id}/stats` - Get feed statistics

### Article Management
- `GET /api/rss/articles` - Query articles with filtering
- `POST /api/rss/feeds/fetch` - Trigger feed fetching
- `POST /api/rss/feeds/{id}/fetch` - Fetch specific feed

### Filtering & Processing
- `GET /api/rss/filtering/config` - Get filtering configuration
- `PUT /api/rss/filtering/config` - Update filtering rules
- `POST /api/rss/deduplication/detect` - Trigger duplicate detection
- `POST /api/rss/enrichment/batch` - Trigger metadata enrichment

### Monitoring
- `GET /api/rss/monitoring/metrics` - Get comprehensive metrics
- `GET /api/rss/monitoring/prometheus` - Get Prometheus metrics
- `GET /api/rss/health` - Health check

## Configuration

### Feed Configuration
```json
{
  "name": "BBC News",
  "url": "https://feeds.bbci.co.uk/news/rss.xml",
  "tier": 2,
  "priority": 3,
  "category": "news",
  "language": "en",
  "country": "UK",
  "update_frequency": 30,
  "max_articles": 50,
  "tags": ["international", "breaking"],
  "custom_headers": {
    "User-Agent": "News Intelligence Bot/1.0"
  },
  "filters": {
    "exclude_categories": ["sports", "entertainment"]
  }
}
```

### Filtering Configuration
```json
{
  "keyword_blacklist": {
    "entertainment": ["celebrity", "oscars", "grammy", "hollywood"],
    "sports": ["nfl", "nba", "mlb", "soccer", "olympics"],
    "lifestyle": ["fashion", "beauty", "tiktok", "influencer"]
  },
  "category_whitelist": {
    "politics": ["election", "government", "policy", "congress"],
    "economy": ["market", "economy", "financial", "business"],
    "technology": ["tech", "innovation", "ai", "cybersecurity"]
  },
  "url_patterns": {
    "include_patterns": ["/politics/", "/economy/", "/tech/", "/world/"],
    "exclude_patterns": ["/sports/", "/entertainment/", "/lifestyle/"]
  }
}
```

## Database Schema

### Core Tables
- `rss_feeds` - Feed registry with metadata
- `articles` - Processed articles with enrichment data
- `feed_performance_metrics` - Daily performance statistics
- `duplicate_pairs` - Detected duplicate relationships
- `feed_filtering_rules` - Individual feed filtering rules
- `global_filtering_config` - Global filtering configuration

### Key Fields
- **Feed Tier**: 1=wire services, 2=institutions, 3=specialized
- **Priority**: 1=highest, 10=lowest processing priority
- **Categories**: JSON array of detected categories
- **Geography**: JSON array of geographical entities
- **Entities**: JSON array of named entities
- **Quality Score**: 0.0-1.0 quality assessment
- **Sentiment Score**: -1.0 to 1.0 sentiment analysis

## Monitoring

### Prometheus Metrics
- `rss_feeds_total` - Total feeds by status and tier
- `rss_feed_success_rate` - Success rate per feed
- `rss_feed_response_time_seconds` - Response time distribution
- `articles_total` - Articles processed by status
- `articles_filtered_total` - Articles filtered by type
- `articles_duplicates_total` - Duplicates found by algorithm
- `processing_duration_seconds` - Processing time by operation
- `system_health_score` - Overall system health
- `errors_total` - Error count by type and component

### Grafana Dashboard
The system includes a comprehensive Grafana dashboard (`rss-ingestion-dashboard.json`) with:
- Feed status overview
- Success rate monitoring
- Article processing trends
- Response time analysis
- Filtering statistics
- Duplicate detection performance
- System health monitoring
- Error rate tracking

## Installation & Setup

### Prerequisites
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install additional ML libraries (optional)
pip install transformers sentence-transformers spacy langdetect googletrans

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Database Migration
```sql
-- Run the enhanced RSS feed registry migration
\i api/database/migrations/013_enhanced_rss_feed_registry.sql
```

### Configuration
1. Update database connection settings
2. Configure filtering rules in `global_filtering_config`
3. Add RSS feeds to the registry
4. Set up Prometheus and Grafana for monitoring

## Usage Examples

### Adding a New Feed
```python
from services.enhanced_rss_service import EnhancedRSSService, FeedConfig

rss_service = EnhancedRSSService()

feed_config = FeedConfig(
    name="Reuters World News",
    url="https://feeds.reuters.com/reuters/worldNews",
    tier=1,  # Wire service
    priority=1,  # Highest priority
    category="world",
    language="en",
    country="UK"
)

result = await rss_service.create_feed(feed_config)
```

### Triggering Feed Fetching
```python
from services.rss_fetcher_service import fetch_all_rss_feeds

# Fetch all active feeds
result = await fetch_all_rss_feeds(max_concurrent=5)
print(f"Processed {result['articles_processed']} articles")
```

### Running Duplicate Detection
```python
from services.deduplication_service import get_deduplication_service

dedup_service = await get_deduplication_service()
result = await dedup_service.detect_duplicates(time_window_hours=24)
print(f"Found {result['duplicates_found']} duplicates")
```

## Performance Considerations

### Concurrency
- Default: 5 concurrent feed fetchers
- Configurable per deployment
- Rate limiting to respect source servers

### Memory Usage
- Sentence transformers: ~500MB for similarity detection
- spaCy model: ~100MB for entity extraction
- Configurable batch sizes for processing

### Database Optimization
- Indexed on frequently queried fields
- Partitioned tables for large datasets
- Connection pooling for high concurrency

## Troubleshooting

### Common Issues
1. **Feed Fetching Failures**: Check network connectivity and feed URLs
2. **High Memory Usage**: Reduce batch sizes or disable ML features
3. **Slow Processing**: Increase concurrency or optimize database queries
4. **Filtering Issues**: Review and update filtering configuration

### Monitoring
- Check Prometheus metrics for system health
- Review Grafana dashboards for trends
- Monitor database performance and connection counts
- Set up alerts for critical metrics

## Security Considerations

### Data Protection
- No external API calls for content processing
- All ML models run locally
- Sensitive data encrypted in transit and at rest

### Rate Limiting
- Respectful fetching with delays
- Configurable rate limits per feed
- User-Agent identification for transparency

### Access Control
- API authentication required for management endpoints
- Read-only access for monitoring endpoints
- Audit logging for all operations

## Future Enhancements

### Planned Features
- Real-time feed validation
- Advanced ML-based content scoring
- Multi-language support improvements
- Enhanced entity linking
- Custom classification models
- Advanced analytics and reporting

### Scalability
- Horizontal scaling support
- Microservices architecture
- Container orchestration
- Cloud deployment options

## Support

For issues, questions, or contributions:
1. Check the troubleshooting section
2. Review the API documentation
3. Examine the monitoring dashboards
4. Create an issue with detailed logs and metrics




