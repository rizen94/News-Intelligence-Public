# Troubleshooting Guide - News Intelligence System v3.0

**Last Updated**: September 26, 2025

## 🚨 Quick Diagnostics

### **System Health Check**
```bash
# Check if all services are running
docker ps

# Check system health
curl http://localhost:8000/api/health/

# Check web interface
curl http://localhost:80
```

### **Common Issues & Solutions**

## 🔧 Service Issues

### **API Not Responding**
**Symptoms**: 500 errors, connection refused, timeout
**Solutions**:
```bash
# Check API container status
docker ps | grep api

# Restart API container
docker restart news-intelligence-api

# Check API logs
docker logs news-intelligence-api --tail 50

# Check if port 8000 is available
netstat -tlnp | grep 8000
```

### **Database Connection Issues**
**Symptoms**: Database errors, connection timeouts
**Solutions**:
```bash
# Check database container
docker ps | grep postgres

# Restart database
docker restart news-intelligence-postgres

# Check database logs
docker logs news-intelligence-postgres --tail 50

# Test database connection
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;"
```

### **Frontend Not Loading**
**Symptoms**: 404 errors, blank page, connection refused
**Solutions**:
```bash
# Check nginx container
docker ps | grep nginx

# Restart nginx
docker restart news-intelligence-nginx

# Check nginx logs
docker logs news-intelligence-nginx --tail 50

# Check if port 80 is available
netstat -tlnp | grep 80
```

## 🐛 Error Messages

### **"generator object has no attribute 'query'"**
**Cause**: Database connection pattern issue
**Solution**: This was fixed in the latest update. Restart the API container:
```bash
docker restart news-intelligence-api
```

### **"column does not exist"**
**Cause**: Database schema mismatch
**Solution**: Check database schema and run migrations:
```bash
# Check table structure
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "\d articles"

# Check for missing columns
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'articles';"
```

### **"connection refused"**
**Cause**: Service not running or port conflict
**Solution**: Check service status and ports:
```bash
# Check all containers
docker ps

# Check port usage
netstat -tlnp | grep -E "(80|8000|5432|6379)"

# Restart all services
docker-compose down && docker-compose up -d
```

### **"invalid input syntax for type integer"**
**Cause**: Route conflict (e.g., /stats being caught by /{id} route)
**Solution**: This was fixed in the latest update. Restart the API container:
```bash
docker restart news-intelligence-api
```

## 🔍 Log Analysis

### **API Logs**
```bash
# View recent API logs
docker logs news-intelligence-api --tail 100

# Follow API logs in real-time
docker logs -f news-intelligence-api

# Search for errors
docker logs news-intelligence-api 2>&1 | grep -i error
```

### **Database Logs**
```bash
# View database logs
docker logs news-intelligence-postgres --tail 100

# Search for database errors
docker logs news-intelligence-postgres 2>&1 | grep -i error
```

### **Nginx Logs**
```bash
# View nginx logs
docker logs news-intelligence-nginx --tail 100

# Check access logs
docker logs news-intelligence-nginx 2>&1 | grep "GET /"
```

## 🔄 Recovery Procedures

### **Complete System Restart**
```bash
# Stop all services
docker-compose down

# Remove containers (if needed)
docker-compose down --volumes

# Start services
docker-compose up -d

# Wait for services to start
sleep 30

# Check health
curl http://localhost:8000/api/health/
```

### **Database Recovery**
```bash
# Check database status
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;"

# If database is corrupted, restore from backup
# (Backup procedures should be implemented)

# Reset database (WARNING: This will lose all data)
docker-compose down
docker volume rm news-intelligence_postgres_data
docker-compose up -d
```

### **File Synchronization Issues**
```bash
# Check if container files are up to date
docker exec news-intelligence-api ls -la /app/routes/

# Copy updated files to container
docker cp api/routes/articles.py news-intelligence-api:/app/routes/articles.py

# Restart API container
docker restart news-intelligence-api
```

## 📊 Performance Issues

### **Slow API Responses**
**Symptoms**: API responses > 1 second
**Solutions**:
```bash
# Check database performance
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT * FROM pg_stat_activity;"

# Check system resources
docker stats

# Check for memory leaks
docker exec news-intelligence-api ps aux
```

### **High Memory Usage**
**Symptoms**: System running out of memory
**Solutions**:
```bash
# Check memory usage
free -h
docker stats

# Restart services to free memory
docker-compose restart

# Check for memory leaks in logs
docker logs news-intelligence-api 2>&1 | grep -i memory
```

## 🔧 Maintenance

### **Regular Health Checks**
```bash
# Daily health check script
#!/bin/bash
echo "=== News Intelligence System Health Check ==="
echo "1. API Health:"
curl -s http://localhost:8000/api/health/ | jq .success
echo "2. Database:"
docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT 1;" > /dev/null && echo "OK" || echo "ERROR"
echo "3. Frontend:"
curl -s http://localhost:80 > /dev/null && echo "OK" || echo "ERROR"
echo "4. Container Status:"
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### **Log Rotation**
```bash
# Set up log rotation for Docker logs
# Add to /etc/docker/daemon.json:
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

## 📞 Getting Help

### **Before Asking for Help**
1. Check this troubleshooting guide
2. Run the health check script
3. Check the logs for errors
4. Try the recovery procedures

### **Information to Provide**
- System status output
- Error messages from logs
- Steps you've already tried
- System configuration details

### **Emergency Contacts**
- System administrator
- Development team
- Documentation: This guide and API reference

---

**Troubleshooting Guide**: 🟢 **UP TO DATE**  
**Last Updated**: September 26, 2025  
**Next Review**: Recommended monthly
