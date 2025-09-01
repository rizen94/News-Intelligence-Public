# 🏗️ System Architecture - News Intelligence System v3.0

## 🎯 **TECHNICAL DESIGN OVERVIEW**

This document provides a comprehensive technical overview of the News Intelligence System architecture, including system components, data flow, and technical decisions.

---

## 🏛️ **SYSTEM ARCHITECTURE**

### **High-Level Architecture**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Frontend  │    │  Backend API    │    │   Database      │
│   (React)       │◄──►│   (Flask)       │◄──►│  (PostgreSQL)   │
│   Port: 8000    │    │   Port: 8000    │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Monitoring    │    │  RSS Collectors │    │   Data Storage  │
│ (Prometheus +   │    │  (Background    │    │  (Local/NAS)    │
│   Grafana)      │    │   Workers)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Component Overview**
- **Frontend**: React-based web interface with Material-UI
- **Backend**: Flask REST API with modular architecture
- **Database**: PostgreSQL with pgvector for similarity search
- **Monitoring**: Prometheus metrics + Grafana dashboards
- **Storage**: Docker volumes (local) or NAS (production)

---

## 🌐 **FRONTEND ARCHITECTURE**

### **React Application Structure**
```
web/src/
├── components/           # Reusable UI components
│   ├── Layout/          # Main layout and navigation
│   ├── Dashboard/       # Dashboard components
│   ├── ContentPrioritization/  # Priority management
│   └── Breadcrumb/      # Navigation breadcrumbs
├── pages/               # Page-level components
│   ├── Dashboard/       # Main dashboard
│   ├── Articles/        # Article management
│   ├── Clusters/        # Story clustering
│   ├── Entities/        # Entity extraction
│   ├── Sources/         # RSS source management
│   ├── Search/          # Search functionality
│   └── Monitoring/      # System monitoring
├── contexts/            # React context providers
│   └── NewsSystemContext.js  # Global state management
├── services/            # API service layer
│   └── newsSystemService.js  # HTTP client and API calls
└── utils/               # Utility functions
```

### **State Management**
- **React Context**: Global state for system status and data
- **Local State**: Component-specific state management
- **API Integration**: Centralized service layer for backend communication

### **UI Framework**
- **Material-UI (MUI)**: Professional component library
- **Responsive Design**: Mobile-first responsive layout
- **Theme System**: Consistent visual design language
- **Accessibility**: WCAG compliance and keyboard navigation

---

## 🐍 **BACKEND ARCHITECTURE**

### **Flask Application Structure**
```
api/
├── app.py               # Main application entry point
├── requirements.txt     # Python dependencies
├── collectors/          # RSS collection modules
│   ├── rss_collector.py        # Basic RSS collection
│   └── enhanced_rss_collector.py  # Enhanced content extraction
├── modules/             # Core business logic
│   ├── deduplication/   # Content deduplication
│   ├── ingestion/       # Content ingestion pipeline
│   ├── intelligence/    # Content analysis and processing
│   ├── monitoring/      # System monitoring
│   └── prioritization/  # Content prioritization
├── config/              # Configuration management
│   ├── __init__.py      # Configuration initialization
│   └── database.py      # Database configuration
├── scripts/             # Utility scripts
│   ├── utilities/       # Core utility functions
│   └── system_monitor.py  # System monitoring
└── tests/               # Test suite
```

### **API Design Principles**
- **RESTful Design**: Standard HTTP methods and status codes
- **Resource-Oriented**: Clear resource hierarchy and relationships
- **Stateless**: No server-side session state
- **Versioned**: API versioning for future compatibility

### **Core API Endpoints**
```
/api/system/status          # System health and status
/api/dashboard/real         # Dashboard data and metrics
/api/articles               # Article CRUD operations
/api/clusters               # Story cluster management
/api/entities               # Entity extraction results
/api/sources                # RSS source management
/api/search                 # Content search functionality
/api/pipeline/run          # Pipeline execution
/api/prioritization/*      # Content prioritization
/api/metrics/*             # System metrics and monitoring
```

---

## 🗄️ **DATABASE ARCHITECTURE**

### **PostgreSQL Database Design**
```
news_system/
├── articles               # Article content and metadata
├── rss_feeds             # RSS source configuration
├── article_clusters      # Story clustering relationships
├── entities              # Named entity extraction
├── content_priorities    # Priority assignments
├── processing_logs       # System processing history
├── system_metrics        # Performance and health metrics
└── user_preferences      # User configuration settings
```

### **Key Database Features**
- **pgvector Extension**: Vector similarity search for content clustering
- **JSONB Support**: Flexible metadata storage
- **Full-Text Search**: PostgreSQL text search capabilities
- **Connection Pooling**: Efficient database connection management
- **Automatic Backups**: Scheduled backup procedures

### **Database Schema Highlights**
```sql
-- Articles table with full-text search
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT,
    source_id INTEGER REFERENCES rss_feeds(id),
    published_date TIMESTAMP,
    quality_score DECIMAL(3,2),
    priority_level VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Full-text search index
CREATE INDEX articles_content_fts ON articles 
USING gin(to_tsvector('english', title || ' ' || content));

-- Vector similarity index for clustering
CREATE INDEX articles_embedding_idx ON articles 
USING ivfflat (embedding vector_cosine_ops);
```

---

## 🔄 **DATA FLOW ARCHITECTURE**

### **Content Processing Pipeline**
```
RSS Feeds → Collection → Deduplication → Processing → Storage → Analysis
    │           │            │            │          │         │
    ▼           ▼            ▼            ▼          ▼         ▼
Validation  Content      Similarity    Entity    Database   Clustering
  &         Extraction   Detection     Extraction Storage   & Priority
Filtering   & Cleaning   & Removal     & Analysis          Assignment
```

### **Pipeline Stages**

#### **1. Collection Stage**
- **RSS Feed Monitoring**: Regular feed polling and validation
- **Content Extraction**: HTML parsing and text extraction
- **Metadata Processing**: Publication dates, categories, authors
- **Quality Assessment**: Initial content quality scoring

#### **2. Deduplication Stage**
- **Content Hashing**: Generate content fingerprints
- **Similarity Detection**: Vector-based similarity analysis
- **Duplicate Removal**: Eliminate redundant content
- **Version Management**: Track content updates

#### **3. Processing Stage**
- **Language Detection**: Automatic language identification
- **Entity Extraction**: Named entity recognition
- **Content Cleaning**: HTML removal and text normalization
- **Quality Validation**: Content reliability assessment

#### **4. Analysis Stage**
- **Clustering**: Group related articles into story threads
- **Priority Assignment**: Automatic importance scoring
- **Trend Analysis**: Content popularity and relevance
- **Insight Generation**: Automated content insights

---

## 🧠 **INTELLIGENCE MODULES**

### **Content Deduplication Engine**
```python
class DeduplicationEngine:
    def __init__(self):
        self.similarity_threshold = 0.85
        self.vector_model = self.load_vector_model()
    
    def detect_duplicates(self, new_article, existing_articles):
        """Detect duplicate or similar content"""
        new_vector = self.vectorize(new_article)
        
        for existing in existing_articles:
            similarity = self.calculate_similarity(new_vector, existing.vector)
            if similarity > self.similarity_threshold:
                return existing
        
        return None
```

### **Entity Extraction System**
```python
class EntityExtractor:
    def __init__(self):
        self.nlp_model = spacy.load("en_core_web_sm")
        self.entity_types = ["PERSON", "ORG", "GPE", "EVENT"]
    
    def extract_entities(self, text):
        """Extract named entities from text"""
        doc = self.nlp_model(text)
        entities = []
        
        for ent in doc.ents:
            if ent.label_ in self.entity_types:
                entities.append({
                    'text': ent.text,
                    'label': ent.label_,
                    'start': ent.start_char,
                    'end': ent.end_char
                })
        
        return entities
```

### **Content Clustering Algorithm**
```python
class ContentClusterer:
    def __init__(self):
        self.clustering_model = self.load_clustering_model()
        self.min_cluster_size = 3
    
    def cluster_articles(self, articles):
        """Group articles into story clusters"""
        # Vectorize articles
        vectors = [self.vectorize(article) for article in articles]
        
        # Perform clustering
        clusters = self.clustering_model.fit_predict(vectors)
        
        # Group articles by cluster
        cluster_groups = self.group_by_cluster(articles, clusters)
        
        return cluster_groups
```

---

## 📊 **MONITORING ARCHITECTURE**

### **Monitoring Stack Components**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   Prometheus    │    │     Grafana     │
│   Metrics       │───►│   (Collector)   │───►│   (Dashboard)   │
│   (Flask)       │    │   Port: 9090    │    │   Port: 3001    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   System        │    │   Database      │    │   GPU           │
│   Metrics       │    │   Metrics       │    │   Metrics       │
│ (Node Exporter) │    │(PostgreSQL      │    │(NVIDIA GPU      │
│   Port: 9100    │    │ Exporter)       │    │ Exporter)       │
│                 │    │ Port: 9187      │    │ Port: 9445      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Metrics Collection**
- **Application Metrics**: API response times, error rates, throughput
- **System Metrics**: CPU, memory, disk usage, network I/O
- **Database Metrics**: Query performance, connection counts, cache hit rates
- **Custom Metrics**: Business-specific KPIs and content processing stats

### **Alerting System**
```yaml
# Prometheus alert rules
groups:
  - name: system_alerts
    rules:
      - alert: HighCPUUsage
        expr: cpu_usage > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High CPU usage detected
          description: CPU usage is above 80% for 5 minutes
      
      - alert: DatabaseConnectionHigh
        expr: postgres_connections > 80
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: High database connection count
          description: Database connections are above 80
```

---

## 🔒 **SECURITY ARCHITECTURE**

### **Security Layers**
```
┌─────────────────────────────────────────────────────────────┐
│                    Application Layer                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Input         │  │   Rate          │  │   CORS      │ │
│  │ Validation      │  │   Limiting      │  │   Control   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Network Layer                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Docker        │  │   Port          │  │   Firewall  │ │
│  │   Isolation     │  │   Management    │  │   Rules     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Database      │  │   Backup        │  │   Audit     │ │
│  │   Encryption    │  │   Encryption    │  │   Logging   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### **Security Features**
- **Input Validation**: SQL injection and XSS protection
- **Rate Limiting**: API request throttling
- **CORS Control**: Cross-origin resource sharing management
- **Docker Isolation**: Container-based security boundaries
- **Data Encryption**: Encryption at rest and in transit
- **Audit Logging**: Complete access and modification tracking

---

## 📈 **PERFORMANCE ARCHITECTURE**

### **Performance Optimization Strategies**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   Database      │
│   Optimization  │    │   Optimization  │    │   Optimization  │
│                 │    │                 │    │                 │
│ • Code          │    │ • Connection    │    │ • Query         │
│   Splitting     │    │   Pooling       │    │   Optimization  │
│ • Lazy Loading  │    │ • Caching       │    │ • Indexing      │
│ • Bundle        │    │ • Async         │    │ • Partitioning  │
│   Optimization  │    │   Processing    │    │ • Connection    │
└─────────────────┘    └─────────────────┘    │   Pooling       │
                                              └─────────────────┘
```

### **Caching Strategy**
- **Application Cache**: In-memory caching for frequently accessed data
- **Database Cache**: PostgreSQL query result caching
- **CDN Integration**: Static asset delivery optimization
- **Browser Cache**: Client-side caching strategies

### **Database Performance**
```sql
-- Performance optimization queries
-- Create indexes for common queries
CREATE INDEX idx_articles_published_date ON articles(published_date);
CREATE INDEX idx_articles_source_id ON articles(source_id);
CREATE INDEX idx_articles_priority ON articles(priority_level);

-- Partition large tables by date
CREATE TABLE articles_2024 PARTITION OF articles
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Optimize query performance
ANALYZE articles;
VACUUM ANALYZE articles;
```

---

## 🔄 **SCALABILITY ARCHITECTURE**

### **Horizontal Scaling Strategy**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Load          │    │   Backend       │    │   Database      │
│   Balancer      │───►│   Instances     │───►│   Cluster       │
│   (Nginx)       │    │   (Multiple)    │    │   (Primary +    │
│                 │    │                 │    │    Replicas)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Cache Layer   │    │   Message       │    │   Storage       │
│   (Redis)       │    │   Queue         │    │   (Distributed) │
│                 │    │   (Celery)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Scaling Components**
- **Load Balancing**: Distribute requests across multiple backend instances
- **Database Clustering**: Primary-replica setup for read scaling
- **Caching Layer**: Redis for session and data caching
- **Message Queues**: Celery for background task processing
- **Storage Scaling**: Distributed storage with NAS or cloud storage

### **Microservices Architecture (Future)**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   API Gateway   │    │   RSS Service   │    │   Content       │
│                 │───►│                 │───►│   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User          │    │   Analytics     │    │   Notification  │
│   Service       │    │   Service       │    │   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🚀 **DEPLOYMENT ARCHITECTURE**

### **Container Orchestration**
```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   Local         │  │   NAS           │  │ Production  │ │
│  │   Profile       │  │   Profile       │  │ Profile     │ │
│  │                 │  │                 │  │             │ │
│  │ • Local         │  │ • NAS Storage   │  │ • High      │ │
│  │   Storage       │  │ • Monitoring    │  │   Availability│ │
│  │ • Basic         │  │ • Persistence   │  │ • Security  │ │
│  │   Monitoring    │  │ • Backup        │  │ • Scaling   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### **Deployment Profiles**
- **Local Profile**: Development and testing environment
- **NAS Profile**: Medium-scale deployment with persistent storage
- **Production Profile**: Enterprise-grade deployment with full monitoring

### **Infrastructure as Code**
```yaml
# Docker Compose service definition
services:
  postgres-nas:
    image: postgres:15
    restart: unless-stopped
    environment:
      POSTGRES_DB: news_system
      POSTGRES_USER: newsapp
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - /mnt/terramaster-nas/docker-postgres-data/pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U newsapp -d news_system"]
      interval: 30s
      timeout: 10s
      retries: 5
```

---

## 🔮 **FUTURE ARCHITECTURE ROADMAP**

### **Version 4.0 - ML Integration**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Content       │    │   ML Pipeline   │    │   Model         │
│   Input         │───►│   (Training)    │───►│   Serving       │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Feature       │    │   Model         │    │   Inference     │
│   Engineering   │    │   Registry      │    │   Engine        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### **Planned Enhancements**
- **ML Pipeline**: Automated model training and deployment
- **Vector Database**: Advanced similarity search with pgvector
- **Real-time Processing**: Stream processing for live content
- **API Gateway**: Advanced API management and rate limiting
- **Service Mesh**: Inter-service communication and security

---

## 🎉 **ARCHITECTURE SUMMARY**

The News Intelligence System v3.0 features a robust, scalable architecture designed for:

- **Modularity**: Clean separation of concerns and responsibilities
- **Scalability**: Horizontal scaling from development to enterprise
- **Reliability**: Comprehensive monitoring and health checking
- **Security**: Multi-layered security with best practices
- **Performance**: Optimized for high-throughput content processing
- **Maintainability**: Clear structure and comprehensive documentation

**The architecture provides a solid foundation for current needs and future growth!** 🚀

---

## 🔗 **RELATED DOCUMENTATION**

- **[Quick Start Guide](QUICK_START.md)** - Get started quickly
- **[User Manual](USER_MANUAL.md)** - Complete feature guide
- **[Deployment Guide](DEPLOYMENT.md)** - Production setup instructions
- **[API Reference](API_REFERENCE.md)** - Backend API documentation

