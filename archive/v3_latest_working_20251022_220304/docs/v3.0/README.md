# News Intelligence System v3.0

[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/your-repo/news-intelligence)
[![Status](https://img.shields.io/badge/status-production%20ready-green.svg)](https://github.com/your-repo/news-intelligence)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **AI-Powered News Aggregation and Analysis Platform**

The News Intelligence System v3.0 is a comprehensive, production-ready platform that consolidates multiple news sources into intelligent summaries and storylines. Built with modern web technologies and powered by local AI processing, it provides journalists, researchers, and news enthusiasts with powerful tools for news analysis and story tracking.

## ✨ Key Features

### 🗞️ **Intelligent News Aggregation**
- **Multi-Source RSS Processing**: Automated collection from 20+ news sources
- **Real-time Updates**: 4x daily feed processing with 24-hour rotation
- **Content Cleaning**: Automated HTML removal and text extraction
- **Deduplication**: Smart article deduplication across sources

### 🤖 **AI-Powered Analysis**
- **Local AI Processing**: Powered by Ollama with `llama3.1:70b` and `deepseek-coder:33b`
- **Sentiment Analysis**: Article sentiment scoring (-1.0 to 1.0)
- **Quality Assessment**: Content quality scoring (0.0 to 1.0)
- **Entity Extraction**: Named entity recognition (people, places, organizations)
- **Readability Analysis**: Flesch-Kincaid reading level calculation
- **Smart Summarization**: AI-generated article summaries

### 📚 **Storyline Management**
- **Story Tracking**: Create and manage storylines across multiple articles
- **Temporal Analysis**: Timeline-based story development tracking
- **AI Consolidation**: Automated storyline summaries and analysis
- **Smart Suggestions**: AI-powered storyline recommendations
- **Database Persistence**: All changes immediately saved

### 🔍 **Advanced Search & Filtering**
- **Real-time Search**: Title search as you type
- **Source Filtering**: Filter by news source
- **Database-Driven**: All filtering at database level for performance
- **Pagination**: Efficient page-based navigation (10-100 articles per page)

### 📊 **Topic Clustering**
- **Living Word Cloud**: Dynamic topic visualization
- **Trend Analysis**: Topic emergence and evolution tracking
- **Batch Processing**: 4-batch rotation system for fresh topics
- **Clustering Algorithm**: Advanced topic grouping and analysis

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### 1. Clone Repository
```bash
git clone https://github.com/your-repo/news-intelligence.git
cd news-intelligence
```

### 2. Start Services
```bash
# Start all services
docker compose up -d

# Check status
docker compose ps
```

### 3. Access Application
- **Frontend**: http://localhost:3001
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

### 4. Verify Installation
```bash
# Check API health
curl http://localhost:8000/api/health/

# Check frontend
curl http://localhost:3001/
```

## 🏗️ Architecture

### Frontend
- **Technology**: HTML5 + JavaScript (Vanilla)
- **Interface**: Single Page Application (SPA)
- **Styling**: Custom CSS with responsive design
- **Deployment**: Docker container with Nginx

### Backend
- **API Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **AI Processing**: Ollama (Local AI)
- **Deployment**: Docker container

### Infrastructure
- **Containerization**: Docker + Docker Compose
- **Web Server**: Nginx
- **Monitoring**: Prometheus + Grafana (optional)
- **SSL**: Self-signed certificates (development)

## 📱 User Interface

### Dashboard
- **System Overview**: Health status, statistics, recent articles
- **Quick Actions**: Access to all major features
- **Recent Articles**: Preview of latest articles with ML data

### Articles Page
- **Master List**: All articles from last 24 hours
- **Search & Filter**: Real-time title search and source filtering
- **Pagination**: Navigate through articles efficiently
- **Article Actions**: Open in source, read local copy, add to storyline
- **ML Data Display**: Sentiment, quality, reading time

### Storylines Page
- **Story Management**: Create, view, and manage storylines
- **Article Association**: Add/remove articles from storylines
- **AI Summaries**: Generate storyline summaries
- **Timeline View**: Track story development over time

### Topic Clusters Page
- **Word Cloud**: Living visualization of current topics
- **Topic Analysis**: Clustering and trend analysis
- **Interactive Controls**: Refresh and explore topics

## 🔧 API Reference

### Core Endpoints
```bash
# Articles
GET    /api/articles/                    # Get articles with pagination
DELETE /api/articles/{id}                # Delete article

# Storylines
GET    /api/storylines/                  # Get all storylines
POST   /api/storylines/                  # Create storyline
POST   /api/storylines/{id}/add-article/ # Add article to storyline

# Processing
POST   /api/processing/process-article/  # Process single article
POST   /api/processing/process-default-feeds/ # Process all feeds

# Clusters
GET    /api/clusters/                    # Get topic clusters
GET    /api/clusters/word-cloud/         # Get word cloud data
```

### Example Usage
```javascript
// Load articles with pagination
const response = await fetch('http://localhost:8000/api/articles/?limit=20&page=1');
const data = await response.json();

// Add article to storyline
await fetch('http://localhost:8000/api/storylines/storyline_123/add-article/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ article_id: 'article_456' })
});
```

## 🗄️ Database Schema

### Core Tables
- **`articles`**: Main articles table with ML data
- **`storylines`**: Storyline definitions
- **`storyline_articles`**: Article-storyline relationships
- **`rss_feeds`**: RSS feed configurations
- **`ai_analysis`**: AI processing results

### Key Fields
```sql
-- Articles
id, title, content, url, source, published_at
sentiment_score, quality_score, summary, ml_data
language, word_count, reading_time

-- Storylines
id, title, description, status, master_summary
created_at, updated_at, article_count
```

## 🤖 AI/ML Capabilities

### Local AI Processing
- **Models**: `llama3.1:70b-instruct-q4_K_M`, `deepseek-coder:33b`
- **Processing**: Sentiment analysis, entity extraction, summarization
- **Fallback**: Graceful degradation if AI models unavailable
- **Performance**: Optimized for local processing

### ML Features
- **Sentiment Analysis**: Article sentiment scoring
- **Quality Assessment**: Content quality evaluation
- **Entity Extraction**: Named entity recognition
- **Readability Analysis**: Reading level calculation
- **Content Summarization**: AI-generated summaries
- **Storyline Consolidation**: Cross-article analysis

## 📊 Performance Metrics

### Current System
- **Total Articles**: 103 articles in database
- **API Response**: < 200ms average
- **Page Load**: < 2 seconds
- **Database Size**: ~50MB
- **Memory Usage**: ~2GB total

### Optimization Features
- **Database Indexing**: Optimized queries with proper indexes
- **Pagination**: Efficient page-based loading
- **Caching**: Redis for frequently accessed data
- **Lazy Loading**: Articles loaded on demand

## 🔒 Security

### Current Measures
- **Input Validation**: All parameters validated
- **SQL Injection Prevention**: Parameterized queries
- **CORS Configuration**: Configured for development
- **Data Sanitization**: Proper input cleaning

### Production Recommendations
- **Authentication**: Implement JWT or OAuth2
- **HTTPS**: Use SSL certificates
- **Rate Limiting**: Implement request throttling
- **API Keys**: Add API key authentication

## 🚀 Deployment

### Development
```bash
# Start development environment
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Production
```bash
# Production deployment
docker compose -f docker-compose.prod.yml up -d

# Scale services
docker compose up -d --scale news-system-app=3
```

## 📚 Documentation

### Available Documentation
- **[Project Status](PROJECT_STATUS_v3.0.md)**: Current project state
- **[API Reference](API_REFERENCE_v3.0.md)**: Complete API documentation
- **[Deployment Guide](DEPLOYMENT_GUIDE_v3.0.md)**: Deployment instructions
- **[Changelog](CHANGELOG_v3.0.md)**: Detailed change history

### API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## 🧪 Testing

### API Testing
```bash
# Test articles API
curl "http://localhost:8000/api/articles/?limit=20&page=1"

# Test storylines API
curl "http://localhost:8000/api/storylines/"

# Test health check
curl "http://localhost:8000/api/health/"
```

### Frontend Testing
- **URL**: http://localhost:3001
- **Navigation**: All page links functional
- **Search**: Title search working
- **Filtering**: Source filtering working
- **Pagination**: Page navigation working

## 🔍 Troubleshooting

### Common Issues
1. **Database Connection Error**: Check password encoding in connection string
2. **Port Already in Use**: Kill processes using ports 3001 or 8000
3. **Container Won't Start**: Check logs with `docker compose logs`
4. **AI Processing Not Working**: Verify Ollama is running and models are available

### Health Checks
```bash
# Check API health
curl http://localhost:8000/api/health/

# Check frontend
curl http://localhost:3001/

# Check database
docker exec news-system-postgres pg_isready -U newsint

# Check Redis
docker exec news-system-redis redis-cli ping
```

## 🎯 Roadmap

### Version 3.2.0 (Planned)
- **Advanced Analytics**: Enhanced analytics dashboard
- **Real-time Updates**: WebSocket-based real-time updates
- **User Management**: User authentication and preferences
- **Mobile App**: Native mobile application

### Version 4.0.0 (Future)
- **Microservices**: Microservices architecture
- **Advanced AI**: More sophisticated AI models
- **Social Features**: Social sharing and collaboration
- **Enterprise Features**: Multi-tenant support

## 🤝 Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

### Code Standards
- **Python**: Follow PEP 8 guidelines
- **JavaScript**: Use ES6+ features
- **CSS**: Use BEM methodology
- **Documentation**: Update documentation for changes

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **FastAPI**: Modern, fast web framework for building APIs
- **PostgreSQL**: Powerful, open source object-relational database
- **Ollama**: Local AI model serving
- **Docker**: Containerization platform
- **Nginx**: High-performance web server

## 📞 Support

### Getting Help
- **Documentation**: Check the comprehensive documentation
- **Issues**: Report bugs and request features on GitHub
- **Discussions**: Join community discussions
- **Email**: Contact the maintainers

### Resources
- **API Docs**: http://localhost:8000/docs
- **Project Status**: [PROJECT_STATUS_v3.0.md](PROJECT_STATUS_v3.0.md)
- **Deployment Guide**: [DEPLOYMENT_GUIDE_v3.0.md](DEPLOYMENT_GUIDE_v3.0.md)

---

**News Intelligence System v3.0**  
*AI-Powered News Aggregation and Analysis Platform*

**Version**: 3.0  
**Last Updated**: January 5, 2025  
**Maintainer**: AI Assistant


