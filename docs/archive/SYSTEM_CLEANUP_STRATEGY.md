# System Cleanup & NAS Mount Strategy

## 🚨 Current Space Issues

### **Large Files Identified**
- **21GB backup directory**: `../news-system-backup-20250826_090951/`
- **2.6GB export zip**: `../news-system-export.zip`
- **752MB virtual environment**: `../venv/`
- **Total waste**: ~24.4GB of unnecessary files

### **Why This Happened**
1. **Backup files** created during development
2. **Export files** from testing/development
3. **Virtual environment** in wrong location
4. **No NAS mount** for large data storage

## 🧹 Immediate Cleanup Actions

### **Phase 1: Remove Large Files (Week 1)**
```bash
# Remove large backup directory
rm -rf ../news-system-backup-20250826_090951/

# Remove export zip
rm -f ../news-system-export.zip

# Remove virtual environment (we'll recreate it properly)
rm -rf ../venv/
```

### **Phase 2: Clean Git History (Week 1)**
```bash
# Check if large files were ever committed
git log --oneline --name-only | grep -E "(backup|export|venv)"

# If found, remove from git history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch ../news-system-backup-*/ ../news-system-export* ../venv/' \
  --prune-empty --tag-name-filter cat -- --all
```

### **Phase 3: Reorganize Project Structure (Week 1)**
```
/home/petes/
├── news-system/                    # Git repository (lean)
│   ├── api/                       # Application code
│   ├── docker/                    # Docker configs
│   ├── docs/                      # Documentation
│   └── .gitignore                 # Proper ignore rules
├── news-data/                     # NAS mount point
│   ├── backups/                   # Automated backups
│   ├── exports/                   # Data exports
│   ├── models/                    # ML models
│   └── datasets/                  # Large datasets
└── news-env/                      # Virtual environment
    └── venv/                      # Python virtual env
```

## 🗄️ NAS Mount Strategy

### **NAS Mount Point: `/home/petes/news-data`**
```bash
# Create mount point
sudo mkdir -p /home/petes/news-data

# Set ownership
sudo chown petes:petes /home/petes/news-data

# Set permissions
sudo chmod 755 /home/petes/news-data
```

### **NAS Mount Configuration**
```bash
# Add to /etc/fstab
# NAS_IP:/share/news-data /home/petes/news-data nfs defaults,user,noatime 0 0

# Manual mount for testing
sudo mount -t nfs NAS_IP:/share/news-data /home/petes/news-data
```

### **Directory Structure on NAS**
```
/news-data/
├── backups/                       # Automated system backups
│   ├── daily/                     # Daily backups
│   ├── weekly/                    # Weekly backups
│   └── monthly/                   # Monthly backups
├── exports/                       # Data exports
│   ├── articles/                  # Article exports
│   ├── reports/                   # Generated reports
│   └── analytics/                 # Analytics data
├── models/                        # ML models and weights
│   ├── trained/                   # Trained models
│   ├── checkpoints/               # Model checkpoints
│   └── embeddings/                # Vector embeddings
├── datasets/                      # Large datasets
│   ├── raw/                       # Raw data
│   ├── processed/                 # Processed data
│   └── training/                  # Training datasets
└── logs/                          # System logs
    ├── application/                # App logs
    ├── database/                   # DB logs
    └── monitoring/                 # Monitoring logs
```

## 🔧 Implementation Steps

### **Step 1: Immediate Cleanup (Today)**
```bash
# Stop any running services
sudo systemctl stop news-system

# Remove large files
rm -rf ../news-system-backup-20250826_090951/
rm -f ../news-system-export.zip
rm -rf ../venv/

# Verify cleanup
du -sh . ../news-system* ../venv* 2>/dev/null
```

### **Step 2: NAS Setup (This Week)**
```bash
# Install NFS client
sudo apt-get update
sudo apt-get install nfs-common

# Create mount point
sudo mkdir -p /home/petes/news-data
sudo chown petes:petes /home/petes/news-data

# Test mount
sudo mount -t nfs NAS_IP:/share/news-data /home/petes/news-data

# Add to fstab for persistence
echo "NAS_IP:/share/news-data /home/petes/news-data nfs defaults,user,noatime 0 0" | sudo tee -a /etc/fstab
```

### **Step 3: Reorganize Project (This Week)**
```bash
# Create new directory structure
mkdir -p /home/petes/news-data/{backups,exports,models,datasets,logs}
mkdir -p /home/petes/news-env

# Move existing large files to NAS
# (if any remain after cleanup)

# Create new virtual environment
cd /home/petes/news-env
python3 -m venv venv
source venv/bin/activate
pip install -r /home/petes/news-system/api/requirements.txt
```

### **Step 4: Update Configuration (This Week)**
```bash
# Update docker-compose.yml to use NAS mount
# Update backup scripts to use NAS
# Update export scripts to use NAS
# Update logging configuration
```

## 📊 Expected Results

### **Space Savings**
- **Before cleanup**: ~24.4GB wasted space
- **After cleanup**: ~964KB project size
- **Space saved**: 99.99% reduction

### **Performance Improvements**
- **Git operations**: 10-100x faster
- **System startup**: 2-3x faster
- **Backup operations**: Centralized and efficient
- **Data management**: Organized and scalable

### **Maintenance Benefits**
- **Automated backups** to NAS
- **Centralized data** management
- **Easy scaling** for future growth
- **Professional** system organization

## 🚀 Future-Proofing

### **Automated Backup Strategy**
```bash
# Daily backup script
#!/bin/bash
DATE=$(date +%Y%m%d)
tar -czf /home/petes/news-data/backups/daily/news-system-$DATE.tar.gz \
  --exclude=venv --exclude=__pycache__ --exclude=*.log \
  /home/petes/news-system/

# Clean old backups (keep 7 daily, 4 weekly, 12 monthly)
find /home/petes/news-data/backups/daily/ -mtime +7 -delete
find /home/petes/news-data/backups/weekly/ -mtime +28 -delete
find /home/petes/news-data/backups/monthly/ -mtime +365 -delete
```

### **Data Export Strategy**
```bash
# Export script with NAS integration
#!/bin/bash
EXPORT_DIR="/home/petes/news-data/exports/articles"
DATE=$(date +%Y%m%d_%H%M%S)

# Export articles to NAS
psql -h localhost -U newsapp -d news_db -c "
  COPY (SELECT * FROM articles WHERE created_at >= NOW() - INTERVAL '7 days')
  TO '$EXPORT_DIR/weekly_export_$DATE.csv' CSV HEADER;
"
```

### **Monitoring and Alerts**
```bash
# Disk space monitoring
#!/bin/bash
USAGE=$(df /home/petes/news-data | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $USAGE -gt 80 ]; then
  echo "WARNING: NAS usage at ${USAGE}%" | mail -s "NAS Space Alert" admin@example.com
fi
```

## ⚠️ Important Notes

### **Before Cleanup**
1. **Verify NAS is accessible** and working
2. **Test mount point** permissions
3. **Ensure backup strategy** is in place
4. **Stop all services** that might use the files

### **After Cleanup**
1. **Test system functionality** thoroughly
2. **Verify NAS mount** persistence
3. **Update documentation** with new structure
4. **Train team** on new organization

### **Ongoing Maintenance**
1. **Monitor NAS space** usage
2. **Rotate backups** automatically
3. **Clean old exports** regularly
4. **Update .gitignore** as needed

## 🎯 Success Criteria

### **Immediate (This Week)**
- [ ] Large files removed
- [ ] NAS mount working
- [ ] Project structure reorganized
- [ ] Virtual environment recreated

### **Short Term (Next 2 Weeks)**
- [ ] Automated backups working
- [ ] Export scripts updated
- [ ] Monitoring in place
- [ ] Documentation updated

### **Long Term (Next Month)**
- [ ] System fully optimized
- [ ] Team trained on new structure
- [ ] Backup strategy validated
- [ ] Performance metrics improved

This cleanup will transform your system from a cluttered development environment into a professional, scalable, and maintainable production system.
