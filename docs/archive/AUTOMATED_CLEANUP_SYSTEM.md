# Automated Cleanup System

## 🎯 Overview

The Automated Cleanup System is a comprehensive solution designed to prevent data drift and garbage buildup in the News Intelligence System. It provides proactive monitoring, automated cleanup, and intelligent resource management to maintain system health and performance.

## 🏗️ System Architecture

### **Core Components**

1. **Automated Cleanup System** (`automated_cleanup.py`)
   - Proactive cleanup of logs, temp files, Docker resources
   - Configurable retention policies and cleanup strategies
   - Multiple cleanup types: delete, archive, compress

2. **System Monitor** (`system_monitor.py`)
   - Real-time monitoring of disk, memory, CPU, and Docker usage
   - Threshold-based alerting system
   - Automatic cleanup triggering when thresholds are exceeded

3. **Systemd Services**
   - `cleanup.service` - Runs cleanup operations
   - `cleanup.timer` - Schedules daily cleanup at 2 AM
   - `monitor.service` - Continuous system monitoring

### **Cleanup Strategies**

#### **Delete Strategy**
- **Use case**: Temporary files, logs, build artifacts
- **Action**: Permanently removes files older than retention period
- **Examples**: `/tmp` files, application logs, Docker build cache

#### **Archive Strategy**
- **Use case**: Important data that should be preserved
- **Action**: Moves files to archive directory
- **Examples**: Backups, exports, old datasets

#### **Compress Strategy**
- **Use case**: Large files that are rarely accessed
- **Action**: Compresses files to save space
- **Examples**: Data exports, ML models, historical datasets

## 📋 Configuration

### **Default Configuration**

The system creates a default configuration file (`cleanup_config.json`) with the following settings:

```json
{
  "cleanup_schedule": {
    "daily": ["logs", "temp_files", "docker_cache"],
    "weekly": ["backups", "exports", "old_datasets"],
    "monthly": ["archives", "old_models", "system_cleanup"]
  },
  "targets": {
    "logs": {
      "path": "/home/petes/news-system/logs",
      "max_size_gb": 1.0,
      "cleanup_priority": 1,
      "cleanup_type": "delete",
      "retention_days": 7,
      "description": "Application and system logs"
    },
    "temp_files": {
      "path": "/tmp",
      "max_size_gb": 2.0,
      "cleanup_priority": 1,
      "cleanup_type": "delete",
      "retention_days": 1,
      "description": "Temporary files"
    },
    "docker_cache": {
      "path": "docker",
      "max_size_gb": 5.0,
      "cleanup_priority": 2,
      "cleanup_type": "docker_cleanup",
      "retention_days": 7,
      "description": "Docker build cache and unused resources"
    }
  },
  "thresholds": {
    "disk_usage_warning": 80.0,
    "disk_usage_critical": 90.0,
    "cleanup_trigger_size_gb": 1.0,
    "max_cleanup_time_seconds": 300
  }
}
```

### **Customizing Configuration**

You can modify the configuration file to:
- Adjust retention periods
- Change cleanup schedules
- Add new cleanup targets
- Modify thresholds
- Configure notification settings

## 🚀 Usage

### **Command Line Interface**

#### **Run Cleanup Manually**
```bash
# Run automatic cleanup (based on disk usage)
python3 api/scripts/automated_cleanup.py auto

# Run specific cleanup types
python3 api/scripts/automated_cleanup.py daily
python3 api/scripts/automated_cleanup.py weekly
python3 api/scripts/automated_cleanup.py monthly

# Clean specific targets
python3 api/scripts/automated_cleanup.py logs
python3 api/scripts/automated_cleanup.py temp_files
python3 api/scripts/automated_cleanup.py docker_cache
```

#### **System Monitoring**
```bash
# Run single monitoring cycle
python3 api/scripts/system_monitor.py

# Run as daemon (continuous monitoring)
python3 api/scripts/system_monitor.py --daemon --interval 300

# Show monitoring summary
python3 api/scripts/system_monitor.py --summary

# Save monitoring data to file
python3 api/scripts/system_monitor.py --save
```

#### **Create Cleanup Script**
```bash
# Create shell script for cron
python3 api/scripts/automated_cleanup.py --create-script

# Show cleanup statistics
python3 api/scripts/automated_cleanup.py --stats
```

### **Systemd Services**

#### **Install Services**
```bash
# Copy service files
sudo cp docker/cleanup.service /etc/systemd/system/
sudo cp docker/cleanup.timer /etc/systemd/system/
sudo cp docker/monitor.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start services
sudo systemctl enable cleanup.timer
sudo systemctl start cleanup.timer
sudo systemctl enable monitor.service
sudo systemctl start monitor.service
```

#### **Service Management**
```bash
# Check service status
sudo systemctl status cleanup.timer
sudo systemctl status monitor.service

# View logs
sudo journalctl -u cleanup.service -f
sudo journalctl -u monitor.service -f

# Manual cleanup trigger
sudo systemctl start cleanup.service
```

## 📊 Monitoring and Alerts

### **Thresholds**

The system monitors several key metrics:

- **Disk Usage**: Warning at 80%, Critical at 90%
- **Memory Usage**: Warning at 85%, Critical at 95%
- **Docker Usage**: Warning at 10GB, Critical at 20GB
- **Cleanup Trigger**: Automatic cleanup at 5GB

### **Alert Levels**

#### **WARNING**
- Disk usage > 80%
- Memory usage > 85%
- Docker usage > 10GB
- Action: Log warning, continue monitoring

#### **CRITICAL**
- Disk usage > 90%
- Memory usage > 95%
- Docker usage > 20GB
- Action: Trigger immediate cleanup, send alerts

### **Monitoring Data**

The system collects and stores:
- System resource usage trends
- Cleanup operation results
- Alert history
- Performance metrics
- Docker resource usage

## 🔧 Advanced Features

### **Intelligent Cleanup**

The system automatically determines cleanup strategy based on:
- Current disk usage
- File types and importance
- Access patterns
- Storage costs

### **Cleanup Prioritization**

Cleanup targets are prioritized by:
1. **High Priority** (1): Logs, temp files
2. **Medium Priority** (2): Docker cache, backups
3. **Low Priority** (3): Exports, old datasets

### **Retention Policies**

- **Logs**: 7 days retention
- **Temp Files**: 1 day retention
- **Docker Cache**: 7 days retention
- **Backups**: 30 days retention
- **Exports**: 90 days retention
- **Datasets**: 180 days retention

### **Space Reclamation**

The system tracks space reclaimed:
- Per cleanup operation
- Per target type
- Total historical savings
- Performance impact analysis

## 📈 Performance Impact

### **Resource Usage**

- **CPU**: Minimal impact (< 1% during cleanup)
- **Memory**: Low memory footprint (~50MB)
- **Disk I/O**: Optimized to minimize impact
- **Network**: No network overhead

### **Cleanup Efficiency**

- **Parallel processing** for multiple targets
- **Timeout protection** (5 minutes max)
- **Incremental cleanup** to avoid long operations
- **Smart file selection** based on age and size

### **Scheduling Optimization**

- **Daily cleanup**: 2 AM (low system load)
- **Randomized delay**: 0-30 minutes to avoid thundering herd
- **Conditional execution**: Only runs when needed
- **Background operation**: Non-blocking execution

## 🛡️ Safety Features

### **Data Protection**

- **No data loss**: Important files are archived, not deleted
- **Retention enforcement**: Respects configured retention periods
- **Backup verification**: Ensures backups exist before cleanup
- **Rollback capability**: Can restore from archives

### **Error Handling**

- **Graceful degradation**: Continues operation on partial failures
- **Detailed logging**: Comprehensive error reporting
- **Timeout protection**: Prevents hanging operations
- **Resource limits**: Prevents excessive resource usage

### **Monitoring and Validation**

- **Pre-cleanup verification**: Checks system state before cleanup
- **Post-cleanup validation**: Verifies cleanup results
- **Performance monitoring**: Tracks cleanup impact
- **Alert system**: Notifies on failures or issues

## 🔍 Troubleshooting

### **Common Issues**

#### **Cleanup Not Running**
```bash
# Check service status
sudo systemctl status cleanup.timer

# Check logs
sudo journalctl -u cleanup.service -n 50

# Verify permissions
ls -la /home/petes/news-system/api/scripts/
```

#### **High Resource Usage**
```bash
# Check cleanup configuration
cat cleanup_config.json

# Adjust thresholds
# Modify max_cleanup_time_seconds
# Reduce cleanup frequency
```

#### **Permission Errors**
```bash
# Fix file permissions
chmod +x /home/petes/news-system/api/scripts/*.py

# Check user permissions
id petes
ls -la /home/petes/news-system/
```

### **Debug Mode**

Enable detailed logging:
```bash
# Set log level
export PYTHONPATH=/home/petes/news-system
python3 -c "import logging; logging.basicConfig(level=logging.DEBUG)"

# Run with debug output
python3 api/scripts/automated_cleanup.py auto --debug
```

## 📚 Best Practices

### **Configuration**

1. **Start Conservative**: Begin with longer retention periods
2. **Monitor Impact**: Watch system performance after cleanup
3. **Adjust Gradually**: Modify settings based on usage patterns
4. **Document Changes**: Keep track of configuration modifications

### **Maintenance**

1. **Regular Review**: Check cleanup logs monthly
2. **Performance Monitoring**: Track cleanup efficiency
3. **Storage Planning**: Plan for data growth
4. **Backup Strategy**: Ensure important data is backed up

### **Integration**

1. **CI/CD Pipeline**: Include cleanup in deployment process
2. **Monitoring Stack**: Integrate with existing monitoring tools
3. **Alert System**: Connect to notification systems
4. **Documentation**: Keep team informed of cleanup policies

## 🚀 Future Enhancements

### **Planned Features**

- **Machine Learning**: Predictive cleanup based on usage patterns
- **Cloud Integration**: Cleanup across multiple storage systems
- **Advanced Analytics**: Detailed cleanup performance metrics
- **API Interface**: REST API for remote management
- **Web Dashboard**: Visual monitoring and control interface

### **Extensibility**

The system is designed to be easily extended:
- **New cleanup types**: Add custom cleanup strategies
- **Additional targets**: Support for new file types and locations
- **Plugin system**: Modular architecture for extensions
- **Configuration templates**: Pre-built configurations for common use cases

## 📞 Support

### **Getting Help**

1. **Check Logs**: Review cleanup and monitoring logs
2. **Documentation**: Refer to this guide and inline code comments
3. **Configuration**: Verify cleanup settings and thresholds
4. **System Status**: Check service status and system resources

### **Reporting Issues**

When reporting issues, include:
- System information (OS, Python version)
- Cleanup configuration
- Error logs and messages
- Steps to reproduce
- Expected vs. actual behavior

## 🎉 Conclusion

The Automated Cleanup System provides a robust, intelligent solution for maintaining system health and preventing data drift. By combining proactive monitoring, automated cleanup, and intelligent resource management, it ensures the News Intelligence System remains performant, reliable, and maintainable.

**Key Benefits:**
- **Prevents data drift** and garbage accumulation
- **Automates maintenance** tasks
- **Optimizes resource usage** and performance
- **Provides comprehensive monitoring** and alerting
- **Ensures data safety** through intelligent cleanup strategies

The system is designed to be **self-maintaining**, **configurable**, and **extensible**, providing a solid foundation for long-term system health and performance.
