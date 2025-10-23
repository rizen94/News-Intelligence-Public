# 🔄 News Intelligence System v3.0 - Workflow & Data Pipeline

## 🎯 **SYSTEM OVERVIEW**

The News Intelligence System is a comprehensive AI-powered platform that automatically collects, processes, and analyzes news content to provide real-time intelligence insights. The system operates through a sophisticated multi-stage pipeline that transforms raw RSS feeds into actionable intelligence.

---

## 🔄 **COMPLETE DATA PIPELINE WORKFLOW**

### **Stage 1: Data Collection & Ingestion**
```
RSS Feeds → Content Extraction → Validation → Database Storage
    │              │                │              │
    ▼              ▼                ▼              ▼
100+ Sources   HTML Parsing    Quality Check   PostgreSQL
RSS Feeds     Text Extraction  Duplicate      Database
               Metadata        Detection
               Extraction
```

**Components:**
- **RSS Collectors** (`/api/collectors/`)
  - `rss_collector.py` - Basic RSS feed collection
  - `enhanced_rss_collector.py` - Advanced content extraction
- **Content Extraction** - HTML parsing, text cleaning, metadata extraction
- **Validation** - URL validation, content quality checks, duplicate detection

### **Stage 2: Content Processing & Deduplication**
```
Raw Articles → Content Cleaning → Deduplication → Quality Scoring
     │               │                │               │
     ▼               ▼                ▼               ▼
Database        HTML Removal    Similarity      Content
Storage         Text Normalize  Detection       Quality
                Language        Vector-based    Assessment
                Detection       Analysis
```

**Components:**
- **Content Cleaner** (`/api/modules/intelligence/content_cleaner.py`)
- **Deduplication Manager** (`/api/modules/deduplication/`)
- **Quality Validator** (`/api/modules/intelligence/quality_validator.py`)

### **Stage 3: AI Analysis & Intelligence Processing**
```
Processed Articles → ML Pipeline → Entity Extraction → Content Analysis
        │                │              │                    │
        ▼                ▼              ▼                    ▼
   Database         Llama 3.1 70B   Named Entity      Sentiment
   Storage          AI Model        Recognition       Analysis
                    Summarization    Classification    Key Points
                    Generation       Event Detection   Extraction
```

**Components:**
- **ML Pipeline** (`/api/modules/ml/ml_pipeline.py`)
- **Background Processor** (`/api/modules/ml/background_processor.py`)
- **Intelligence Orchestrator** (`/api/modules/intelligence/intelligence_orchestrator.py`)

### **Stage 4: Story Clustering & Prioritization**
```
Analyzed Articles → Content Clustering → Story Threads → Priority Assignment
        │                │                    │               │
        ▼                ▼                    ▼               ▼
   AI Results        Vector-based        Story Groups    Priority
   Database          Similarity          Thread          Scoring
   Storage           Analysis            Creation        System
```

**Components:**
- **Content Prioritization Manager** (`/api/modules/prioritization/content_prioritization_manager.py`)
- **Content Prioritization Engine** (`/api/modules/prioritization/content_prioritization_engine.py`)
- **Intelligent Tagging Service** (`/api/modules/prioritization/intelligent_tagging_service.py`)

### **Stage 5: RAG Enhancement & Context Building**
```
Story Threads → RAG Context → Enhanced Analysis → Intelligence Insights
      │              │              │                    │
      ▼              ▼              ▼                    ▼
  Story Groups   Context        Deep Analysis      Intelligence
  Database       Building       with External      Dashboard
  Storage        Service        Data Sources       Delivery
```

**Components:**
- **Iterative RAG Service** (`/api/modules/ml/iterative_rag_service.py`)
- **RAG Context Builder** (`/api/modules/prioritization/rag_context_builder.py`)

### **Stage 6: Intelligence Delivery & User Interface**
```
Intelligence Data → Dashboard APIs → React Frontend → User Interface
        │                │               │               │
        ▼                ▼               ▼               ▼
   Processed         REST API        React App      Real-time
   Insights          Endpoints       Components     Dashboards
   Database          (FastAPI)       (Material-UI)  & Reports
```

**Components:**
- **Dashboard APIs** (`/api/routes/dashboard.py`)
- **Articles APIs** (`/api/routes/articles.py`)
- **Intelligence APIs** (`/api/routes/intelligence.py`)
- **React Frontend** (`/web/src/`)

---

## 🏗️ **DETAILED WORKFLOW STEPS**

### **1. RSS Collection Workflow**
```python
# Every 30 minutes (configurable)
def collect_rss_feeds():
    for feed in active_feeds:
        # Parse RSS feed with timeout protection
        articles = parse_rss_feed(feed.url)
        
        for article in articles:
            # Extract content and metadata
            content = extract_article_content(article.url)
            metadata = extract_metadata(article)
            
            # Check for duplicates
            if not is_duplicate(content):
                # Store in database
                store_article(article, content, metadata)
```

### **2. Content Processing Workflow**
```python
# Background processing queue
def process_article(article_id):
    # Step 1: Content cleaning
    cleaned_content = clean_html_content(article.content)
    
    # Step 2: Language detection
    language = detect_language(cleaned_content)
    
    # Step 3: Quality validation
    quality_score = validate_content_quality(cleaned_content)
    
    # Step 4: Store processed content
    update_article_processing(article_id, cleaned_content, quality_score)
```

### **3. AI Analysis Workflow**
```python
# ML Pipeline processing
def analyze_article_with_ai(article_id):
    article = get_article(article_id)
    
    # Step 1: Content analysis
    content_analysis = analyze_content(article)
    
    # Step 2: Quality scoring
    quality_score = score_quality(article, content_analysis)
    
    # Step 3: ML processing (if quality sufficient)
    if quality_score >= 0.3:
        ml_results = run_ml_processing(article)
        # - Summarization
        # - Key points extraction
        # - Sentiment analysis
        # - Argument analysis
    
    # Step 4: Store results
    store_ml_results(article_id, content_analysis, quality_score, ml_results)
```

### **4. Story Clustering Workflow**
```python
# Content clustering and story thread creation
def create_story_clusters():
    # Step 1: Get processed articles
    articles = get_processed_articles()
    
    # Step 2: Vectorize articles
    vectors = vectorize_articles(articles)
    
    # Step 3: Perform clustering
    clusters = perform_clustering(vectors)
    
    # Step 4: Create story threads
    for cluster in clusters:
        story_thread = create_story_thread(cluster)
        assign_articles_to_thread(cluster.articles, story_thread.id)
```

### **5. Priority Assignment Workflow**
```python
# Content prioritization and ranking
def assign_content_priority(article_data):
    # Step 1: Calculate base priority
    base_priority = calculate_base_priority(article_data)
    
    # Step 2: Apply user rules
    user_priority = apply_user_rules(article_data, base_priority)
    
    # Step 3: Apply collection rules
    final_priority = apply_collection_rules(article_data, user_priority)
    
    # Step 4: Check for story thread matches
    thread_matches = find_story_thread_matches(article_data)
    
    # Step 5: Assign priority and thread
    assign_priority_and_thread(article_data.id, final_priority, thread_matches)
```

---

## 📊 **DATA FLOW DIAGRAM**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RSS Feeds     │───▶│  Content        │───▶│   Database      │
│   (100+ Sources)│    │  Collection     │    │  (PostgreSQL)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI Analysis   │◄───│  Content        │◄───│   Content       │
│  (Llama 3.1)    │    │  Processing     │    │  Deduplication  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Story         │◄───│   Content       │◄───│   Entity        │
│   Clustering    │    │   Prioritization│    │   Extraction    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RAG           │◄───│   Intelligence  │◄───│   Quality       │
│   Enhancement   │    │   Insights      │    │   Validation    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Dashboard     │◄───│   API Layer     │◄───│   Data          │
│   (React)       │    │   (FastAPI)     │    │   Storage       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🔧 **TECHNICAL IMPLEMENTATION**

### **Backend Processing**
- **FastAPI** - REST API endpoints for all operations
- **PostgreSQL** - Primary database with pgvector for similarity search
- **Redis** - Caching layer for performance
- **Background Workers** - Asynchronous processing queues

### **AI/ML Components**
- **Llama 3.1 70B** - Primary AI model for content analysis
- **Vector Embeddings** - Content similarity and clustering
- **Named Entity Recognition** - Person, organization, location extraction
- **Sentiment Analysis** - Content sentiment scoring
- **Text Summarization** - AI-generated article summaries

### **Frontend Interface**
- **React.js** - Modern web application framework
- **Material-UI** - Professional component library
- **Real-time Updates** - Live dashboard updates
- **Responsive Design** - Mobile and desktop support

---

## ⚡ **PERFORMANCE CHARACTERISTICS**

### **Processing Speed**
- **RSS Collection** - 100+ feeds in ~2-3 minutes
- **Content Processing** - 1000 articles in ~5-10 minutes
- **AI Analysis** - 100 articles in ~15-30 minutes
- **Story Clustering** - 1000 articles in ~2-5 minutes

### **Scalability**
- **Horizontal Scaling** - Multiple worker processes
- **Database Optimization** - Indexed queries and connection pooling
- **Caching Strategy** - Redis for frequently accessed data
- **Background Processing** - Asynchronous task queues

### **Reliability**
- **Error Handling** - Comprehensive error recovery
- **Timeout Protection** - Prevents hanging operations
- **Duplicate Detection** - Prevents redundant processing
- **Quality Validation** - Ensures content quality

---

## 🎯 **EXPECTED OUTCOMES**

### **For Users**
- **Real-time Intelligence** - Live news monitoring and analysis
- **Story Tracking** - Follow story evolution over time
- **Content Discovery** - Find relevant articles and insights
- **Automated Summaries** - AI-generated content summaries

### **For System**
- **High Throughput** - Process thousands of articles daily
- **Low Latency** - Sub-second response times for queries
- **High Availability** - 99.9% uptime with monitoring
- **Scalable Architecture** - Handle increasing data volumes

This comprehensive workflow ensures that raw news content is transformed into actionable intelligence through a sophisticated, AI-powered pipeline that operates continuously and efficiently.
