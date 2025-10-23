# News Intelligence System v4.0 - API Architecture Plan

**Document Version**: 1.0  
**Created**: October 22, 2025  
**Status**: 🚧 **IN DEVELOPMENT**  
**Target Release**: Q4 2025

## 🎯 **Executive Summary**

The News Intelligence System v4.0 represents a complete architectural transformation from a monolithic API to a domain-driven, microservice-ready architecture. This plan focuses on business-driven grouping with integrated ML/LLM capabilities, ensuring scalability, maintainability, and future extensibility.

### **Key Objectives**
- **Business-Driven Architecture**: Organize by business domains, not technical layers
- **ML/LLM Integration**: Embed AI capabilities directly into each business domain using local models only
- **Microservice Readiness**: Design for future service decomposition
- **Zero-Downtime Migration**: Maintain full system functionality during transition
- **Hybrid Performance**: Real-time endpoints (<200ms) + batch processing (2000ms+) for complex operations

---

## 🏗️ **Architecture Overview**

### **Current State (v3.0)**
```
api/
├── routes/          # 37 files - technical grouping
├── services/        # 49 files - scattered functionality  
├── modules/         # 36 files - mixed concerns
└── main.py         # Monolithic registration
```

### **Target State (v4.0)**
```
api/
├── domains/                    # Business-driven domains
│   ├── news_aggregation/       # RSS, feeds, collection
│   ├── content_analysis/       # ML, sentiment, entities
│   ├── storyline_management/   # Storylines, timelines
│   ├── intelligence_hub/       # AI insights, predictions
│   ├── user_management/        # Users, preferences, auth
│   └── system_monitoring/      # Health, metrics, logs
├── shared/                     # Cross-cutting concerns
│   ├── database/
│   ├── middleware/
│   ├── utils/
│   ├── exceptions/
│   └── monitoring/
└── main.py                    # Domain orchestration
```

---

## 📋 **Migration Strategy**

### **Phase 1: Foundation (Week 1)**
- [ ] Create shared infrastructure layer
- [ ] Implement base domain classes
- [ ] Set up comprehensive error handling
- [ ] Create monitoring framework

### **Phase 2: Domain Implementation (Week 2-3)**
- [ ] **News Aggregation Domain** - RSS feeds, collection, ingestion
- [ ] **Content Analysis Domain** - ML processing, sentiment, entities
- [ ] **Storyline Management Domain** - Storylines, timelines, narratives
- [ ] **Intelligence Hub Domain** - AI insights, predictions, recommendations

### **Phase 3: Advanced Features (Week 4)**
- [ ] API versioning strategy
- [ ] Performance optimization
- [ ] Comprehensive monitoring
- [ ] Circuit breaker patterns

### **Phase 4: Production Migration (Week 5)**
- [ ] Branch creation (v4.0-dev)
- [ ] Parallel testing
- [ ] Performance validation
- [ ] Production deployment

---

## 🎯 **Business Domain Specifications**

### **Domain 1: News Aggregation**
**Business Purpose**: Collect, ingest, and manage news content from multiple sources

**Core Responsibilities**:
- RSS feed management and monitoring
- Article collection and ingestion
- Source validation and quality control
- Content deduplication and normalization

**ML/LLM Integration**:
- **Content Quality Scoring**: AI-powered quality assessment using local models
- **Source Reliability Analysis**: ML-based source credibility scoring
- **Automatic Categorization**: LLM-powered content classification using Ollama
- **Duplicate Detection**: Advanced ML similarity matching

**API Endpoints**:
- `GET /api/v4/news/feeds` - List all RSS feeds
- `POST /api/v4/news/feeds` - Add new RSS feed
- `GET /api/v4/news/feeds/{id}/articles` - Get articles from feed
- `POST /api/v4/news/ingest` - Manual content ingestion
- `GET /api/v4/news/sources/quality` - Source quality metrics

### **Domain 2: Content Analysis**
**Business Purpose**: Analyze, process, and extract insights from news content

**Core Responsibilities**:
- Sentiment analysis and emotional tone detection
- Entity extraction and relationship mapping
- Content summarization and key point extraction
- Bias detection and perspective analysis

**ML/LLM Integration**:
- **Sentiment Analysis**: Multi-dimensional sentiment scoring using local models
- **Entity Recognition**: Advanced NER with relationship mapping
- **Content Summarization**: LLM-powered abstractive summarization using Ollama Llama 3.1 70B
- **Bias Detection**: AI-powered bias and perspective analysis
- **Topic Modeling**: Unsupervised topic discovery and clustering

**API Endpoints**:
- `POST /api/v4/analysis/sentiment` - Analyze article sentiment
- `POST /api/v4/analysis/entities` - Extract entities and relationships
- `POST /api/v4/analysis/summarize` - Generate content summary
- `POST /api/v4/analysis/bias` - Detect content bias
- `GET /api/v4/analysis/topics` - Get topic clusters

### **Domain 3: Storyline Management**
**Business Purpose**: Create, manage, and evolve narrative storylines from news events

**Core Responsibilities**:
- Storyline creation and evolution
- Timeline generation and management
- Narrative coherence and consistency
- Cross-source story correlation

**ML/LLM Integration**:
- **Storyline Generation**: AI-powered narrative creation using Ollama Llama 3.1 70B
- **Timeline Construction**: ML-based chronological ordering
- **Narrative Coherence**: LLM-powered story consistency checking
- **Cross-Reference Analysis**: AI-powered story correlation
- **Trend Prediction**: ML-based storyline evolution prediction

**API Endpoints**:
- `GET /api/v4/storylines` - List all storylines
- `POST /api/v4/storylines` - Create new storyline
- `GET /api/v4/storylines/{id}/timeline` - Get storyline timeline
- `POST /api/v4/storylines/{id}/evolve` - Evolve storyline with new content
- `GET /api/v4/storylines/{id}/correlations` - Find related storylines

### **Domain 4: Intelligence Hub**
**Business Purpose**: Provide AI-powered insights, predictions, and recommendations

**Core Responsibilities**:
- Predictive analytics and trend forecasting
- Risk assessment and impact analysis
- Recommendation engine for content and storylines
- Advanced AI-powered insights and patterns

**ML/LLM Integration**:
- **Predictive Analytics**: ML-based trend and event prediction using local models
- **Impact Assessment**: AI-powered impact and consequence analysis
- **Recommendation Engine**: Collaborative filtering and content-based recommendations
- **Pattern Recognition**: Advanced AI pattern detection and anomaly identification
- **Strategic Insights**: LLM-powered strategic analysis and recommendations using Ollama

**API Endpoints**:
- `GET /api/v4/intelligence/predictions` - Get trend predictions
- `POST /api/v4/intelligence/impact` - Assess content impact
- `GET /api/v4/intelligence/recommendations` - Get personalized recommendations
- `POST /api/v4/intelligence/analyze` - Deep analysis of content/storylines
- `GET /api/v4/intelligence/patterns` - Discover hidden patterns

### **Domain 5: User Management**
**Business Purpose**: Manage users, preferences, and personalized experiences

**Core Responsibilities**:
- User authentication and authorization
- Preference management and personalization
- User behavior tracking and analytics
- Custom dashboard and notification management

**ML/LLM Integration**:
- **Personalization Engine**: ML-based content personalization using local models
- **Behavior Analysis**: AI-powered user behavior pattern recognition
- **Preference Learning**: Adaptive preference learning and recommendation
- **Custom Dashboards**: AI-powered dashboard customization using Ollama

**API Endpoints**:
- `POST /api/v4/users/auth` - User authentication
- `GET /api/v4/users/preferences` - Get user preferences
- `PUT /api/v4/users/preferences` - Update user preferences
- `GET /api/v4/users/dashboard` - Get personalized dashboard
- `POST /api/v4/users/feedback` - Submit user feedback

### **Domain 6: System Monitoring**
**Business Purpose**: Monitor system health, performance, and operational metrics

**Core Responsibilities**:
- System health monitoring and alerting
- Performance metrics and analytics
- Log aggregation and analysis
- Operational dashboards and reporting

**ML/LLM Integration**:
- **Anomaly Detection**: ML-based system anomaly detection using local models
- **Predictive Maintenance**: AI-powered system health prediction
- **Performance Optimization**: ML-based performance tuning recommendations
- **Intelligent Alerting**: AI-powered alert prioritization and filtering using Ollama

**API Endpoints**:
- `GET /api/v4/monitoring/health` - System health status
- `GET /api/v4/monitoring/metrics` - Performance metrics
- `GET /api/v4/monitoring/logs` - System logs
- `GET /api/v4/monitoring/alerts` - Active alerts
- `POST /api/v4/monitoring/analyze` - Analyze system performance

---

## 🔧 **Technical Implementation Details**

### **Shared Infrastructure**

#### **Base Domain Class**
```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

class BaseDomain(ABC):
    """Base class for all business domains"""
    
    def __init__(self, db: Session):
        self.db = db
        self.router = APIRouter()
        self.services = self._initialize_services()
        self._register_routes()
    
    @abstractmethod
    def _initialize_services(self) -> Dict[str, Any]:
        """Initialize domain-specific services"""
        pass
    
    @abstractmethod
    def _register_routes(self):
        """Register domain-specific routes"""
        pass
    
    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """Return domain health status"""
        pass
```

#### **Error Handling Framework**
```python
class DomainException(Exception):
    """Base exception for domain-specific errors"""
    
    def __init__(self, message: str, domain: str, error_code: str = None):
        self.message = message
        self.domain = domain
        self.error_code = error_code
        super().__init__(message)

class NewsAggregationError(DomainException):
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message, "news_aggregation", error_code)

class ContentAnalysisError(DomainException):
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message, "content_analysis", error_code)
```

#### **Monitoring and Observability**
```python
import time
from functools import wraps
from typing import Callable

def monitor_performance(func: Callable):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            duration = time.time() - start_time
            
            # Log performance metrics
            logger.info(f"Domain call {func.__name__} completed in {duration:.3f}s")
            
            return result
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Domain call {func.__name__} failed after {duration:.3f}s: {e}")
            raise
    return wrapper
```

---

## 📊 **Performance Targets**

### **Response Time Goals (Hybrid Approach)**
- **Real-time Operations**: < 200ms average (health checks, basic queries, simple operations)
- **News Aggregation**: < 150ms average (feed operations, article retrieval)
- **Content Analysis**: < 2000ms average (ML processing, LLM summarization)
- **Storyline Management**: < 2000ms average (timeline generation, basic operations)
- **Intelligence Hub**: < 5000ms average (AI processing, comprehensive analysis)
- **User Management**: < 100ms average (authentication, preferences)
- **System Monitoring**: < 50ms average (health checks, metrics)

### **Scalability Targets**
- **Concurrent Users**: 10,000+
- **API Requests**: 1M+ per day
- **Data Processing**: 100K+ articles per day
- **ML Processing**: 10K+ analyses per day

---

## 🚀 **Migration Timeline**

### **Week 1: Foundation**
- [ ] Create shared infrastructure
- [ ] Implement base classes
- [ ] Set up error handling
- [ ] Create monitoring framework

### **Week 2: Core Domains**
- [ ] News Aggregation Domain
- [ ] Content Analysis Domain
- [ ] Basic ML/LLM integration

### **Week 3: Advanced Domains**
- [ ] Storyline Management Domain
- [ ] Intelligence Hub Domain
- [ ] Advanced AI features

### **Week 4: Supporting Domains**
- [ ] User Management Domain
- [ ] System Monitoring Domain
- [ ] Performance optimization

### **Week 5: Production Ready**
- [ ] API versioning
- [ ] Comprehensive testing
- [ ] Performance validation
- [ ] Production deployment

---

## 📝 **Documentation Standards**

### **Domain Documentation Template**
Each domain will include:
1. **Business Purpose**: Clear business objective
2. **Core Responsibilities**: Key functions and capabilities
3. **ML/LLM Integration**: AI features and capabilities
4. **API Endpoints**: Complete endpoint specification
5. **Data Models**: Schema and data structures
6. **Service Architecture**: Internal service organization
7. **Performance Metrics**: Expected performance characteristics
8. **Dependencies**: External dependencies and integrations

### **Code Documentation Standards**
- Comprehensive docstrings for all classes and methods
- Type hints for all function parameters and returns
- Inline comments for complex business logic
- API endpoint documentation with examples
- Error handling documentation

---

## ✅ **Success Criteria**

### **Technical Success**
- [ ] All domains operational and tested
- [ ] Performance targets met
- [ ] Zero-downtime migration completed
- [ ] Comprehensive monitoring in place

### **Business Success**
- [ ] Improved development velocity
- [ ] Enhanced system maintainability
- [ ] Better AI/ML integration
- [ ] Scalable architecture for future growth

### **Operational Success**
- [ ] Reduced system complexity
- [ ] Improved error handling and debugging
- [ ] Better performance monitoring
- [ ] Enhanced system reliability

---

**Document Status**: 🚧 **IN DEVELOPMENT**  
**Next Review**: Weekly during implementation  
**Approval Required**: Technical Lead, Product Owner  
**Implementation Start**: TBD based on approval
