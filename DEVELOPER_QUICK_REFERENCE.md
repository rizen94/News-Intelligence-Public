# 🚀 Developer Quick Reference Card

## ⚠️ **MANDATORY: READ BEFORE ANY UPDATE**

### **1. Field Mapping Quick Reference**

```javascript
// STORYLINES - CRITICAL FIELD MAPPINGS
storyline.story_id     // ✅ Use for storyline IDs (NOT storyline.id)
storyline.name         // ✅ Use for storyline title
storyline.priority_level // ✅ Use for priority (NOT storyline.priority)
storyline.is_active    // ✅ Use for status (NOT storyline.status)
storyline.keywords     // ✅ Use for targets (NOT storyline.targets)

// ARTICLES - Use consistent field names
article.id            // ✅ Use for article IDs
article.title         // ✅ Use for article title
article.content       // ✅ Use for article content
```

### **2. Button Handler Naming**

```javascript
// CRUD Operations
handleCreateStoryline()  // ✅ Create storyline
handleEditStoryline()    // ✅ Edit storyline  
handleDeleteStoryline()  // ✅ Delete storyline
handleViewArticle()      // ✅ View article

// Navigation
handleArticleClick()     // ✅ Article click
handleStorylineClick()   // ✅ Storyline click
handleBackNavigation()   // ✅ Back navigation
```

### **3. API Response Format**

```javascript
// ALL API responses MUST follow this format:
{
  "success": boolean,
  "data": any,
  "message": string,
  "error": string
}
```

### **4. Common Mistakes to Avoid**

```javascript
// ❌ WRONG - Using wrong ID field
onClick={() => handleStorylineClick(storyline.id)}

// ✅ CORRECT - Using correct ID field  
onClick={() => handleStorylineClick(storyline.story_id)}

// ❌ WRONG - Using wrong field names
storyline.priority, storyline.status, storyline.targets

// ✅ CORRECT - Using correct field names
storyline.priority_level, storyline.is_active, storyline.keywords
```

### **5. Pre-Update Checklist**

- [ ] Read CODING_STYLE_GUIDE.md
- [ ] Check field mappings in API section
- [ ] Verify ID field usage
- [ ] Test all button functionality
- [ ] Check API response format
- [ ] Validate form submissions
- [ ] Test navigation

### **6. Port Configuration**

```bash
3000 - React Development Server
3001 - React Production Server  
8000 - FastAPI Backend API
5432 - PostgreSQL Database
6379 - Redis Cache
11434 - Ollama API (for ML timeline generation)
```

### **7. Timeline API Endpoints**

```javascript
// Timeline-specific API calls
const timelineEndpoints = {
  getTimeline: `/api/storyline-timeline/${storylineId}`,
  getEvents: `/api/storyline-timeline/${storylineId}/events`,
  getMilestones: `/api/storyline-timeline/${storylineId}/milestones`
};
```

### **8. Environment Variables**

```bash
DB_USER=newsapp
DB_PASSWORD=newsapp123
API_BASE_URL=http://localhost:8000
REACT_APP_API_BASE_URL=http://localhost:8000
```

---

## 🔧 **Quick Fixes for Common Issues**

### **Issue: Button not working**
1. Check onClick handler name follows convention
2. Verify correct ID field is used
3. Check API service function exists
4. Test error handling

### **Issue: Form not submitting**
1. Check field mapping in form data
2. Verify API endpoint exists
3. Check response format handling
4. Test validation

### **Issue: Navigation not working**
1. Check route parameter names
2. Verify useParams() usage
3. Check navigate() calls
4. Test route definitions

### **Issue: Data not displaying**
1. Check API response format
2. Verify field mapping
3. Check data structure
4. Test loading states

---

**Remember: Always reference the full CODING_STYLE_GUIDE.md for complete details!**
