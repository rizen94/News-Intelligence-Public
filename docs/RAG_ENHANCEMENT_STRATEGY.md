# RAG Enhancement Strategy

## Overview
This document explains the strategy for when and how RAG (Retrieval-Augmented Generation) enhancement is used in the News Intelligence system.

## When RAG Enhancement is Used

### 1. **Storyline Enhancement (Primary Use Case)**

RAG enhancement is primarily used to enhance storyline summaries with additional context from external sources.

#### **Trigger Conditions**

RAG enhancement is triggered when **any** of the following conditions are met:

1. **Never Enhanced Before**
   - If a storyline has never been RAG-enhanced (`last_rag_enhancement_at` is NULL)
   - First-time enhancement to get baseline context

2. **New Articles Added**
   - If the number of articles in the storyline (`article_count`) exceeds the number of enhancements (`enhancement_count`)
   - Indicates new content that needs fresh context

3. **Time-Based Refresh**
   - If last enhancement was more than **24 hours** ago
   - Ensures context stays current as stories evolve

4. **Forced Enhancement**
   - When explicitly requested via API with `force=True`
   - Manual trigger for immediate enhancement

5. **Automated Scheduled Enhancement**
   - Automation Manager runs RAG enhancement tasks
   - Checks every storyline and enhances if last enhancement was > 1 hour ago

### 2. **Progressive Enhancement Pattern**

The system uses a **progressive enhancement** approach:

```
Storyline Created
    ↓
Generate Basic Summary (immediate)
    ↓
Wait for trigger conditions
    ↓
Enhance with RAG (when needed)
    ↓
Generate Enhanced Summary
```

#### **Summary Versions**
- **Version 1**: Basic summary (local AI only, immediate)
- **Version 2+**: RAG-enhanced summaries (with external context)

### 3. **Context Sources Used**

When RAG enhancement runs, it gathers context from:

1. **Wikipedia**
   - Background information on topics and entities
   - Historical context
   - Related concepts

2. **GDELT** (Global Database of Events, Language, and Tone)
   - Timeline of related events
   - Historical event context
   - Entity relationships

3. **Internal Database** (Enhanced)
   - Related articles using semantic search
   - Historical articles on same topics
   - Cross-referenced storylines

## Decision Logic

### Enhancement Decision Flow

```python
def should_enhance_storyline(storyline_id):
    # Get storyline metadata
    storyline = get_storyline(storyline_id)
    
    # Check 1: Never enhanced
    if not storyline.last_rag_enhancement_at:
        return True
    
    # Check 2: New articles added
    if storyline.article_count > storyline.enhancement_count:
        return True
    
    # Check 3: Time threshold (24 hours)
    hours_since = (now - storyline.last_rag_enhancement_at).hours
    if hours_since > 24:
        return True
    
    return False
```

### Rate Limiting & Resource Management

Before enhancing, the system checks:

1. **API Rate Limits**
   - Wikipedia API daily limits
   - GDELT API rate limits
   - If limits reached, enhancement is skipped

2. **Caching**
   - Wikipedia results are cached per term
   - Prevents redundant API calls
   - Cache TTL: Configurable (default: 24 hours)

3. **Usage Monitoring**
   - Tracks API usage per service
   - Monitors daily limits
   - Records processing times

## Enhancement Process

### Step-by-Step Flow

1. **Decision Check**
   - Evaluate if enhancement is needed
   - Check rate limits and resource availability

2. **Entity & Topic Extraction**
   - Extract key entities from articles
   - Extract relevant topics
   - Uses enhanced entity extractor (if available)

3. **Context Gathering**
   - Query Wikipedia for each topic/entity
   - Query GDELT for timeline/event context
   - Use cached results when available
   - Rate limit API calls

4. **Context Assembly**
   - Combine Wikipedia context
   - Combine GDELT context
   - Include extracted entities/topics
   - Add metadata (timestamps, sources)

5. **Summary Generation**
   - Generate enhanced summary using RAG context
   - Save as new version
   - Update storyline metadata

6. **Cleanup**
   - Cache new results
   - Record API usage
   - Update enhancement timestamps

## Configuration

### Enhancement Thresholds

```python
RAG_ENHANCEMENT_CONFIG = {
    'time_threshold_hours': 24,      # Refresh every 24 hours
    'automation_interval_hours': 1,  # Check every hour
    'max_topics': 10,                 # Max topics to search
    'max_entities': 10,               # Max entities to search
    'cache_ttl_hours': 24,           # Cache validity
    'rate_limit_delay': 0.5,         # Seconds between API calls
}
```

### Enhancement Criteria Weights

The system uses multiple signals to decide enhancement priority:

1. **Storyline Age**: Older storylines get priority
2. **Article Count**: More articles = higher priority
3. **Last Enhancement**: Longer since last = higher priority
4. **User Requests**: Forced enhancements get immediate priority

## Use Cases

### 1. **New Storyline Created**
- **When**: Immediately after storyline creation
- **Action**: Generate basic summary first
- **RAG**: Enhanced on first automated check (within 1 hour)

### 2. **New Articles Added**
- **When**: When new articles are added to existing storyline
- **Action**: Trigger RAG enhancement to incorporate new context
- **RAG**: Enhanced on next check if `article_count > enhancement_count`

### 3. **Scheduled Refresh**
- **When**: Every hour (automation manager)
- **Action**: Check all storylines, enhance those meeting criteria
- **RAG**: Enhanced if > 24 hours since last enhancement

### 4. **Manual Request**
- **When**: User/admin requests via API
- **Action**: Force enhancement immediately
- **RAG**: Enhanced with `force=True` flag

### 5. **Story Analysis**
- **When**: Generating expert analysis, multi-perspective analysis
- **Action**: Use enhanced RAG retrieval for comprehensive context
- **RAG**: Uses semantic search for related articles

## Performance Considerations

### Optimization Strategies

1. **Caching**
   - Wikipedia results cached per search term
   - Prevents redundant API calls
   - Reduces latency and API usage

2. **Batch Processing**
   - Processes multiple storylines in automation tasks
   - Rate limits API calls to avoid throttling
   - Handles errors gracefully

3. **Progressive Enhancement**
   - Basic summary generated immediately (fast)
   - RAG enhancement happens asynchronously (slower but richer)
   - Users see basic summary while enhancement runs

4. **Selective Enhancement**
   - Only enhances when criteria met
   - Avoids unnecessary processing
   - Respects rate limits and resources

### Cost Management

1. **API Call Limits**
   - Monitors Wikipedia API usage
   - Skips enhancement if limits reached
   - Uses caching to reduce API calls

2. **Processing Time**
   - RAG enhancement is async (doesn't block)
   - Timeout set to 5 minutes
   - Falls back gracefully on errors

3. **Resource Usage**
   - Limits concurrent enhancements
   - Processes in batches
   - Monitors system load

## Integration Points

### Services Using RAG Enhancement

1. **ProgressiveEnhancementService**
   - Primary service for storyline RAG enhancement
   - Decision logic and execution
   - Version management

2. **AutomationManager**
   - Scheduled RAG enhancement tasks
   - Bulk processing of storylines
   - Resource management

3. **StorylineService**
   - Summary generation with RAG context
   - Storyline lifecycle management
   - Article relationship tracking

4. **RAGEnhancedService**
   - Advanced RAG retrieval with semantic search
   - Multi-source context gathering
   - Expert analysis support

### Enhanced Services Integration

The new enhanced RAG retrieval services are integrated into:

1. **Enhanced RAG Retrieval**
   - Used when building comprehensive context
   - Semantic search for better article matching
   - Hybrid search combining multiple techniques

2. **Enhanced Entity Extractor**
   - Better entity extraction for RAG queries
   - More accurate topic identification
   - Improved context gathering

## Best Practices

### When to Use RAG Enhancement

✅ **DO Use RAG Enhancement When:**
- Creating new storylines (initial context)
- Adding significant new articles
- Storyline hasn't been updated in 24+ hours
- Generating expert analysis
- User explicitly requests enhancement

❌ **DON'T Use RAG Enhancement When:**
- Rate limits are reached
- Storyline is very recent (< 1 hour old)
- No new articles added since last enhancement
- Context is already up-to-date
- System resources are constrained

### Optimization Tips

1. **Monitor Cache Hit Rates**
   - High cache hits = good (reducing API calls)
   - Low cache hits = may need to expand cache TTL

2. **Track Enhancement Frequency**
   - Too frequent = wasting resources
   - Too infrequent = stale context
   - Target: Once per 24 hours per storyline

3. **Balance Quality vs Speed**
   - Basic summaries: Fast, immediate
   - RAG-enhanced: Slower but richer
   - Progressive approach: Best of both

## Monitoring & Metrics

### Key Metrics to Track

1. **Enhancement Frequency**
   - Storylines enhanced per day
   - Average time between enhancements
   - Enhancement success rate

2. **API Usage**
   - Wikipedia API calls per day
   - Cache hit rate
   - Rate limit hits

3. **Performance**
   - Average enhancement time
   - Timeout rate
   - Error rate

4. **Quality**
   - User feedback on enhanced summaries
   - Comparison: basic vs enhanced
   - Context relevance scores

## Future Enhancements

### Planned Improvements

1. **Smarter Trigger Logic**
   - ML-based decision for when to enhance
   - Predict which storylines need enhancement
   - Dynamic thresholds based on story importance

2. **Multi-Source Context**
   - NewsAPI integration
   - Knowledge Graph API
   - Academic paper search

3. **Adaptive Caching**
   - Smart cache invalidation
   - Context-specific TTLs
   - Predictive pre-caching

4. **Real-Time Enhancement**
   - Stream updates to existing storylines
   - Incremental context addition
   - Event-driven enhancement

## Summary

The RAG enhancement strategy follows a **progressive, resource-aware approach**:

1. **Basic summaries first** (fast, immediate)
2. **Enhanced summaries later** (richer, contextual)
3. **Triggered intelligently** (when needed, not always)
4. **Optimized for resources** (caching, rate limiting)
5. **Graceful degradation** (falls back if services unavailable)

This ensures users get immediate value while the system builds richer context over time, all while respecting API limits and system resources.

