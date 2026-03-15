# API Testing Guide

**Date**: 2025-01-27  
**Status**: ✅ **CODE VERIFIED - READY FOR RUNTIME TESTING**

---

## ✅ **Code Verification Complete**

### **1. Route Definitions** ✅
- ✅ All routes properly defined in `main_v4.py`
- ✅ Domain routes use correct path parameters
- ✅ Pagination parameters implemented correctly
- ✅ Response formats standardized

### **2. Frontend-Backend Alignment** ✅
- ✅ Frontend API calls match backend routes
- ✅ Pagination mapping implemented (`page` → `offset`)
- ✅ Response format matches frontend expectations (`data.total`)

### **3. Database Query Structure** ✅
- ✅ Domain-aware services query correct schemas
- ✅ Pagination queries use `LIMIT` and `OFFSET`
- ✅ Total count queries implemented

---

## 🧪 **Runtime Testing Required**

### **Prerequisites**

1. **Start API Server**:
   ```bash
   cd api
   python3 main_v4.py
   # Or: uvicorn main_v4:app --host 0.0.0.0 --port 8000
   ```

2. **Set Database Environment Variables** (if needed):
   ```bash
   export DB_HOST=localhost  # or 192.168.93.100 for NAS
   export DB_PORT=5433        # or 5432
   export DB_NAME=news_intelligence
   export DB_USER=newsapp
   export DB_PASSWORD=newsapp_password
   ```

3. **Verify Database Schemas Exist**:
   - Check that `politics`, `finance`, `science_tech` schemas exist
   - Verify tables exist: `articles`, `storylines`, `rss_feeds`

---

## 📋 **Test Checklist**

### **Test 1: Health Check**
```bash
curl http://localhost:8000/api/system_monitoring/health
```
**Expected**: `{"success": true, ...}`

### **Test 2: Articles Endpoint**
```bash
# Test pagination
curl "http://localhost:8000/api/politics/articles?limit=10&offset=0"
```
**Expected**:
- Status: 200
- Response includes `data.articles` array
- Response includes `data.total` number
- Response includes `data.limit` and `data.offset`

### **Test 3: Storylines Endpoint**
```bash
curl "http://localhost:8000/api/politics/storylines?limit=10&offset=0"
```
**Expected**:
- Status: 200
- Response includes `data.storylines` array
- Response includes `data.total` number

### **Test 4: RSS Feeds Endpoint**
```bash
curl "http://localhost:8000/api/politics/rss_feeds"
```
**Expected**:
- Status: 200
- Response includes `data.feeds` array
- Response includes `data.total` number

### **Test 5: Pagination**
```bash
# Page 1
curl "http://localhost:8000/api/politics/articles?limit=5&offset=0"

# Page 2
curl "http://localhost:8000/api/politics/articles?limit=5&offset=5"
```
**Expected**:
- Different articles returned
- No overlap between pages
- Total count consistent

### **Test 6: All Domains**
Test each domain:
- `politics`
- `finance`
- `science-tech`

---

## 🚀 **Quick Test Script**

Run the automated test script:

```bash
cd api
./test_api_endpoints.sh
```

Or with custom API URL:
```bash
API_BASE_URL=http://localhost:8000 ./test_api_endpoints.sh
```

---

## ✅ **Frontend Verification**

Once API is running, verify frontend can repopulate:

1. **Start Frontend**:
   ```bash
   cd web
   npm start
   ```

2. **Check Browser Console**:
   - No API errors
   - Articles load correctly
   - Storylines load correctly
   - RSS feeds load correctly

3. **Verify Data Display**:
   - Articles page shows articles from database
   - Storylines page shows storylines from database
   - RSS Feeds page shows feeds from database
   - Pagination works correctly

---

## 📊 **Expected Results**

### **If Database Has Data**:
- ✅ All endpoints return 200 status
- ✅ Response includes data arrays
- ✅ Total counts match database records
- ✅ Pagination works correctly

### **If Database Is Empty**:
- ✅ All endpoints return 200 status
- ✅ Response includes empty arrays
- ✅ Total counts are 0
- ✅ No errors in frontend

### **If Database Schemas Don't Exist**:
- ❌ Endpoints return 500 errors
- ❌ Error messages indicate schema issues
- **Action**: Run database migrations

---

## 🔧 **Troubleshooting**

### **Issue: Cannot Connect to API**
- Check API server is running: `curl http://localhost:8000/`
- Check port 8000 is not in use
- Check firewall settings

### **Issue: Database Connection Errors**
- Verify `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- Check database server is accessible
- Verify SSH tunnel (if using NAS database)

### **Issue: Schema Not Found Errors**
- Run database migrations
- Check `domains` table exists
- Verify domain schemas are created

### **Issue: Empty Responses**
- Check database has data
- Verify domain schemas have tables
- Check data exists in correct schemas

---

## 📝 **Test Results Template**

```
Date: ___________
API Server: [ ] Running [ ] Not Running
Database: [ ] Connected [ ] Not Connected

Health Check: [ ] Pass [ ] Fail
Articles Endpoint: [ ] Pass [ ] Fail
Storylines Endpoint: [ ] Pass [ ] Fail
RSS Feeds Endpoint: [ ] Pass [ ] Fail
Pagination: [ ] Pass [ ] Fail

Notes:
_______________________________________
_______________________________________
```

---

**Status**: ✅ **CODE VERIFIED - AWAITING RUNTIME TESTING**


