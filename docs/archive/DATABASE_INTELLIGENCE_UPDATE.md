# Database Intelligence System Update v2.1.0

## Overview

This document outlines the comprehensive database schema updates required to support the News Intelligence System v2.1.0. The updates provide proper status tracking, data separation, RAG system support, and intelligent cleanup protection.

## Key Changes

### 1. Articles Table Enhancements

The existing `articles` table is enhanced with new columns to support the intelligence pipeline:

#### New Columns Added:
- **`processing_status`** (VARCHAR(50)): Tracks article processing state
  - `raw` (default): Newly ingested articles
  - `processing`: Currently being processed
  - `ml_processed`: Successfully processed by ML pipeline
  - `processing_error`: Failed processing
  
- **`ml_data`** (JSONB): Stores ML processing results and metadata
  
- **`rag_keep_longer`** (BOOLEAN): Flag to prevent cleanup for RAG research
  
- **`rag_context_needed`** (BOOLEAN): Indicates need for additional context research
  
- **`rag_priority`** (INTEGER): Priority level for RAG processing (0=normal, higher=more important)
  
- **`processing_started_at`** (TIMESTAMP): When processing began
  
- **`processing_completed_at`** (TIMESTAMP): When processing completed

### 2. New Tables Created

#### Processed Articles Table (`processed_articles`)
- **Separates processed content from raw RSS data**
- Stores cleaned, segmented content ready for ML processing
- Includes quality scores, key phrases, and content metrics
- Links back to original article via `original_article_id`

#### RAG System Tables
- **`rag_context_requests`**: Tracks requests for additional context
- **`rag_research_topics`**: Defines research topics and priorities
- **`rag_research_sessions`**: Tracks individual research sessions

#### Intelligence Processing Tables
- **`article_clusters`**: Groups similar articles for ML processing
- **`ml_datasets`**: Manages ML dataset configurations
- **`ml_dataset_content`**: Stores actual dataset content
- **`intelligence_pipeline_results`**: Tracks pipeline execution

#### Cleanup Protection System
- **`cleanup_protection_rules`**: Defines rules for protecting articles from cleanup

### 3. Data Separation Strategy

#### Raw vs. Processed Data
- **Raw articles** remain in the `articles` table with status tracking
- **Processed content** moves to `processed_articles` table
- **ML datasets** are stored separately for training and analysis
- **RAG research data** is organized by topic and session

#### Benefits:
- Prevents accidental deletion of important research data
- Enables efficient ML processing on clean, structured data
- Maintains data lineage and traceability
- Supports incremental processing and updates

### 4. RAG System Integration

#### Context Request Management
- Articles can be marked for additional context research
- Priority levels determine research order and resource allocation
- Research sessions track progress and results
- Context data is stored with confidence scores and sources

#### Research Topic Management
- Configurable research frequencies (hourly, daily, weekly)
- Automatic topic tracking and evolution
- Integration with cleanup protection system

### 5. Cleanup Protection System

#### Protection Rules
- **RAG Keep Longer**: Protects articles marked for extended research (90-365 days)
- **RAG Context Needed**: Protects articles needing context research (60-180 days)
- **High Priority**: Protects high-priority articles (30-90 days)
- **Research Topics**: Protects articles related to active research (90-365 days)

#### Smart Cleanup Process
- Only removes articles that are safe to delete
- Respects all protection rules and RAG flags
- Provides dry-run mode for safety
- Generates recommendations based on system state

## Implementation Steps

### Step 1: Update Database Schema
```bash
# Update the database schema
python api/manage_intelligence_database.py update-schema
```

### Step 2: Verify Schema Update
```bash
# Check system status
python api/manage_intelligence_database.py status
```

### Step 3: Mark Articles for Processing
```bash
# Mark all raw articles for processing
python api/manage_intelligence_database.py mark-processing
```

### Step 4: Mark Articles for RAG Research
```bash
# Mark specific articles for RAG processing
python api/manage_intelligence_database.py mark-rag --article-ids 1,2,3 --priority 2
```

### Step 5: Test Smart Cleanup
```bash
# Dry run cleanup to see what would be removed
python api/manage_intelligence_database.py cleanup --dry-run --max-age 30

# Get cleanup recommendations
python api/manage_intelligence_database.py cleanup-recommendations
```

## Database Functions

### ML Processing Statistics
- **`get_ml_processing_stats()`**: Comprehensive processing statistics
- **`get_articles_needing_rag_context()`**: Articles requiring RAG research
- **`get_cleanup_protection_status(article_id)`**: Protection status for specific articles
- **`mark_article_for_rag(article_id, context_needed, keep_longer, priority)`**: Mark articles for RAG

## Performance Considerations

### Indexes Created
- Processing status and RAG flags for fast filtering
- Timestamps for efficient date-based queries
- Foreign keys for relationship lookups
- JSONB indexes for ML data queries

### Query Optimization
- Efficient status-based filtering
- Batch operations for large datasets
- Connection pooling and timeout protection
- Transaction management for data consistency

## Security Features

### Data Protection
- Cleanup protection prevents accidental data loss
- RAG flags preserve important research data
- Transaction rollback on errors
- Comprehensive logging and audit trails

### Access Control
- Database user permissions properly configured
- Connection timeout protection
- Statement timeout limits
- Secure environment variable configuration

## Monitoring and Maintenance

### System Health Checks
- Schema update verification
- Processing pipeline status
- Cleanup protection effectiveness
- RAG system performance

### Maintenance Tasks
- Regular cleanup with protection rules
- RAG research priority management
- Processing pipeline optimization
- Database performance monitoring

## Migration Notes

### From Previous Versions
- Existing articles automatically get `processing_status = 'raw'`
- RAG flags default to `FALSE` for backward compatibility
- New tables are created alongside existing ones
- No data loss during migration

### Future Considerations
- Schema designed for ML model integration
- Scalable architecture for large datasets
- Support for advanced RAG capabilities
- Integration with external research APIs

## Troubleshooting

### Common Issues
1. **Schema Update Failures**: Check database permissions and connection
2. **Processing Status Issues**: Verify column existence and constraints
3. **Cleanup Protection**: Review protection rules and article flags
4. **RAG System**: Check topic configuration and research priorities

### Debug Commands
```bash
# Check database connection
python api/manage_intelligence_database.py status

# Verify schema tables
python -c "import psycopg2; conn = psycopg2.connect('your_connection_string'); cursor = conn.cursor(); cursor.execute('SELECT table_name FROM information_schema.tables WHERE table_schema = \\'public\\''); print(cursor.fetchall())"

# Test smart pruner
python api/modules/ingestion/smart_article_pruner.py
```

## Conclusion

The database intelligence system update provides a robust foundation for:
- **Intelligent article processing** with status tracking
- **RAG system integration** for context research
- **Smart cleanup protection** preventing data loss
- **ML pipeline support** for advanced processing
- **Scalable architecture** for future enhancements

This update transforms the system from simple RSS aggregation to a comprehensive news intelligence platform capable of advanced analysis, research, and ML processing.
