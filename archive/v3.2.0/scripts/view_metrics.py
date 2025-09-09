#!/usr/bin/env python3
"""
News Intelligence System - Metrics Viewer
Command-line tool to view and analyze logged resource metrics
"""

import sqlite3
import argparse
import json
from datetime import datetime, timedelta
import sys
import os

def connect_db(db_path="logs/resource_metrics.db"):
    """Connect to the metrics database"""
    if not os.path.exists(db_path):
        print(f"❌ Metrics database not found at: {db_path}")
        print("   Make sure the resource logger has been running")
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None

def get_metrics_summary(conn, hours=24):
    """Get metrics summary for the last N hours"""
    try:
        cursor = conn.cursor()
        
        # System metrics summary
        cursor.execute("""
            SELECT 
                AVG(cpu_percent) as avg_cpu,
                MAX(cpu_percent) as max_cpu,
                AVG(memory_percent) as avg_memory,
                MAX(memory_percent) as max_memory,
                AVG(gpu_utilization_percent) as avg_gpu_util,
                MAX(gpu_utilization_percent) as max_gpu_util,
                AVG(gpu_memory_used_mb) as avg_gpu_memory,
                MAX(gpu_memory_used_mb) as max_gpu_memory,
                COUNT(*) as data_points
            FROM system_metrics 
            WHERE timestamp >= datetime('now', '-{} hours')
        """.format(hours))
        
        system_summary = cursor.fetchone()
        
        # Application metrics summary
        cursor.execute("""
            SELECT 
                SUM(requests_total) as total_requests,
                SUM(articles_processed) as total_articles,
                SUM(ml_inferences) as total_ml_inferences,
                SUM(database_queries) as total_db_queries,
                SUM(errors_total) as total_errors,
                COUNT(*) as data_points
            FROM application_metrics 
            WHERE timestamp >= datetime('now', '-{} hours')
        """.format(hours))
        
        app_summary = cursor.fetchone()
        
        return {
            'system': system_summary,
            'application': app_summary
        }
        
    except Exception as e:
        print(f"❌ Error getting metrics summary: {e}")
        return None

def get_recent_metrics(conn, limit=20):
    """Get recent metrics data points"""
    try:
        cursor = conn.cursor()
        
        # Recent system metrics
        cursor.execute("""
            SELECT timestamp, cpu_percent, memory_percent, gpu_utilization_percent, gpu_memory_used_mb
            FROM system_metrics 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        system_metrics = cursor.fetchall()
        
        # Recent application metrics
        cursor.execute("""
            SELECT timestamp, requests_total, articles_processed, ml_inferences, database_queries, errors_total
            FROM application_metrics 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (limit,))
        
        app_metrics = cursor.fetchall()
        
        return {
            'system': system_metrics,
            'application': app_metrics
        }
        
    except Exception as e:
        print(f"❌ Error getting recent metrics: {e}")
        return None

def get_performance_events(conn, hours=24):
    """Get performance events for the last N hours"""
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, event_type, event_description, severity, metadata
            FROM performance_events 
            WHERE timestamp >= datetime('now', '-{} hours')
            ORDER BY timestamp DESC
        """.format(hours))
        
        return cursor.fetchall()
        
    except Exception as e:
        print(f"❌ Error getting performance events: {e}")
        return None

def display_summary(summary, hours):
    """Display metrics summary"""
    if not summary:
        return
    
    print(f"\n📊 METRICS SUMMARY (Last {hours} hours)")
    print("=" * 60)
    
    # System metrics
    sys_data = summary['system']
    if sys_data and sys_data[0] is not None:
        print(f"\n🖥️  SYSTEM PERFORMANCE:")
        print(f"   CPU:     Avg: {sys_data[0]:5.1f}% | Max: {sys_data[1]:5.1f}%")
        print(f"   Memory:  Avg: {sys_data[2]:5.1f}% | Max: {sys_data[3]:5.1f}%")
        print(f"   GPU:     Avg: {sys_data[4]:5.1f}% | Max: {sys_data[5]:5.1f}%")
        print(f"   GPU Mem: Avg: {sys_data[6]:5.1f}MB | Max: {sys_data[7]:5.1f}MB")
        print(f"   Data Points: {sys_data[8]}")
    
    # Application metrics
    app_data = summary['application']
    if app_data and app_data[0] is not None:
        print(f"\n📱 APPLICATION ACTIVITY:")
        print(f"   Requests:        {app_data[0]:,}")
        print(f"   Articles:        {app_data[1]:,}")
        print(f"   ML Inferences:   {app_data[2]:,}")
        print(f"   DB Queries:      {app_data[3]:,}")
        print(f"   Errors:          {app_data[4]:,}")
        print(f"   Data Points:     {app_data[5]}")

def display_recent_metrics(metrics, limit):
    """Display recent metrics data"""
    if not metrics:
        return
    
    print(f"\n📈 RECENT METRICS (Last {limit} data points)")
    print("=" * 80)
    
    # System metrics
    print(f"\n🖥️  SYSTEM METRICS:")
    print(f"{'Timestamp':<20} {'CPU%':<6} {'Mem%':<6} {'GPU%':<6} {'GPU Mem(MB)':<12}")
    print("-" * 60)
    
    for row in metrics['system']:
        timestamp, cpu, mem, gpu_util, gpu_mem = row
        print(f"{timestamp:<20} {cpu:<6.1f} {mem:<6.1f} {gpu_util:<6.1f} {gpu_mem:<12}")
    
    # Application metrics
    print(f"\n📱 APPLICATION METRICS:")
    print(f"{'Timestamp':<20} {'Reqs':<6} {'Arts':<6} {'ML':<6} {'DB':<6} {'Errors':<6}")
    print("-" * 60)
    
    for row in metrics['application']:
        timestamp, reqs, arts, ml, db, errors = row
        print(f"{timestamp:<20} {reqs:<6} {arts:<6} {ml:<6} {db:<6} {errors:<6}")

def display_performance_events(events):
    """Display performance events"""
    if not events:
        print("\n✅ No performance events in the specified time period")
        return
    
    print(f"\n🚨 PERFORMANCE EVENTS")
    print("=" * 80)
    
    for event in events:
        timestamp, event_type, description, severity, metadata = event
        
        # Color coding for severity
        severity_icon = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }.get(severity, 'ℹ️')
        
        print(f"\n{severity_icon} {event_type.upper()} - {timestamp}")
        print(f"   {description}")
        if metadata:
            try:
                meta = json.loads(metadata)
                for key, value in meta.items():
                    print(f"   {key}: {value}")
            except:
                print(f"   Metadata: {metadata}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='View News Intelligence System metrics')
    parser.add_argument('--hours', type=int, default=24, help='Hours to look back (default: 24)')
    parser.add_argument('--recent', type=int, default=20, help='Number of recent data points to show (default: 20)')
    parser.add_argument('--events', action='store_true', help='Show performance events')
    parser.add_argument('--db-path', default='logs/resource_metrics.db', help='Path to metrics database')
    
    args = parser.parse_args()
    
    # Connect to database
    conn = connect_db(args.db_path)
    if not conn:
        sys.exit(1)
    
    try:
        print("🔍 NEWS INTELLIGENCE SYSTEM - METRICS VIEWER")
        print("=" * 60)
        
        # Get and display summary
        summary = get_metrics_summary(conn, args.hours)
        display_summary(summary, args.hours)
        
        # Get and display recent metrics
        recent_metrics = get_recent_metrics(conn, args.recent)
        display_recent_metrics(recent_metrics, args.recent)
        
        # Get and display performance events if requested
        if args.events:
            events = get_performance_events(conn, args.hours)
            display_performance_events(events)
        
        print(f"\n✅ Metrics analysis complete for the last {args.hours} hours")
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
