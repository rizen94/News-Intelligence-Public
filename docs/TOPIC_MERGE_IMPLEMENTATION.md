# Topic Merge API Implementation

## Date: 2025-12-07
## Status: ✅ Complete

---

## Overview

Implemented the Topic Merge API endpoint to allow users to merge duplicate or similar topics into a single consolidated topic. This feature was identified as the highest priority incomplete feature.

---

## Implementation Details

### **Backend API Endpoint**

**Endpoint**: `POST /api/v4/topic-management/topics/merge`

**Request Model**:
```python
class TopicMerge(BaseModel):
    topic_ids: List[int]  # List of topic IDs to merge (minimum 2)
    keep_primary: bool = True  # Keep first topic as primary
```

**Response**:
```json
{
    "success": true,
    "data": {
        "primary_topic": {
            "id": 1,
            "name": "Primary Topic Name"
        },
        "merged_topics": [
            {"id": 2, "name": "Merged Topic 1"},
            {"id": 3, "name": "Merged Topic 2"}
        ],
        "merged_count": 2,
        "total_articles": 150,
        "message": "Successfully merged 2 topics into 'Primary Topic Name'"
    }
}
```

### **Merge Process**

The merge operation performs the following steps:

1. **Validation**
   - Verifies at least 2 topics are provided
   - Checks all topics exist
   - Prevents merging already-merged topics

2. **Primary Topic Selection**
   - First topic in the list becomes the primary topic
   - All other topics are merged into the primary

3. **Data Consolidation**
   - **Keywords**: Combines all keywords from merged topics (removes duplicates)
   - **Description**: Merges descriptions with separator
   - **Statistics**: Combines review counts, correct/incorrect assignments
   - **Scores**: Calculates weighted averages for confidence and accuracy

4. **Article Assignment Transfer**
   - Transfers all article assignments from merged topics to primary
   - Handles duplicate assignments (keeps highest confidence score)
   - Preserves validation status and feedback notes

5. **Status Update**
   - Updates primary topic with merged data
   - Marks merged topics as `'merged'` status
   - Updates timestamps

### **Frontend Integration**

**API Service Method**:
```typescript
mergeTopics: async(topicIds: number[]) => {
  const response = await api.post(
    '/api/v4/topic-management/topics/merge',
    {
      topic_ids: topicIds,
      keep_primary: true,
    },
  );
  return response.data;
}
```

**UI Integration**:
- Updated `handleMergeTopics` in `TopicManagement.js`
- Added success/error handling with snackbar notifications
- Automatically refreshes topic list after successful merge
- Shows loading state during merge operation

---

## Features

### ✅ **Implemented**

- Merge multiple topics into one
- Transfer all article assignments
- Combine keywords and descriptions
- Merge statistics (counts, scores)
- Handle duplicate assignments intelligently
- Mark merged topics appropriately
- Comprehensive error handling
- Frontend integration with user feedback

### **Edge Cases Handled**

1. **Duplicate Assignments**: If an article is assigned to multiple topics being merged, keeps the assignment with highest confidence
2. **Already Merged Topics**: Prevents merging topics that are already in 'merged' status
3. **Missing Topics**: Validates all topics exist before merging
4. **Empty Lists**: Requires at least 2 topics to merge
5. **Transaction Safety**: All operations in a single database transaction

---

## Database Schema Support

The merge operation uses existing schema features:

- `topics.status` field supports `'merged'` status
- `article_topic_assignments` has unique constraint on `(article_id, topic_id)`
- Foreign key constraints ensure data integrity
- ON CONFLICT handling for duplicate assignments

---

## Testing Recommendations

### **Manual Testing**

1. **Basic Merge**
   - Select 2 topics with different articles
   - Verify all articles transferred to primary
   - Check merged topics marked as 'merged'

2. **Duplicate Assignments**
   - Select topics that share article assignments
   - Verify highest confidence assignment is kept
   - Check no duplicate assignments created

3. **Statistics Merge**
   - Merge topics with different review counts
   - Verify combined statistics are correct
   - Check scores are recalculated properly

4. **Error Cases**
   - Try merging with only 1 topic (should fail)
   - Try merging non-existent topics (should fail)
   - Try merging already-merged topics (should fail)

### **API Testing**

```bash
# Merge topics
curl -X POST http://localhost:8000/api/v4/topic-management/topics/merge \
  -H "Content-Type: application/json" \
  -d '{
    "topic_ids": [1, 2, 3],
    "keep_primary": true
  }'
```

---

## Files Modified

### **Backend**
- `api/domains/content_analysis/routes/topic_management.py`
  - Added `TopicMerge` Pydantic model
  - Added `merge_topics` endpoint handler
  - Implemented merge logic with transaction safety

### **Frontend**
- `web/src/services/apiService.ts`
  - Added `mergeTopics` method

- `web/src/pages/Topics/TopicManagement.js`
  - Updated `handleMergeTopics` to call API
  - Added success/error handling
  - Added topic list refresh after merge

---

## Status

✅ **COMPLETE** - Topic merge API is fully implemented and integrated

- Backend endpoint: ✅ Implemented
- Frontend integration: ✅ Complete
- Error handling: ✅ Comprehensive
- Edge cases: ✅ Handled
- Documentation: ✅ Complete

---

*Implementation completed: 2025-12-07*

