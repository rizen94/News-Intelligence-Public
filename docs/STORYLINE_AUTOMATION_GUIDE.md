# Storyline Automation & RAG Enhancement Guide

## Overview

The Storyline Automation system provides **RAG-enhanced article discovery** with **configurable automation controls**, allowing you to balance automation with manual oversight.

## Key Features

### 1. **RAG-Enhanced Article Discovery**
- **Semantic Search**: Finds articles based on meaning, not just keywords
- **Hybrid Search**: Combines keyword and semantic matching
- **Query Expansion**: Automatically expands search terms with related concepts
- **Multi-Signal Re-Ranking**: Scores articles using relevance, quality, recency, and credibility

### 2. **Automation Modes**

#### **Disabled** (default)
- No automation
- Manual article addition only

#### **Manual** (Suggestions Only)
- Discovers relevant articles
- Adds them to a **review queue**
- Requires manual approval before adding

#### **Auto-Approve** (High Confidence)
- Discovers relevant articles
- Automatically adds articles above threshold
- Lower threshold articles still go to review queue

#### **Review Queue** (Full Control)
- All discovered articles go to review queue
- You review and approve/reject each one
- Maximum control over content quality

### 3. **Configurable Controls**

Each storyline has its own automation settings:

```json
{
  "min_relevance_score": 0.6,      // Minimum relevance to suggest
  "min_quality_score": 0.5,         // Minimum article quality
  "min_semantic_score": 0.55,       // Minimum semantic similarity
  "max_articles_per_run": 20,       // Max articles to suggest per run
  "date_range_days": 30,            // Look back this many days
  "source_diversity": true,         // Prefer diverse sources
  "exclude_duplicates": true,       // Skip duplicate content
  "use_rag_expansion": true,        // Use RAG query expansion
  "rerank_results": true            // Re-rank with multiple signals
}
```

### 4. **Search Parameters**

- **Keywords**: Specific terms to search for
- **Entities**: People, organizations, locations to track
- **Exclude Keywords**: Terms to filter out
- **Frequency**: How often to run automation (hours)

## Usage

All automation endpoints use `/api/{domain}/storylines/...` where `{domain}` is one of `politics`, `finance`, or `science-tech`.

### Setting Up Automation

1. **Enable Automation for a Storyline**

```bash
PUT /api/{domain}/storylines/{storyline_id}/automation/settings
```

```json
{
  "automation_enabled": true,
  "automation_mode": "manual",
  "search_keywords": ["Ukraine", "Russia", "conflict"],
  "search_entities": ["Volodymyr Zelensky", "Vladimir Putin"],
  "search_exclude_keywords": ["advertisement", "sponsored"],
  "frequency_hours": 24,
  "settings": {
    "min_relevance_score": 0.6,
    "min_quality_score": 0.5,
    "max_articles_per_run": 20,
    "date_range_days": 30
  }
}
```

### Discovering Articles

2. **Trigger Article Discovery**

```bash
POST /api/{domain}/storylines/{storyline_id}/automation/discover?force_refresh=true
```

This will:
- Use RAG to find relevant articles
- Score them using multiple signals
- Store suggestions in review queue (or auto-add if mode is `auto_approve`)

### Managing Suggestions

3. **View Pending Suggestions**

```bash
GET /api/{domain}/storylines/{storyline_id}/automation/suggestions
```

Returns:
- Articles sorted by combined score
- Relevance, semantic, keyword, and quality scores
- Matched keywords and entities
- Reasoning for why article was suggested

4. **Approve a Suggestion**

```bash
POST /api/{domain}/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/approve
```

Adds the article to the storyline.

5. **Reject a Suggestion**

```bash
POST /api/{domain}/storylines/{storyline_id}/automation/suggestions/{suggestion_id}/reject?reason=Not relevant
```

Marks the suggestion as rejected.

## Automation Workflow

### Example: Ukraine Storyline

1. **Initial Setup:
   ```json
   {
     "automation_enabled": true,
     "automation_mode": "manual",
     "search_keywords": ["Ukraine", "Russia", "war", "conflict"],
     "search_entities": ["Zelensky", "Putin", "Kyiv", "Moscow"],
     "frequency_hours": 12
   }
   ```

2. **System Runs Discovery** (every 12 hours):
   - Searches articles from last 30 days
   - Uses semantic similarity to "Ukraine conflict"
   - Scores each article
   - Adds high-scoring articles to review queue

3. **You Review Suggestions**:
   - View pending suggestions in UI
   - See scores and reasoning
   - Approve relevant articles
   - Reject off-topic articles

4. **System Learns** (future):
   - Tracks your approval/rejection patterns
   - Adjusts scoring weights
   - Improves relevance over time

## Database Schema

### New Tables

- **`storyline_article_suggestions`**: Review queue for suggested articles
- **`storyline_automation_log`**: History of automation runs

### New Columns on `storylines`

- `automation_enabled`: Boolean
- `automation_mode`: 'disabled' | 'manual' | 'auto_approve' | 'review_queue'
- `automation_settings`: JSONB configuration
- `search_keywords`: TEXT[] keywords to search
- `search_entities`: TEXT[] entities to track
- `search_exclude_keywords`: TEXT[] terms to exclude
- `automation_frequency_hours`: How often to run
- `last_automation_run`: Timestamp of last run

## Best Practices

### For Maximum Control
- Use `automation_mode: "manual"` or `"review_queue"`
- Set higher thresholds (`min_relevance_score: 0.7+`)
- Review suggestions regularly
- Update exclude keywords based on rejections

### For Balanced Automation
- Use `automation_mode: "auto_approve"`
- Set moderate thresholds (`min_relevance_score: 0.65`)
- Periodically review auto-added articles
- Monitor storyline quality

### For Maximum Automation
- Use `automation_mode: "auto_approve"`
- Set lower thresholds (`min_relevance_score: 0.55`)
- Set shorter frequency (6-12 hours)
- Monitor closely for off-topic articles

## Troubleshooting

### Too Many Suggestions
- Increase `min_relevance_score`
- Add more `search_exclude_keywords`
- Reduce `max_articles_per_run`

### Too Few Suggestions
- Decrease `min_relevance_score`
- Add more `search_keywords`
- Increase `date_range_days`
- Check if articles exist in database

### Poor Quality Suggestions
- Increase `min_quality_score`
- Review and refine `search_keywords`
- Add better `search_entities`
- Check RAG service status

## Migration

Run the migration to add automation support:

```bash
psql -U newsapp -d news_intelligence -f api/database/migrations/120_storyline_automation_settings.sql
```

## API Endpoints Summary

- `GET /storylines/{id}/automation/settings` - Get settings
- `PUT /storylines/{id}/automation/settings` - Update settings
- `POST /storylines/{id}/automation/discover` - Trigger discovery
- `GET /storylines/{id}/automation/suggestions` - View suggestions
- `POST /storylines/{id}/automation/suggestions/{id}/approve` - Approve
- `POST /storylines/{id}/automation/suggestions/{id}/reject` - Reject

