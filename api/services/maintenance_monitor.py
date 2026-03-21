#!/usr/bin/env python3
"""
Maintenance Monitor for News Intelligence System v3.0
Proactive monitoring and alerting for resource management
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import docker
import psutil

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.config.paths import ARCHIVE_DIR, BACKUPS_DIR, LOGS_DIR, PROJECT_ROOT, WEB_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MaintenanceMonitor:
    """Proactive monitoring system for maintenance and resource management"""

    def __init__(self):
        self.thresholds = {
            "disk_usage_warning": 75.0,  # 75% disk usage
            "disk_usage_critical": 85.0,  # 85% disk usage
            "file_count_warning": 10000,  # 10k files in any directory
            "file_count_critical": 20000,  # 20k files in any directory
            "log_size_warning": 100,  # 100MB log files
            "log_size_critical": 500,  # 500MB log files
            "node_modules_warning": 1000,  # 1GB node_modules
            "node_modules_critical": 2000,  # 2GB node_modules
            "archive_size_warning": 3000,  # 3GB archive
            "archive_size_critical": 5000,  # 5GB archive
        }

        self.alerts = []
        self.monitoring_data = {}

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")
            self.docker_client = None

    def check_disk_usage(self) -> dict:
        """Check disk usage and return status"""
        try:
            disk_usage = psutil.disk_usage("/")
            total_gb = disk_usage.total / (1024**3)
            used_gb = (disk_usage.total - disk_usage.free) / (1024**3)
            free_gb = disk_usage.free / (1024**3)
            usage_percent = (used_gb / total_gb) * 100

            status = {
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "usage_percent": round(usage_percent, 2),
                "status": "OK",
            }

            if usage_percent >= self.thresholds["disk_usage_critical"]:
                status["status"] = "CRITICAL"
                self.alerts.append(
                    {
                        "level": "CRITICAL",
                        "component": "disk",
                        "message": f"Disk usage critical: {usage_percent:.1f}%",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            elif usage_percent >= self.thresholds["disk_usage_warning"]:
                status["status"] = "WARNING"
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "disk",
                        "message": f"Disk usage warning: {usage_percent:.1f}%",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return status

        except Exception as e:
            logger.error(f"Error checking disk usage: {e}")
            return {"error": str(e), "status": "ERROR"}

    def check_file_counts(self) -> dict:
        """Check file counts in key directories"""
        directories = {
            "project_root": PROJECT_ROOT,
            "logs": LOGS_DIR,
            "web": WEB_DIR,
            "archive": ARCHIVE_DIR,
            "backups": BACKUPS_DIR,
        }

        file_counts = {}

        for name, path in directories.items():
            try:
                if os.path.exists(path):
                    count = sum(1 for _ in Path(path).rglob("*") if _.is_file())
                    file_counts[name] = {"count": count, "path": path, "status": "OK"}

                    if count >= self.thresholds["file_count_critical"]:
                        file_counts[name]["status"] = "CRITICAL"
                        self.alerts.append(
                            {
                                "level": "CRITICAL",
                                "component": "file_count",
                                "message": f"File count critical in {name}: {count} files",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    elif count >= self.thresholds["file_count_warning"]:
                        file_counts[name]["status"] = "WARNING"
                        self.alerts.append(
                            {
                                "level": "WARNING",
                                "component": "file_count",
                                "message": f"File count warning in {name}: {count} files",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                else:
                    file_counts[name] = {"error": "Directory not found", "status": "ERROR"}

            except Exception as e:
                file_counts[name] = {"error": str(e), "status": "ERROR"}
                logger.error(f"Error checking file count for {name}: {e}")

        return file_counts

    def check_log_sizes(self) -> dict:
        """Check log file sizes"""
        log_sizes = {}

        try:
            if os.path.exists(LOGS_DIR):
                for log_file in Path(LOGS_DIR).glob("*.log"):
                    size_mb = log_file.stat().st_size / (1024**2)
                    log_sizes[log_file.name] = {
                        "size_mb": round(size_mb, 2),
                        "path": str(log_file),
                        "status": "OK",
                    }

                    if size_mb >= self.thresholds["log_size_critical"]:
                        log_sizes[log_file.name]["status"] = "CRITICAL"
                        self.alerts.append(
                            {
                                "level": "CRITICAL",
                                "component": "log_size",
                                "message": f"Log file critical: {log_file.name} ({size_mb:.1f}MB)",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    elif size_mb >= self.thresholds["log_size_warning"]:
                        log_sizes[log_file.name]["status"] = "WARNING"
                        self.alerts.append(
                            {
                                "level": "WARNING",
                                "component": "log_size",
                                "message": f"Log file warning: {log_file.name} ({size_mb:.1f}MB)",
                                "timestamp": datetime.now().isoformat(),
                            }
                        )

            return log_sizes

        except Exception as e:
            logger.error(f"Error checking log sizes: {e}")
            return {"error": str(e)}

    def check_node_modules_size(self) -> dict:
        """Check node_modules directory size"""
        node_modules_path = os.path.join(WEB_DIR, "node_modules")

        try:
            if os.path.exists(node_modules_path):
                total_size = sum(
                    f.stat().st_size for f in Path(node_modules_path).rglob("*") if f.is_file()
                )
                size_gb = total_size / (1024**3)

                status = {"size_gb": round(size_gb, 2), "path": node_modules_path, "status": "OK"}

                if size_gb >= self.thresholds["node_modules_critical"]:
                    status["status"] = "CRITICAL"
                    self.alerts.append(
                        {
                            "level": "CRITICAL",
                            "component": "node_modules",
                            "message": f"Node modules critical: {size_gb:.1f}GB",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                elif size_gb >= self.thresholds["node_modules_warning"]:
                    status["status"] = "WARNING"
                    self.alerts.append(
                        {
                            "level": "WARNING",
                            "component": "node_modules",
                            "message": f"Node modules warning: {size_gb:.1f}GB",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

                return status
            else:
                return {"error": "node_modules not found", "status": "OK"}

        except Exception as e:
            logger.error(f"Error checking node_modules size: {e}")
            return {"error": str(e), "status": "ERROR"}

    def check_docker_resources(self) -> dict:
        """Check Docker resource usage"""
        if not self.docker_client:
            return {"error": "Docker client not available", "status": "ERROR"}

        try:
            # Get Docker system info
            docker_df = self.docker_client.containers.prune()
            containers_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.images.prune()
            images_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.networks.prune()
            networks_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.volumes.prune()
            volumes_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            total_freed = containers_freed + images_freed + networks_freed + volumes_freed

            return {
                "containers_freed_gb": round(containers_freed, 2),
                "images_freed_gb": round(images_freed, 2),
                "networks_freed_gb": round(networks_freed, 2),
                "volumes_freed_gb": round(volumes_freed, 2),
                "total_freed_gb": round(total_freed, 2),
                "status": "OK",
            }

        except Exception as e:
            logger.error(f"Error checking Docker resources: {e}")
            return {"error": str(e), "status": "ERROR"}

    def run_full_monitoring(self) -> dict:
        """Run complete monitoring check"""
        logger.info("Starting full maintenance monitoring...")

        self.alerts = []  # Reset alerts

        monitoring_data = {
            "timestamp": datetime.now().isoformat(),
            "disk_usage": self.check_disk_usage(),
            "file_counts": self.check_file_counts(),
            "log_sizes": self.check_log_sizes(),
            "node_modules_size": self.check_node_modules_size(),
            "docker_resources": self.check_docker_resources(),
            "alerts": self.alerts,
            "alert_count": len(self.alerts),
        }

        self.monitoring_data = monitoring_data

        # Log alerts
        for alert in self.alerts:
            if alert["level"] == "CRITICAL":
                logger.critical(alert["message"])
            elif alert["level"] == "WARNING":
                logger.warning(alert["message"])

        logger.info(f"Monitoring complete. {len(self.alerts)} alerts generated.")
        return monitoring_data

    def save_monitoring_report(self, filepath: str = None) -> str:
        """Save monitoring report to file"""
        if not filepath:
            filepath = os.path.join(
                LOGS_DIR, f"maintenance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w") as f:
                json.dump(self.monitoring_data, f, indent=2, default=str)

            logger.info(f"Monitoring report saved to: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Error saving monitoring report: {e}")
            return None


def main():
    """Main function for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Maintenance Monitor")
    parser.add_argument("--check", action="store_true", help="Run monitoring check")
    parser.add_argument("--save", action="store_true", help="Save report to file")
    parser.add_argument("--alerts-only", action="store_true", help="Show only alerts")

    args = parser.parse_args()

    monitor = MaintenanceMonitor()

    if args.check or not any([args.save, args.alerts_only]):
        result = monitor.run_full_monitoring()

        if args.alerts_only:
            alerts = result.get("alerts", [])
            if alerts:
                print(f"Found {len(alerts)} alerts:")
                for alert in alerts:
                    print(f"  {alert['level']}: {alert['message']}")
            else:
                print("No alerts found.")
        else:
            print(json.dumps(result, indent=2, default=str))

    if args.save:
        report_path = monitor.save_monitoring_report()
        if report_path:
            print(f"Report saved to: {report_path}")


if __name__ == "__main__":
    main()
