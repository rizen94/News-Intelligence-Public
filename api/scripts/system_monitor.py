#!/usr/bin/env python3
"""
System Monitor for News Intelligence System v2.1.3
Monitors system health and triggers cleanup when needed
"""
import os
import sys
import json
import logging
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import psutil
import docker

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemMonitor:
    def __init__(self):
        self.thresholds = {
            'disk_usage_warning': 80.0,      # Percentage
            'disk_usage_critical': 90.0,     # Percentage
            'memory_usage_warning': 85.0,    # Percentage
            'memory_usage_critical': 95.0,   # Percentage
            'docker_usage_warning': 10.0,    # GB
            'docker_usage_critical': 20.0,   # GB
            'cleanup_trigger_size': 5.0      # GB
        }
        
        self.monitoring_history = []
        self.alerts = []
        
        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")
            self.docker_client = None
    
    def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        try:
            # Disk usage
            disk_usage = psutil.disk_usage('/')
            disk_total_gb = disk_usage.total / (1024**3)
            disk_used_gb = (disk_usage.total - disk_usage.free) / (1024**3)
            disk_free_gb = disk_usage.free / (1024**3)
            disk_usage_percent = (disk_used_gb / disk_total_gb) * 100
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            memory_free_gb = memory.available / (1024**3)
            memory_usage_percent = (memory.used / memory.total) * 100
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Docker usage
            docker_usage = self.get_docker_usage()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Load average (Linux only)
            try:
                load_avg = os.getloadavg()
            except AttributeError:
                load_avg = (0, 0, 0)
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'disk': {
                    'total_gb': round(disk_total_gb, 2),
                    'used_gb': round(disk_used_gb, 2),
                    'free_gb': round(disk_free_gb, 2),
                    'usage_percent': round(disk_usage_percent, 2)
                },
                'memory': {
                    'total_gb': round(memory_total_gb, 2),
                    'used_gb': round(memory_used_gb, 2),
                    'free_gb': round(memory_free_gb, 2),
                    'usage_percent': round(memory_usage_percent, 2)
                },
                'cpu': {
                    'usage_percent': round(cpu_percent, 2),
                    'count': cpu_count,
                    'load_average': load_avg
                },
                'docker': docker_usage,
                'processes': process_count,
                'system': {
                    'uptime': self.get_system_uptime(),
                    'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system stats: {e}")
            return {}
    
    def get_docker_usage(self) -> Dict:
        """Get Docker resource usage"""
        if not self.docker_client:
            return {'error': 'Docker client not available'}
        
        try:
            # Get Docker system info
            docker_df = self.docker_client.containers.prune()
            containers_freed = docker_df.get('SpaceReclaimed', 0) / (1024**3)
            
            docker_df = self.docker_client.images.prune()
            images_freed = docker_df.get('SpaceReclaimed', 0) / (1024**3)
            
            docker_df = self.docker_client.networks.prune()
            networks_freed = docker_df.get('SpaceReclaimed', 0) / (1024**3)
            
            docker_df = self.docker_client.volumes.prune()
            volumes_freed = docker_df.get('SpaceReclaimed', 0) / (1024**3)
            
            # Get Docker system df
            try:
                result = subprocess.run(
                    ['docker', 'system', 'df', '--format', 'json'],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    docker_info = json.loads(result.stdout)
                else:
                    docker_info = {}
            except Exception:
                docker_info = {}
            
            return {
                'containers_freed_gb': round(containers_freed, 2),
                'images_freed_gb': round(images_freed, 2),
                'networks_freed_gb': round(networks_freed, 2),
                'volumes_freed_gb': round(volumes_freed, 2),
                'system_info': docker_info
            }
            
        except Exception as e:
            logger.error(f"Error getting Docker usage: {e}")
            return {'error': str(e)}
    
    def get_system_uptime(self) -> str:
        """Get system uptime in human readable format"""
        try:
            uptime_seconds = time.time() - psutil.boot_time()
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except Exception:
            return "Unknown"
    
    def check_thresholds(self, stats: Dict) -> List[Dict]:
        """Check if any thresholds are exceeded"""
        alerts = []
        
        # Disk usage alerts
        disk_usage = stats.get('disk', {}).get('usage_percent', 0)
        if disk_usage >= self.thresholds['disk_usage_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'component': 'disk',
                'message': f"Disk usage critical: {disk_usage:.1f}%",
                'value': disk_usage,
                'threshold': self.thresholds['disk_usage_critical']
            })
        elif disk_usage >= self.thresholds['disk_usage_warning']:
            alerts.append({
                'level': 'WARNING',
                'component': 'disk',
                'message': f"Disk usage warning: {disk_usage:.1f}%",
                'value': disk_usage,
                'threshold': self.thresholds['disk_usage_warning']
            })
        
        # Memory usage alerts
        memory_usage = stats.get('memory', {}).get('usage_percent', 0)
        if memory_usage >= self.thresholds['memory_usage_critical']:
            alerts.append({
                'level': 'CRITICAL',
                'component': 'memory',
                'message': f"Memory usage critical: {memory_usage:.1f}%",
                'value': memory_usage,
                'threshold': self.thresholds['memory_usage_critical']
            })
        elif memory_usage >= self.thresholds['memory_usage_warning']:
            alerts.append({
                'level': 'WARNING',
                'component': 'memory',
                'message': f"Memory usage warning: {memory_usage:.1f}%",
                'value': memory_usage,
                'threshold': self.thresholds['memory_usage_warning']
            })
        
        # Docker usage alerts
        docker_info = stats.get('docker', {})
        if 'error' not in docker_info:
            total_docker_gb = sum([
                docker_info.get('containers_freed_gb', 0),
                docker_info.get('images_freed_gb', 0),
                docker_info.get('networks_freed_gb', 0),
                docker_info.get('volumes_freed_gb', 0)
            ])
            
            if total_docker_gb >= self.thresholds['docker_usage_critical']:
                alerts.append({
                    'level': 'CRITICAL',
                    'component': 'docker',
                    'message': f"Docker usage critical: {total_docker_gb:.1f}GB",
                    'value': total_docker_gb,
                    'threshold': self.thresholds['docker_usage_critical']
                })
            elif total_docker_gb >= self.thresholds['docker_usage_warning']:
                alerts.append({
                    'level': 'WARNING',
                    'component': 'docker',
                    'message': f"Docker usage warning: {total_docker_gb:.1f}GB",
                    'value': total_docker_gb,
                    'threshold': self.thresholds['docker_usage_warning']
                })
        
        return alerts
    
    def should_trigger_cleanup(self, stats: Dict) -> bool:
        """Determine if cleanup should be triggered"""
        # Check if disk usage is critical
        disk_usage = stats.get('disk', {}).get('usage_percent', 0)
        if disk_usage >= self.thresholds['disk_usage_critical']:
            return True
        
        # Check if Docker usage is high
        docker_info = stats.get('docker', {})
        if 'error' not in docker_info:
            total_docker_gb = sum([
                docker_info.get('containers_freed_gb', 0),
                docker_info.get('images_freed_gb', 0),
                docker_info.get('networks_freed_gb', 0),
                docker_info.get('volumes_freed_gb', 0)
            ])
            
            if total_docker_gb >= self.thresholds['cleanup_trigger_size']:
                return True
        
        return False
    
    def trigger_cleanup(self) -> bool:
        """Trigger the cleanup system"""
        try:
            logger.info("Triggering automated cleanup due to threshold exceeded")
            
            # Run cleanup script
            result = subprocess.run([
                '/usr/bin/python3',
                '/home/petes/news-system/api/scripts/automated_cleanup.py',
                'auto'
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("Cleanup triggered successfully")
                return True
            else:
                logger.error(f"Cleanup failed: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error triggering cleanup: {e}")
            return False
    
    def run_monitoring_cycle(self) -> Dict:
        """Run one monitoring cycle"""
        # Get system stats
        stats = self.get_system_stats()
        
        # Check thresholds
        alerts = self.check_thresholds(stats)
        
        # Add alerts to stats
        stats['alerts'] = alerts
        stats['alert_count'] = len(alerts)
        
        # Store in history
        self.monitoring_history.append(stats)
        if len(self.monitoring_history) > 1000:  # Keep last 1000 entries
            self.monitoring_history = self.monitoring_history[-1000:]
        
        # Check if cleanup should be triggered
        if self.should_trigger_cleanup(stats):
            cleanup_triggered = self.trigger_cleanup()
            stats['cleanup_triggered'] = cleanup_triggered
        
        # Log alerts
        for alert in alerts:
            if alert['level'] == 'CRITICAL':
                logger.critical(alert['message'])
            elif alert['level'] == 'WARNING':
                logger.warning(alert['message'])
        
        return stats
    
    def get_monitoring_summary(self) -> Dict:
        """Get monitoring summary and trends"""
        if not self.monitoring_history:
            return {'error': 'No monitoring data available'}
        
        recent_stats = self.monitoring_history[-24:]  # Last 24 entries
        
        # Calculate trends
        disk_trend = []
        memory_trend = []
        cpu_trend = []
        
        for stat in recent_stats:
            if 'disk' in stat and 'usage_percent' in stat['disk']:
                disk_trend.append(stat['disk']['usage_percent'])
            if 'memory' in stat and 'usage_percent' in stat['memory']:
                memory_trend.append(stat['memory']['usage_percent'])
            if 'cpu' in stat and 'usage_percent' in stat['cpu']:
                cpu_trend.append(stat['cpu']['usage_percent'])
        
        # Calculate averages
        avg_disk = sum(disk_trend) / len(disk_trend) if disk_trend else 0
        avg_memory = sum(memory_trend) / len(memory_trend) if memory_trend else 0
        avg_cpu = sum(cpu_trend) / len(cpu_trend) if cpu_trend else 0
        
        # Count alerts by level
        alert_counts = {'CRITICAL': 0, 'WARNING': 0}
        for stat in recent_stats:
            for alert in stat.get('alerts', []):
                level = alert.get('level', 'UNKNOWN')
                if level in alert_counts:
                    alert_counts[level] += 1
        
        return {
            'monitoring_period': f"Last {len(recent_stats)} cycles",
            'averages': {
                'disk_usage_percent': round(avg_disk, 2),
                'memory_usage_percent': round(avg_memory, 2),
                'cpu_usage_percent': round(avg_cpu, 2)
            },
            'alert_summary': alert_counts,
            'total_cycles': len(self.monitoring_history),
            'last_update': datetime.now().isoformat()
        }
    
    def save_monitoring_data(self, filepath: str = None):
        """Save monitoring data to file"""
        if not filepath:
            filepath = "/home/petes/news-system/logs/monitoring_data.json"
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            data = {
                'summary': self.get_monitoring_summary(),
                'recent_history': self.monitoring_history[-100:],  # Last 100 entries
                'thresholds': self.thresholds,
                'exported_at': datetime.now().isoformat()
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            
            logger.info(f"Monitoring data saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving monitoring data: {e}")

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='System Monitor')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    parser.add_argument('--interval', type=int, default=300, help='Monitoring interval in seconds')
    parser.add_argument('--summary', action='store_true', help='Show monitoring summary')
    parser.add_argument('--save', action='store_true', help='Save monitoring data to file')
    
    args = parser.parse_args()
    
    monitor = SystemMonitor()
    
    if args.summary:
        summary = monitor.get_monitoring_summary()
        print(json.dumps(summary, indent=2, default=str))
        return
    
    if args.save:
        monitor.save_monitoring_data()
        return
    
    if args.daemon:
        logger.info(f"Starting system monitor daemon (interval: {args.interval}s)")
        
        while True:
            try:
                monitor.run_monitoring_cycle()
                time.sleep(args.interval)
            except KeyboardInterrupt:
                logger.info("System monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in monitoring cycle: {e}")
                time.sleep(60)  # Wait before retrying
    else:
        # Run single cycle
        result = monitor.run_monitoring_cycle()
        print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()
