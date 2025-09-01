# 🤖 ML User Guide - News Intelligence System

## 🎯 **OVERVIEW**

This guide explains how to use the AI/ML features in the News Intelligence System. The system now includes **Llama 3.1 70B** for intelligent content processing, summarization, and analysis.

---

## 🚀 **GETTING STARTED WITH ML**

### **Prerequisites**

Before using ML features, ensure:

1. ✅ **Ollama is installed and running**
2. ✅ **Llama 3.1 70B model is downloaded**
3. ✅ **News Intelligence System is deployed**
4. ✅ **ML service is online**

### **Check ML Status**

Visit the **ML Status** page in the web interface or use the API:

```bash
curl http://localhost:8000/api/ml/status
```

You should see:
```json
{
  "success": true,
  "ml_available": true,
  "service_status": {
    "status": "online",
    "model_available": true,
    "model_name": "llama3.1:70b-instruct-q4_K_M"
  }
}
```

---

## 📊 **ML PROCESSING WORKFLOW**

### **Automatic Processing**

The system automatically processes articles through the ML pipeline:

1. **Content Analysis** - Cleans and analyzes article content
2. **Quality Scoring** - Evaluates content quality (0.0-1.0 scale)
3. **ML Processing** - Generates summaries, key points, and sentiment
4. **Data Storage** - Stores results in the database

### **Processing Thresholds**

- **Minimum Quality Score**: 0.3 (articles below this are skipped)
- **Minimum Content Length**: 100 characters
- **Processing Time**: 10-30 seconds per article

---

## 🎨 **WEB INTERFACE FEATURES**

### **Dashboard ML Metrics**

The main dashboard now shows:

- **ML Processing Status** - Number of articles processed
- **Quality Score Distribution** - Chart of content quality scores
- **Summary Generation Rate** - Success rate of AI summarization
- **Sentiment Analysis** - Distribution of positive/negative/neutral content

### **Article View Enhancements**

When viewing articles, you'll see:

- **AI-Generated Summary** - 2-3 sentence summary at the top
- **Quality Score** - Letter grade (A+ to F) with details
- **Key Points** - Bullet points extracted by AI
- **Sentiment** - Positive/negative/neutral classification
- **Processing Status** - Shows if article has been ML processed

### **ML Processing Controls**

- **Process All Articles** - Button to run ML on all unprocessed articles
- **Process Individual Article** - Process specific articles on demand
- **ML Status Monitor** - Real-time processing status

---

## 🔧 **API USAGE**

### **Process All Articles**

```bash
curl -X POST http://localhost:8000/api/ml/process-all
```

**Response:**
```json
{
  "success": true,
  "result": {
    "total_articles": 10,
    "processed": 8,
    "failed": 0,
    "skipped": 2,
    "success_rate": 0.8
  }
}
```

### **Process Single Article**

```bash
curl -X POST http://localhost:8000/api/ml/process-article/123
```

### **Generate Custom Summary**

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{
    "content": "Your article content here...",
    "title": "Article Title"
  }' \
  http://localhost:8000/api/ml/summarize
```

### **Get Processing Status**

```bash
curl http://localhost:8000/api/ml/processing-status
```

---

## 📈 **UNDERSTANDING QUALITY SCORES**

### **Quality Score Breakdown**

The system evaluates articles across 6 dimensions:

| Dimension | Weight | What It Measures |
|-----------|--------|------------------|
| **Content Length** | 15% | Optimal 200-1000 words |
| **Readability** | 20% | Sentence complexity and clarity |
| **Structure** | 15% | Paragraphs and organization |
| **Uniqueness** | 15% | Vocabulary variety and repetition |
| **Completeness** | 15% | Introduction, body, conclusion |
| **Language Quality** | 20% | Grammar, punctuation, spelling |

### **Quality Grades**

- **A+ (0.9-1.0)**: Excellent - Professional quality content
- **A (0.8-0.9)**: Very Good - High-quality content
- **B+ (0.7-0.8)**: Good - Solid content with minor issues
- **B (0.6-0.7)**: Acceptable - Decent content
- **C+ (0.5-0.6)**: Below Average - Needs improvement
- **C (0.4-0.5)**: Poor - Significant quality issues
- **D (0.3-0.4)**: Very Poor - Major problems
- **F (0.0-0.3)**: Unacceptable - Not processed by ML

### **Improvement Recommendations**

The system provides specific recommendations for each article:

- **Content Length**: "Consider adjusting content length (optimal: 200-1000 words)"
- **Readability**: "Improve readability by using shorter sentences and simpler words"
- **Structure**: "Improve structure with clear paragraphs and proper formatting"
- **Uniqueness**: "Reduce repetitive content and increase vocabulary variety"
- **Completeness**: "Ensure content has proper introduction, body, and conclusion"
- **Language Quality**: "Improve language quality with proper grammar and punctuation"

---

## 🎯 **BEST PRACTICES**

### **For Content Creators**

1. **Write Complete Articles** - Include introduction, body, and conclusion
2. **Use Proper Structure** - Break content into clear paragraphs
3. **Maintain Quality** - Check grammar, spelling, and punctuation
4. **Avoid Repetition** - Use varied vocabulary and sentence structure
5. **Optimal Length** - Aim for 200-1000 words for best results

### **For System Administrators**

1. **Monitor Processing** - Check ML status regularly
2. **Review Quality Scores** - Identify content quality trends
3. **Adjust Thresholds** - Modify minimum quality scores if needed
4. **Monitor Performance** - Watch processing times and success rates
5. **Backup ML Data** - Ensure ML results are included in backups

### **For Users**

1. **Check Summaries** - Review AI-generated summaries for accuracy
2. **Use Key Points** - Leverage extracted key points for quick scanning
3. **Consider Sentiment** - Use sentiment analysis for content filtering
4. **Quality Awareness** - Pay attention to quality scores when selecting content
5. **Feedback Loop** - Report any issues with ML processing

---

## 🔍 **TROUBLESHOOTING**

### **Common Issues**

#### **ML Service Offline**
**Symptoms**: ML features not working, "ML not available" errors
**Solutions**:
1. Check if Ollama is running: `ps aux | grep ollama`
2. Restart Ollama: `export OLLAMA_HOST=0.0.0.0:11434 && ollama serve`
3. Verify model is available: `ollama list`

#### **Incomplete Summaries**
**Symptoms**: Summaries showing "Here is a summary of the article:" only
**Solutions**:
1. Check model response time (may need longer timeout)
2. Verify article content is substantial (>100 characters)
3. Check if article meets quality threshold (≥0.3)

#### **Low Quality Scores**
**Symptoms**: Many articles scoring below 0.3, not being processed
**Solutions**:
1. Review content quality recommendations
2. Consider adjusting quality threshold
3. Improve source content quality

#### **Processing Failures**
**Symptoms**: Articles failing ML processing
**Solutions**:
1. Check system resources (GPU memory, RAM)
2. Verify Ollama service stability
3. Review error logs for specific issues

### **Performance Optimization**

#### **Faster Processing**
- Ensure GPU is properly utilized
- Close unnecessary applications
- Monitor system resources during processing

#### **Better Quality Scores**
- Use high-quality source content
- Ensure articles have proper structure
- Maintain consistent formatting

#### **Reliable Processing**
- Keep Ollama service running
- Monitor system health
- Regular maintenance and updates

---

## 📊 **MONITORING & ANALYTICS**

### **Key Metrics to Watch**

1. **Processing Success Rate** - Should be >95%
2. **Average Quality Score** - Track content quality trends
3. **Processing Time** - Monitor performance
4. **Model Utilization** - Ensure GPU is being used effectively
5. **Error Rates** - Watch for processing failures

### **Dashboard Monitoring**

The web dashboard provides real-time monitoring of:

- **ML Processing Status** - Current processing state
- **Quality Score Distribution** - Histogram of content quality
- **Sentiment Analysis** - Distribution of sentiment classifications
- **Processing Statistics** - Success rates and timing
- **System Health** - ML service status and availability

---

## 🚀 **ADVANCED FEATURES**

### **Custom Processing**

You can process specific articles or batches:

```bash
# Process specific article IDs
curl -X POST -H "Content-Type: application/json" \
  -d '{"article_ids": [1, 2, 3, 4, 5]}' \
  http://localhost:8000/api/ml/process-batch
```

### **Content Analysis**

Analyze content quality without full ML processing:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"content": "Your content here", "title": "Title"}' \
  http://localhost:8000/api/ml/analyze-content
```

### **Quality Threshold Adjustment**

Modify the minimum quality threshold in the ML pipeline configuration to process lower-quality content if needed.

---

## 📚 **ADDITIONAL RESOURCES**

- **[ML Integration Guide](ML_INTEGRATION.md)** - Technical implementation details
- **[API Reference](API_REFERENCE.md)** - Complete API documentation
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Common issues and solutions
- **[System Architecture](ARCHITECTURE.md)** - Overall system design

---

## 🎉 **SUCCESS INDICATORS**

You'll know the ML system is working well when:

✅ **High Processing Success Rate** (>95%)  
✅ **Good Quality Score Distribution** (most articles B+ or higher)  
✅ **Fast Processing Times** (10-30 seconds per article)  
✅ **Accurate Summaries** (meaningful, not truncated)  
✅ **Reliable Sentiment Analysis** (consistent classifications)  
✅ **Stable Service** (minimal downtime or errors)  

**The AI/ML features are now fully integrated and ready for production use!** 🚀
