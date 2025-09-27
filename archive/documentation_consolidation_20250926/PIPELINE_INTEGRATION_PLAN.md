# Pipeline Integration Plan

## 🎯 Goal: Connect All Moving Parts

**From RSS Collection → Article Processing → ML Analysis → Storyline Creation → Dossier Generation**

## 🔗 Current Pipeline Status

### **Step 1: RSS Collection** ✅
- **Status**: Working
- **Feeds**: 5 configured (CNN, Fox, MSNBC, BBC, Reuters)
- **Collection**: Manual refresh working
- **Next**: Automate collection

### **Step 2: Article Processing** ✅
- **Status**: Working
- **Articles**: 1 found in database
- **Processing**: Basic processing working
- **Next**: Add quality gates

### **Step 3: ML Processing** ⚠️
- **Status**: Degraded
- **Issue**: Ollama model downloading (llama3.1:70b-instruct-q4_K_M)
- **Fallback**: None (good - we want real ML)
- **Next**: Wait for download completion

### **Step 4: Storyline Creation** ✅
- **Status**: Working
- **Storylines**: 1 found in database
- **Creation**: Manual creation working
- **Next**: Automate storyline creation

### **Step 5: Dossier Generation** ✅
- **Status**: Working
- **Reports**: Basic reports working
- **Display**: Frontend showing reports
- **Next**: Enhance report content

## 🚀 Integration Actions

### **Immediate Actions (Today)**

1. **Wait for Ollama Download**
   ```bash
   # Check download progress
   tail -f ollama_download.log
   
   # When complete, test ML processing
   python3 scripts/quick_check.py
   ```

2. **Test Complete Pipeline**
   ```bash
   # Test RSS collection
   curl -X POST http://localhost:8000/api/rss/feeds/1/refresh
   
   # Test ML processing
   curl -X POST http://localhost:8000/api/storylines/1/process-ml
   
   # Test dossier generation
   curl -X GET http://localhost:8000/api/storylines/1/report
   ```

3. **Verify Frontend Integration**
   ```bash
   # Check if frontend is built
   ls web/build/
   
   # If not built, build it
   cd web && npm run build
   ```

### **Short-term Actions (This Week)**

1. **Automate RSS Collection**
   - Set up scheduled collection every 30 minutes
   - Add error handling and retry logic
   - Monitor collection success rates

2. **Enhance ML Processing**
   - Add more ML models (sentiment, entity extraction)
   - Improve summary quality
   - Add confidence scoring

3. **Improve Storyline Creation**
   - Add automatic storyline suggestions
   - Implement article clustering
   - Add storyline merging logic

4. **Enhance Dossier Generation**
   - Add timeline visualization
   - Include source analysis
   - Add edit history tracking

### **Long-term Actions (Next Month)**

1. **Real-time Processing**
   - WebSocket connections for live updates
   - Real-time dashboard
   - Push notifications

2. **Advanced Analytics**
   - Trend analysis
   - Predictive modeling
   - Impact assessment

3. **User Experience**
   - Mobile responsiveness
   - Advanced filtering
   - Export capabilities

## 🔧 Technical Integration Points

### **API Endpoints**
- `GET /api/rss/feeds/` - List RSS feeds
- `POST /api/rss/feeds/{id}/refresh` - Collect articles
- `GET /api/articles/` - List articles
- `POST /api/storylines/` - Create storyline
- `POST /api/storylines/{id}/process-ml` - ML processing
- `GET /api/storylines/{id}/report` - Generate dossier

### **Database Tables**
- `rss_feeds` - RSS feed configuration
- `articles` - Collected articles
- `storylines` - Storyline definitions
- `storyline_articles` - Article-storyline relationships
- `storyline_events` - Timeline events
- `storyline_sources` - Source analysis

### **Frontend Components**
- `Storylines.js` - Storyline list
- `SimpleStorylineReport.js` - Dossier display
- `App.tsx` - Main application

## 📊 Success Metrics

### **Pipeline Health**
- RSS collection success rate > 95%
- Article processing time < 30 seconds
- ML processing success rate > 90%
- Dossier generation time < 10 seconds

### **Data Quality**
- Article deduplication rate > 99%
- ML summary quality score > 8/10
- Storyline relevance score > 8/10
- Source diversity score > 7/10

### **User Experience**
- Page load time < 3 seconds
- API response time < 1 second
- Error rate < 1%
- User satisfaction > 8/10

## 🚨 Common Issues & Solutions

### **RSS Collection Fails**
```bash
# Check feed status
curl http://localhost:8000/api/rss/feeds/

# Restart collection
curl -X POST http://localhost:8000/api/rss/feeds/1/refresh
```

### **ML Processing Fails**
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Restart ML processing
curl -X POST http://localhost:8000/api/storylines/1/process-ml
```

### **Frontend Not Loading**
```bash
# Check if built
ls web/build/

# Rebuild if needed
cd web && npm run build
```

### **Database Issues**
```bash
# Check database health
curl http://localhost:8000/api/database/health

# Restart database
docker restart news-intelligence-postgres
```

## 🎯 Next Steps

1. **Wait for Ollama download completion**
2. **Test complete pipeline end-to-end**
3. **Fix any broken connections**
4. **Automate RSS collection**
5. **Enhance ML processing**
6. **Improve user experience**

---

*This plan focuses on practical, actionable steps to connect all moving parts and create a seamless workflow from RSS collection to storyline dossier generation.*
