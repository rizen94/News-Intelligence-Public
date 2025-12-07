# RAG System Enhancements

## Overview
The RAG (Retrieval-Augmented Generation) system has been significantly enhanced with advanced retrieval techniques, improved entity extraction, and multi-signal re-ranking.

## Key Enhancements

### 1. Enhanced RAG Retrieval Service (`services/enhanced_rag_retrieval.py`)
A comprehensive retrieval service that implements multiple advanced techniques:

#### **Semantic Search**
- Uses sentence transformers (`all-MiniLM-L6-v2`) for embedding-based semantic matching
- Computes cosine similarity between query and article embeddings
- Better understands meaning beyond keyword matching

#### **Hybrid Search**
- Combines keyword and semantic search results
- Configurable weighting (default: 70% semantic, 30% keyword)
- Merges results intelligently to get best of both worlds

#### **Query Expansion**
- Automatically expands queries with synonyms and related terms
- Includes plural/singular variations
- Improves recall by finding articles with different terminology

#### **Multi-Signal Re-Ranking**
Re-ranks results using multiple signals:
- **Relevance Score** (40%): Semantic/keyword match quality
- **Quality Score** (20%): Article quality metrics
- **Recency Score** (20%): How recent the article is (boost for last 7 days)
- **Title Match** (10%): Exact keyword matches in title
- **Credibility Score** (10%): Source credibility

### 2. Enhanced Entity Extraction (`services/enhanced_entity_extractor.py`)
Improved entity extraction with better accuracy:

#### **Entity Types**
- **People**: Names with titles (Mr, Dr, President, etc.)
- **Organizations**: Companies, agencies, universities
- **Locations**: Cities, states, countries, addresses
- **Topics**: Subject matter keywords
- **Products**: Technology, products, branded items
- **Events**: Conferences, awards, incidents

#### **Improvements**
- Pattern-based extraction with validation
- Context-aware extraction (e.g., "X said" patterns)
- Deduplication and filtering
- Stop word filtering

### 3. Integration with Existing RAG Services
The enhanced services are integrated into:
- `modules/ml/rag_enhanced_service.py`: Uses enhanced retrieval and entity extraction
- Falls back gracefully if enhanced services aren't available
- Maintains backward compatibility

## Usage

### Basic Usage
```python
from services.enhanced_rag_retrieval import EnhancedRAGRetrieval

# Initialize
retrieval = EnhancedRAGRetrieval(db_config)

# Retrieve articles
articles = await retrieval.retrieve_relevant_articles(
    query="artificial intelligence policy",
    max_results=25,
    use_semantic=True,
    use_hybrid=True,
    expand_query=True,
    rerank=True
)
```

### Advanced Usage
```python
# With filters
articles = await retrieval.retrieve_relevant_articles(
    query="climate change",
    max_results=20,
    filters={
        'min_quality': 0.6,
        'date_from': datetime.now() - timedelta(days=30),
        'min_word_count': 500
    }
)
```

### Entity Extraction
```python
from services.enhanced_entity_extractor import EnhancedEntityExtractor

extractor = EnhancedEntityExtractor()
entities = extractor.extract_entities(
    text="President Biden announced new AI regulations...",
    context="technology policy"
)
# Returns: {
#   'people': ['President Biden'],
#   'organizations': [],
#   'locations': [],
#   'topics': ['AI', 'Technology', 'Regulations'],
#   ...
# }
```

## Configuration

### Retrieval Configuration
```python
config = {
    'embedding_model': 'all-MiniLM-L6-v2',
    'max_results_initial': 100,
    'max_results_final': 25,
    'hybrid_search_alpha': 0.7,  # Semantic weight
    'similarity_threshold': 0.3,
    'rerank_top_k': 50,
    'query_expansion_max_terms': 5,
}
```

## Performance Considerations

1. **Embeddings**: First load may take time; subsequent uses are fast
2. **Hybrid Search**: Slightly slower than keyword-only but much more accurate
3. **Re-ranking**: Only applies when multiple results are found
4. **Entity Extraction**: Processes first 10 articles for performance

## Dependencies

### Required
- `sentence-transformers`: For semantic embeddings
- `numpy`: For vector operations
- `psycopg2`: Database access

### Installation
```bash
pip install sentence-transformers numpy psycopg2-binary
```

## Benefits

### Improved Accuracy
- Semantic understanding finds relevant articles even without exact keyword matches
- Hybrid approach combines precision (keywords) with recall (semantics)

### Better Entity Extraction
- More accurate entity identification
- Better classification (people, organizations, locations)
- Reduces false positives

### Smarter Ranking
- Multiple signals ensure best articles surface first
- Recency boost for fresh content
- Quality filtering improves overall results

## Future Enhancements

### Potential Improvements
1. **Vector Database**: Use dedicated vector DB (Pinecone, Weaviate) for faster semantic search
2. **Advanced NER**: Integrate spaCy or similar for better entity extraction
3. **Query Understanding**: Use LLM for query interpretation and expansion
4. **Personalization**: User-specific ranking signals
5. **Embedding Caching**: Cache embeddings in database for faster retrieval
6. **Batch Processing**: Batch embedding generation for better performance

## Testing

### Test Enhanced Retrieval
```python
# Test semantic search
articles = await retrieval.retrieve_relevant_articles(
    query="machine learning regulations",
    use_semantic=True,
    use_hybrid=False
)

# Test hybrid search
articles = await retrieval.retrieve_relevant_articles(
    query="machine learning regulations",
    use_hybrid=True
)

# Compare results
```

## Backward Compatibility

The enhancements are fully backward compatible:
- Existing code continues to work
- Falls back to basic keyword search if enhanced services unavailable
- No breaking changes to API

## Migration Notes

### For Existing Code
1. Enhanced services automatically used if available
2. No code changes required
3. Optional: Explicitly use enhanced services for better results

### Database Changes
- No schema changes required
- Embeddings stored in `metadata` JSONB field (optional)
- Can be added incrementally

