# 🤖 ML Integration Guide - News Intelligence System

## 🎯 **OVERVIEW**

The News Intelligence System now includes **AI-powered machine learning capabilities** using Ollama and Llama 3.1 70B for intelligent content processing, summarization, and analysis.

---

## 🏗️ **ML ARCHITECTURE**

### **Core Components**

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Ollama API    │    │  ML Pipeline     │    │   PostgreSQL    │
│  (Llama 3.1)    │◄──►│   Service        │◄──►│   Database      │
│                 │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   GPU (RTX)     │    │  Content Analysis│    │  ML Data Store  │
│   Processing    │    │  & Quality Score │    │  (JSONB)        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### **ML Services**

1. **MLSummarizationService** - AI-powered content summarization with argument analysis
2. **ContentAnalyzer** - Content cleaning and metadata extraction  
3. **QualityScorer** - Multi-dimensional content quality assessment
4. **MLPipeline** - Orchestrated ML processing workflow

---

## 🚀 **QUICK START**

### **Prerequisites**

- ✅ **Ollama Installed**: `curl -fsSL https://ollama.ai/install.sh | sh`
- ✅ **Llama 3.1 70B Model**: `ollama pull llama3.1:70b-instruct-q4_K_M`
- ✅ **Ollama Running**: `export OLLAMA_HOST=0.0.0.0:11434 && ollama serve`
- ✅ **News Intelligence System**: Running with ML modules

### **Test ML Integration**

```bash
# Check ML service status
curl http://localhost:8000/api/ml/status

# Process all articles through ML pipeline
curl -X POST http://localhost:8000/api/ml/process-all

# Generate summary for custom content
curl -X POST -H "Content-Type: application/json" \
  -d '{"content": "Your article content here", "title": "Article Title"}' \
  http://localhost:8000/api/ml/summarize
```

---

## 📊 **ML PROCESSING PIPELINE**

### **Step 1: Content Analysis**
- **Content Cleaning**: HTML removal, normalization, encoding fixes
- **Metadata Extraction**: Word count, reading time, language detection
- **Content Hashing**: SHA256 hash for deduplication
- **Quality Validation**: Length, structure, completeness checks

### **Step 2: Quality Scoring**
- **Content Length**: Optimal 200-1000 words (0.15 weight)
- **Readability**: Flesch Reading Ease analysis (0.20 weight)
- **Structure**: Paragraphs, sentences, formatting (0.15 weight)
- **Uniqueness**: Vocabulary variety, repetition analysis (0.15 weight)
- **Completeness**: Introduction, body, conclusion (0.15 weight)
- **Language Quality**: Grammar, punctuation, spelling (0.20 weight)

### **Step 3: ML Processing**
- **Summarization**: Comprehensive AI-generated summaries with argument analysis
- **Key Points**: 3-5 bullet point extraction
- **Sentiment Analysis**: Positive/negative/neutral classification
- **Argument Analysis**: Balanced perspective breakdown for controversial topics
- **Quality Threshold**: Only process content with score ≥ 0.3

### **Step 4: Data Storage**
- **Summary**: Stored in `articles.summary` column
- **Quality Score**: Stored in `articles.quality_score` column
- **ML Data**: Complete analysis stored in `articles.ml_data` JSONB
- **Processing Status**: Updated to `ml_processed`

---

## 🔧 **API ENDPOINTS**

### **ML Service Status**
```http
GET /api/ml/status
```
**Response:**
```json
{
  "success": true,
  "ml_available": true,
  "service_status": {
    "status": "online",
    "model_available": true,
    "model_name": "llama3.1:70b-instruct-q4_K_M",
    "available_models": ["llama3.1:70b-instruct-q4_K_M"]
  }
}
```

### **Process Single Article**
```http
POST /api/ml/process-article/{article_id}
```
**Response:**
```json
{
  "success": true,
  "result": {
    "status": "success",
    "article_id": 11,
    "content_analysis": { ... },
    "quality_score": { ... },
    "ml_results": { ... }
  }
}
```

### **Process All Articles**
```http
POST /api/ml/process-all
```
**Response:**
```json
{
  "success": true,
  "result": {
    "total_articles": 5,
    "processed": 4,
    "failed": 0,
    "skipped": 1,
    "success_rate": 0.8
  }
}
```

### **Generate Summary**
```http
POST /api/ml/summarize
Content-Type: application/json

{
  "content": "Article content here...",
  "title": "Article Title"
}
```

### **Analyze Arguments**
```http
POST /api/ml/analyze-arguments
Content-Type: application/json

{
  "content": "Article content here...",
  "title": "Article Title"
}
```

### **Get Processing Status**
```http
GET /api/ml/processing-status
```

---

## 📈 **QUALITY SCORING SYSTEM**

### **Scoring Dimensions**

| Dimension | Weight | Description | Optimal Range |
|-----------|--------|-------------|---------------|
| **Content Length** | 15% | Word count analysis | 200-1000 words |
| **Readability** | 20% | Flesch Reading Ease | 60-80 score |
| **Structure** | 15% | Paragraphs, sentences | 3+ paragraphs |
| **Uniqueness** | 15% | Vocabulary variety | 70%+ unique words |
| **Completeness** | 15% | Intro, body, conclusion | All present |
| **Language Quality** | 20% | Grammar, punctuation | Proper usage |

### **Quality Grades**

- **A+ (0.9-1.0)**: Excellent content quality
- **A (0.8-0.9)**: Very good content quality  
- **B+ (0.7-0.8)**: Good content quality
- **B (0.6-0.7)**: Acceptable content quality
- **C+ (0.5-0.6)**: Below average quality
- **C (0.4-0.5)**: Poor content quality
- **D (0.3-0.4)**: Very poor quality
- **F (0.0-0.3)**: Unacceptable quality

---

## 🗄️ **DATABASE SCHEMA**

### **ML-Enhanced Articles Table**

```sql
-- Articles table with ML columns
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,                    -- AI-generated summary
    url TEXT,
    source VARCHAR(255),
    published_date TIMESTAMP,
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',
    quality_score DECIMAL(3,2),     -- ML quality score (0.0-1.0)
    processing_status VARCHAR(50),  -- 'raw', 'ml_processed', etc.
    content_hash VARCHAR(64),       -- SHA256 for deduplication
    normalized_content TEXT,        -- Cleaned content
    ml_data JSONB,                  -- Complete ML analysis
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **ML Data Structure**

```json
{
  "content_analysis": {
    "cleaning_result": {
      "cleaned_content": "...",
      "changes_made": ["removed_html_tags"],
      "original_length": 500,
      "cleaned_length": 480
    },
    "metadata": {
      "word_count": 85,
      "sentence_count": 4,
      "reading_time_minutes": 1,
      "language_indicators": ["english"]
    },
    "content_hash": "sha256_hash_here"
  },
  "quality_score": {
    "overall_score": 0.75,
    "grade": "B+",
    "dimensions": { ... },
    "recommendations": [ ... ]
  },
  "ml_processing": {
    "summary": {
      "summary": "AI-generated summary...",
      "status": "success",
      "model_used": "llama3.1:70b-instruct-q4_K_M"
    },
    "key_points": {
      "key_points": ["Point 1", "Point 2"],
      "status": "success"
    },
    "sentiment": {
      "sentiment": "positive",
      "sentiment_analysis": "Analysis text...",
      "status": "success"
    }
  }
}
```

---

## ⚙️ **CONFIGURATION**

### **Ollama Configuration**

```bash
# Set Ollama to bind to all interfaces
export OLLAMA_HOST=0.0.0.0:11434

# Start Ollama service
ollama serve

# Pull required model
ollama pull llama3.1:70b-instruct-q4_K_M
```

### **ML Service Configuration**

```python
# In api/modules/ml/summarization_service.py
class MLSummarizationService:
    def __init__(self, 
                 ollama_url="http://192.168.93.92:11434",  # Host IP
                 model_name="llama3.1:70b-instruct-q4_K_M"):
        # Configuration
        self.timeout = 300  # 5 minutes for large models
        self.max_content_length = 4000  # Token limit
```

### **Quality Scoring Weights**

```python
# In api/modules/ml/quality_scorer.py
self.weights = {
    "content_length": 0.15,
    "readability": 0.20,
    "structure": 0.15,
    "uniqueness": 0.15,
    "completeness": 0.15,
    "language_quality": 0.20
}
```

---

## 🔍 **MONITORING & TROUBLESHOOTING**

### **Check ML Service Health**

```bash
# Test Ollama connection
curl http://192.168.93.92:11434/api/tags

# Check ML API status
curl http://localhost:8000/api/ml/status

# View processing statistics
curl http://localhost:8000/api/ml/processing-status
```

### **Common Issues**

#### **1. Ollama Connection Refused**
```bash
# Check if Ollama is running
ps aux | grep ollama

# Restart Ollama with correct host binding
export OLLAMA_HOST=0.0.0.0:11434
ollama serve
```

#### **2. Model Not Available**
```bash
# List available models
ollama list

# Pull required model
ollama pull llama3.1:70b-instruct-q4_K_M
```

#### **3. Incomplete Summaries**
- **Issue**: Model responses truncated
- **Solution**: Increase timeout in `summarization_service.py`
- **Current**: 300 seconds (5 minutes)

#### **4. Low Quality Scores**
- **Issue**: Articles scoring below 0.3 threshold
- **Solution**: Review content quality or adjust threshold
- **Current**: Minimum 0.3 for ML processing

---

## 📊 **PERFORMANCE METRICS**

### **Processing Statistics**

| Metric | Value | Description |
|--------|-------|-------------|
| **Model Size** | 42.5 GB | Llama 3.1 70B Q4_K_M |
| **Processing Time** | 10-30s | Per article (varies by length) |
| **Memory Usage** | ~32GB | GPU VRAM utilization |
| **Quality Threshold** | 0.3 | Minimum score for processing |
| **Success Rate** | 95%+ | Typical processing success |

### **Resource Requirements**

- **GPU**: RTX 5090 (32GB VRAM) ✅
- **RAM**: 64GB system memory ✅
- **Storage**: 50GB+ for model storage ✅
- **Network**: Ollama API accessible from containers ✅

---

## 🚀 **NEXT STEPS**

### **Phase 2: Advanced Features**
- [ ] **Content Deduplication**: Advanced similarity detection
- [ ] **Batch Processing**: Optimized multi-article processing
- [ ] **Model Fine-tuning**: Custom news summarization model
- [ ] **Real-time Processing**: Live article processing

### **Phase 3: Production Optimization**
- [ ] **Caching**: Response caching for similar content
- [ ] **Queue Management**: Background job processing
- [ ] **A/B Testing**: Multiple model comparison
- [ ] **Performance Monitoring**: ML-specific metrics

---

## 📚 **ADDITIONAL RESOURCES**

- **Ollama Documentation**: https://ollama.ai/docs
- **Llama 3.1 Model**: https://huggingface.co/meta-llama/Llama-3.1-70B-Instruct
- **News Intelligence System**: `/docs/README.md`
- **API Documentation**: `/docs/API.md`

---

## 🎉 **SUCCESS INDICATORS**

✅ **ML Service Online**: Ollama connected and model available  
✅ **Pipeline Working**: Articles processed through ML pipeline  
✅ **Quality Scoring**: Multi-dimensional content assessment  
✅ **Summarization**: AI-generated article summaries  
✅ **Data Storage**: ML results stored in database  
✅ **API Integration**: RESTful endpoints for ML operations  

**The News Intelligence System now has full AI-powered machine learning capabilities!** 🚀
