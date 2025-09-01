# Docker Cleanup Strategy

## 🚨 Current Docker State Analysis

### **Space Usage Breakdown**
- **Images**: 17.09GB (15.92GB reclaimable - 93%)
- **Containers**: 1.37kB (598B reclaimable - 43%)
- **Volumes**: 14.07GB (268.5MB reclaimable - 1%)
- **Build Cache**: 9.17GB (9.17GB reclaimable - 100%)
- **Total reclaimable**: ~25.2GB

### **Problem Areas Identified**

#### **1. Dangling Images (Major Issue)**
- **Multiple `<none>` images** at 7.81GB each
- **Failed builds** creating orphaned images
- **Old versions** not cleaned up

#### **2. Large Volumes**
- **PostgreSQL data**: 13GB (news-system_news_pgdata)
- **Build cache**: 9.17GB (all reclaimable)
- **Unused volumes**: Taking up space

#### **3. Build Cache**
- **133 build cache entries** at 9.17GB
- **All reclaimable** (0 active builds)

## 🧹 Docker Cleanup Plan

### **Phase 1: Safe Cleanup (Immediate)**
```bash
# Remove dangling images (safe)
docker image prune -f

# Remove unused containers
docker container prune -f

# Remove unused networks
docker network prune -f

# Remove build cache (safe if no active builds)
docker builder prune -f
```

### **Phase 2: Volume Management (Careful)**
```bash
# List volumes with sizes
docker volume ls -q | xargs -I {} docker run --rm -v {}:/vol busybox sh -c "du -sh /vol 2>/dev/null || echo 'Cannot access'"

# Remove unused volumes (BE CAREFUL - this deletes data)
docker volume prune -f

# Remove specific large volumes (if confirmed safe)
docker volume rm news-system_news_pgdata  # 13GB PostgreSQL data
```

### **Phase 3: Image Cleanup (Selective)**
```bash
# Remove specific large images
docker rmi $(docker images -q --filter "dangling=true")

# Remove old versions of images
docker image prune -a --filter "until=24h"

# Keep only latest versions
docker images --format "{{.Repository}}:{{.Tag}}" | grep -v "latest" | xargs -r docker rmi
```

### **Phase 4: System Cleanup (Aggressive)**
```bash
# Full system cleanup (removes everything unused)
docker system prune -a --volumes -f

# Remove all stopped containers
docker rm $(docker ps -aq)

# Remove all unused images
docker rmi $(docker images -aq)
```

## 🔧 Implementation Steps

### **Step 1: Stop Services (Safety First)**
```bash
# Stop all running containers
docker stop $(docker ps -q)

# Or stop specific services
docker stop dockside-proxy dockside-api dockside-pgadmin dockside-landingpage
```

### **Step 2: Backup Important Data**
```bash
# Backup PostgreSQL data if needed
docker run --rm -v news-system_news_pgdata:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .

# Backup other important volumes
docker run --rm -v news-system_news_data:/data -v $(pwd):/backup alpine tar czf /backup/news_data_backup.tar.gz -C /data .
```

### **Step 3: Execute Cleanup**
```bash
# Safe cleanup first
docker image prune -f
docker container prune -f
docker network prune -f
docker builder prune -f

# Check space reclaimed
docker system df
```

### **Step 4: Volume Assessment**
```bash
# Check which volumes are actually needed
docker volume ls

# Remove unused volumes (BE CAREFUL)
docker volume prune -f

# Remove specific large volumes if confirmed safe
# docker volume rm news-system_news_pgdata
```

### **Step 5: Image Cleanup**
```bash
# Remove dangling images
docker rmi $(docker images -q --filter "dangling=true")

# Remove old versions
docker image prune -a --filter "until=24h"
```

## 📊 Expected Results

### **Space Reclaimed**
- **Dangling images**: 7-15GB (multiple 7.81GB images)
- **Build cache**: 9.17GB (100% reclaimable)
- **Unused volumes**: 1-5GB (depending on what's safe to remove)
- **Total expected**: 15-25GB

### **Performance Improvements**
- **Docker operations**: 2-3x faster
- **Disk I/O**: Reduced significantly
- **System responsiveness**: Improved
- **Build times**: Faster (cleaner cache)

## ⚠️ Safety Considerations

### **Before Cleanup**
1. **Stop all services** that might be using volumes
2. **Backup important data** from volumes
3. **Verify volume contents** before deletion
4. **Check container dependencies**

### **Volume Safety Check**
```bash
# Check which containers use each volume
docker ps -a --format "{{.Names}}" | xargs -I {} docker inspect {} --format "{{.Name}}: {{.Mounts}}"

# Check volume usage
docker volume ls -q | xargs -I {} sh -c "echo 'Volume: {}'; docker ps -a --filter volume={} --format '{{.Names}}'"
```

### **Data Preservation**
- **PostgreSQL data**: Backup before removing
- **Application data**: Verify importance
- **Logs**: Archive if needed
- **Build artifacts**: Confirm not needed

## 🚀 Post-Cleanup Optimization

### **Docker Configuration**
```bash
# Set up automatic cleanup
echo '{"experimental": true, "features": {"buildkit": true}}' | sudo tee /etc/docker/daemon.json

# Restart Docker daemon
sudo systemctl restart docker
```

### **Automated Cleanup Script**
```bash
#!/bin/bash
# Daily Docker cleanup script

# Remove dangling images
docker image prune -f

# Remove unused containers
docker container prune -f

# Remove build cache older than 7 days
docker builder prune --filter "until=168h" -f

# Log cleanup results
echo "$(date): Docker cleanup completed" >> /var/log/docker-cleanup.log
```

### **Volume Management Strategy**
```bash
# Use named volumes instead of bind mounts
# Implement volume rotation
# Set up automated backups
# Monitor volume growth
```

## 📈 Success Metrics

### **Immediate Goals**
- [ ] Remove dangling images (7-15GB)
- [ ] Clear build cache (9.17GB)
- [ ] Clean unused containers
- [ ] Assess volume usage

### **Short Term Goals**
- [ ] Implement automated cleanup
- [ ] Optimize volume strategy
- [ ] Set up monitoring
- [ ] Document cleanup procedures

### **Long Term Goals**
- [ ] Prevent accumulation of unused resources
- [ ] Implement volume lifecycle management
- [ ] Optimize build processes
- [ ] Establish cleanup policies

## 🎯 Implementation Priority

### **Priority 1: Safe Cleanup (Today)**
1. Stop services
2. Backup important data
3. Execute safe cleanup commands
4. Verify space reclaimed

### **Priority 2: Volume Assessment (This Week)**
1. Analyze volume usage
2. Identify safe removals
3. Execute volume cleanup
4. Implement monitoring

### **Priority 3: Optimization (Next Week)**
1. Implement automated cleanup
2. Optimize build processes
3. Document procedures
4. Train team

This Docker cleanup will complement the system cleanup and provide a comprehensive solution for reclaiming space and improving performance.
