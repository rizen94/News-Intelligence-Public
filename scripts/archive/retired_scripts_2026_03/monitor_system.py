#!/usr/bin/env python3
"""
News Intelligence System - System Monitoring Script
Displays real-time system metrics and resource usage
"""

import psutil
import time
import subprocess
import json
from datetime import datetime

def get_system_metrics():
    """Get comprehensive system metrics"""
    metrics = {}
    
    # CPU metrics
    metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
    metrics['cpu_count'] = psutil.cpu_count()
    metrics['cpu_freq'] = psutil.cpu_freq().current if psutil.cpu_freq() else 0
    
    # Memory metrics
    memory = psutil.virtual_memory()
    metrics['memory_total_gb'] = round(memory.total / (1024**3), 2)
    metrics['memory_used_gb'] = round(memory.used / (1024**3), 2)
    metrics['memory_percent'] = memory.percent
    
    # Disk metrics
    disk = psutil.disk_usage('/')
    metrics['disk_total_gb'] = round(disk.total / (1024**3), 2)
    metrics['disk_used_gb'] = round(disk.used / (1024**3), 2)
    metrics['disk_percent'] = round((disk.used / disk.total) * 100, 2)
    
    # Network metrics
    network = psutil.net_io_counters()
    metrics['network_bytes_sent'] = network.bytes_sent
    metrics['network_bytes_recv'] = network.bytes_recv
    
    # GPU metrics (if available)
    try:
        result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu,temperature.gpu', '--format=csv,noheader,nounits'], 
                             capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            gpu_info = result.stdout.strip().split(',')
            if len(gpu_info) >= 4:
                metrics['gpu_memory_used_mb'] = int(gpu_info[0])
                metrics['gpu_memory_total_mb'] = int(gpu_info[1])
                metrics['gpu_utilization_percent'] = int(gpu_info[2])
                metrics['gpu_temperature_c'] = int(gpu_info[3])
    except:
        metrics['gpu_available'] = False
    
    return metrics

def get_docker_stats():
    """Get Docker container statistics"""
    try:
        result = subprocess.run(['docker', 'stats', '--no-stream', '--format', 'json'], 
                             capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            containers = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    containers.append(json.loads(line))
            return containers
    except:
        pass
    return []

def display_metrics(metrics, containers):
    """Display metrics in a formatted way"""
    print("\n" + "="*80)
    print(f"NEWS INTELLIGENCE SYSTEM - SYSTEM MONITORING")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # System Resources
    print("\n🖥️  SYSTEM RESOURCES:")
    print(f"   CPU: {metrics['cpu_percent']:5.1f}% ({metrics['cpu_count']} cores, {metrics['cpu_freq']:.0f} MHz)")
    print(f"   RAM: {metrics['memory_used_gb']:6.1f}GB / {metrics['memory_total_gb']:6.1f}GB ({metrics['memory_percent']:5.1f}%)")
    print(f"   Disk: {metrics['disk_used_gb']:6.1f}GB / {metrics['disk_total_gb']:6.1f}GB ({metrics['disk_percent']:5.1f}%)")
    
    # GPU Information
    if 'gpu_memory_used_mb' in metrics:
        print(f"\n🎮 GPU PERFORMANCE:")
        print(f"   Memory: {metrics['gpu_memory_used_mb']:6d}MB / {metrics['gpu_memory_total_mb']:6d}MB")
        print(f"   Utilization: {metrics['gpu_utilization_percent']:5.1f}%")
        print(f"   Temperature: {metrics['gpu_temperature_c']:5.1f}°C")
    else:
        print("\n🎮 GPU: Not available or not accessible")
    
    # Network
    print(f"\n🌐 NETWORK:")
    print(f"   Sent: {metrics['network_bytes_sent'] / (1024**3):8.2f} GB")
    print(f"   Received: {metrics['network_bytes_recv'] / (1024**3):8.2f} GB")
    
    # Docker Containers
    if containers:
        print(f"\n🐳 DOCKER CONTAINERS:")
        for container in containers:
            name = container.get('Name', 'Unknown')
            cpu = container.get('CPUPerc', '0%')
            mem = container.get('MemPerc', '0%')
            mem_usage = container.get('MemUsage', '0B')
            print(f"   {name:25s} | CPU: {cpu:>8s} | RAM: {mem:>8s} | {mem_usage:>15s}")
    
    print("\n" + "="*80)

def main():
    """Main monitoring loop"""
    print("Starting News Intelligence System monitoring...")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            metrics = get_system_metrics()
            containers = get_docker_stats()
            display_metrics(metrics, containers)
            time.sleep(30)  # Update every 30 seconds
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped.")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()
