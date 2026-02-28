# Route Supervisor Service Documentation

**Date**: 2025-12-12  
**Version**: 4.0  
**Status**: ✅ **IMPLEMENTED**

---

## 🎯 **Overview**

The Route Supervisor is a comprehensive monitoring service that manages consistency between routes, monitors database connections, and logs breaks/disconnects between the database and API. It provides proactive detection of issues and maintains system health visibility.

---

## 🔧 **Features**

### **1. Route Health Monitoring**
- Monitors route accessibility and response times
- Detects route failures and degradation
- Tracks consecutive failures
- Validates route-to-database connections

### **2. Database Connection Monitoring**
- Checks database connectivity for all domains
- Monitors connection response times
- Detects disconnections and errors
- Tracks connection pool status

### **3. Schema Validation**
- Detects schema mismatches between routes and database
- Identifies missing columns
- Logs database errors from routes
- Validates domain-specific schemas

### **4. Issue Logging**
- Maintains a log of all issues
- Categorizes issues by type
- Tracks issue frequency
- Provides historical issue data

### **5. Automated Reporting**
- Generates comprehensive health reports
- Provides route and database summaries
- Identifies critical issues
- Tracks system degradation

---

## 📊 **Service Architecture**

### **Core Components**

1. **RouteSupervisor Class**
   - Main service class
   - Manages monitoring lifecycle
   - Coordinates health checks
   - Maintains health state

2. **RouteHealth**
   - Tracks individual route status
   - Monitors response times
   - Tracks failures
   - Validates database connections

3. **DatabaseConnectionHealth**
   - Monitors database connections
   - Tracks connection status
   - Measures response times
   - Detects errors

4. **RouteSupervisorReport**
   - Comprehensive system report
   - Aggregates all health data
   - Identifies issues and warnings
   - Provides actionable insights

---

## 🚀 **Usage**

### **Starting the Supervisor**

The supervisor can run in two modes:

1. **Manual Checks** (On-demand)
```python
from shared.services.route_supervisor import get_route_supervisor

supervisor = get_route_supervisor()
report = await supervisor.generate_report()
```

2. **Continuous Monitoring** (Background)
```python
supervisor = get_route_supervisor()
await supervisor.start_monitoring()  # Runs continuously
```

### **API Endpoints**

#### **Get Health Summary**
```bash
GET /api/v4/system-monitoring/route-supervisor/health
```

Returns:
```json
{
  "success": true,
  "route_health": {
    "status": "healthy",
    "total": 25,
    "healthy": 23,
    "degraded": 1,
    "unhealthy": 1
  },
  "database_health": {
    "status": "healthy",
    "total": 4,
    "connected": 4,
    "disconnected": 0,
    "errors": 0
  },
  "is_monitoring": true,
  "last_check": "2025-12-12T10:00:00"
}
```

#### **Get Comprehensive Report**
```bash
GET /api/v4/system-monitoring/route-supervisor/report
```

Returns detailed report with:
- Route health for all critical routes
- Database connection status for all domains
- List of issues and warnings
- Response times and error messages

#### **Get Recent Issues**
```bash
GET /api/v4/system-monitoring/route-supervisor/issues?hours=24&limit=100
```

Returns recent issues from the log.

#### **Check Specific Route**
```bash
GET /api/v4/system-monitoring/route-supervisor/routes/{route_path}?method=GET&domain=politics
```

Returns health status for a specific route.

#### **Trigger Immediate Check**
```bash
POST /api/v4/system-monitoring/route-supervisor/check-now
```

Triggers an immediate health check.

---

## 📋 **Configuration**

### **Supervisor Settings**

```python
supervisor = RouteSupervisor(
    check_interval_seconds=60  # Check every 60 seconds
)
```

### **Health Thresholds**

```python
supervisor.max_response_time_ms = 5000  # 5 seconds
supervisor.max_consecutive_failures = 3
supervisor.db_timeout_seconds = 5
```

---

## 🔍 **Monitoring Capabilities**

### **Route Status Types**

- **HEALTHY**: Route responding correctly
- **DEGRADED**: Route responding but slow
- **UNHEALTHY**: Route failing or erroring
- **UNKNOWN**: Route not yet checked

### **Connection Status Types**

- **CONNECTED**: Database connection working
- **DISCONNECTED**: Cannot connect to database
- **SLOW**: Connection working but slow (>1 second)
- **ERROR**: Connection error occurred

### **Issue Types**

- **route_unhealthy**: Route is failing
- **schema_mismatch**: Database schema doesn't match route expectations
- **database_connection**: Database connection issue
- **route_timeout**: Route taking too long to respond

---

## 📊 **Integration with System Monitoring**

The Route Supervisor integrates with the existing system monitoring:

1. **Health Checks**: Provides route and database health data
2. **Alerts**: Can trigger alerts for critical issues
3. **Metrics**: Tracks response times and failure rates
4. **Logging**: Logs all issues to system logs

---

## 🎯 **Use Cases**

### **1. Proactive Issue Detection**
Monitor routes continuously to detect issues before users report them.

### **2. Database Connection Monitoring**
Ensure all domain databases are accessible and responding.

### **3. Schema Validation**
Detect when database schema changes break API routes.

### **4. Performance Monitoring**
Track route response times and identify slow endpoints.

### **5. Issue Investigation**
Review issue logs to understand system problems.

---

## 🔧 **Implementation Details**

### **Route Health Check Process**

1. Substitute path parameters (domain, IDs, etc.)
2. Make HTTP request to route
3. Measure response time
4. Check response status
5. Validate database connection if domain route
6. Check for schema errors in response
7. Update health status
8. Log issues if found

### **Database Connection Check Process**

1. Get database connection
2. Set schema path for domain
3. Execute test query
4. Measure response time
5. Check connection pool status
6. Update connection health
7. Log issues if found

---

## 📈 **Benefits**

1. **Early Detection**: Catch issues before they affect users
2. **Consistency**: Ensure routes match database schemas
3. **Visibility**: Clear view of system health
4. **Debugging**: Historical issue logs for troubleshooting
5. **Automation**: Continuous monitoring without manual checks

---

## 🔄 **Future Enhancements**

1. **Alerting**: Integrate with alerting system
2. **Metrics Export**: Export metrics to Prometheus
3. **Dashboard**: Visual dashboard for route health
4. **Auto-Recovery**: Attempt automatic fixes for common issues
5. **Predictive Analysis**: Predict issues before they occur

---

## 📚 **Related Documentation**

- `ROUTE_AUDIT_REPORT.md` - Route audit findings
- `ROUTER_PREFIX_AUDIT_REPORT.md` - Router prefix standards
- `SYSTEM_MONITORING.md` - System monitoring documentation

---

*Last Updated: 2025-12-12*  
*Status: ✅ Implemented*

