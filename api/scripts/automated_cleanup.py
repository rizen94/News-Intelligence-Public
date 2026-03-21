#!/usr/bin/env python3
"""
Automated Cleanup System for News Intelligence System v3.0
Prevents data drift and garbage buildup through proactive monitoring and cleanup
Follows architectural standards and naming conventions
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta

import docker

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import centralized path configuration
from config.paths import LOGS_DIR, PROJECT_ROOT, SCRIPTS_DIR

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class CleanupTarget:
    name: str
    path: str
    max_size_gb: float
    current_size_gb: float
    cleanup_priority: int  # 1=high, 2=medium, 3=low
    cleanup_type: str  # 'delete', 'archive', 'compress'
    retention_days: int
    description: str


@dataclass
class CleanupResult:
    target: CleanupTarget
    action_taken: str
    space_freed_gb: float
    success: bool
    error_message: str | None = None
    timestamp: datetime = None


class AutomatedCleanupSystem:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "cleanup_config.json"
        self.docker_client = None
        self.cleanup_history: list[CleanupResult] = []
        self.stats = {
            "total_cleanups": 0,
            "total_space_freed": 0.0,
            "last_cleanup": None,
            "errors": 0,
        }

        # Initialize Docker client
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")

        # Load configuration
        self.config = self._load_config()

        # Setup logging
        self._setup_logging()

    def _load_config(self) -> dict:
        """Load cleanup configuration from file or create default"""
        default_config = {
            "cleanup_schedule": {
                "daily": ["logs", "temp_files", "docker_cache"],
                "weekly": ["backups", "exports", "old_datasets"],
                "monthly": ["archives", "old_models", "system_cleanup"],
            },
            "targets": {
                "logs": {
                    "path": LOGS_DIR,
                    "max_size_gb": 1.0,
                    "cleanup_priority": 1,
                    "cleanup_type": "delete",
                    "retention_days": 7,
                    "description": "Application and system logs",
                },
                "temp_files": {
                    "path": "/tmp",
                    "max_size_gb": 2.0,
                    "cleanup_priority": 1,
                    "cleanup_type": "delete",
                    "retention_days": 1,
                    "description": "Temporary files",
                },
                "docker_cache": {
                    "path": "docker",
                    "max_size_gb": 5.0,
                    "cleanup_priority": 2,
                    "cleanup_type": "docker_cleanup",
                    "retention_days": 7,
                    "description": "Docker build cache and unused resources",
                },
                "postgres_data": {
                    "path": os.path.join(PROJECT_ROOT, "postgres_data"),
                    "max_size_gb": 50.0,
                    "cleanup_priority": 3,
                    "cleanup_type": "archive",
                    "retention_days": 90,
                    "description": "PostgreSQL data directory",
                },
                "redis_data": {
                    "path": os.path.join(PROJECT_ROOT, "redis_data"),
                    "max_size_gb": 5.0,
                    "cleanup_priority": 2,
                    "cleanup_type": "delete",
                    "retention_days": 30,
                    "description": "Redis data directory",
                },
                "api_logs": {
                    "path": os.path.join(PROJECT_ROOT, "api", "logs"),
                    "max_size_gb": 2.0,
                    "cleanup_priority": 1,
                    "cleanup_type": "delete",
                    "retention_days": 14,
                    "description": "API application logs",
                },
                "backups": {
                    "path": os.path.join(PROJECT_ROOT, "backups"),
                    "max_size_gb": 10.0,
                    "cleanup_priority": 2,
                    "cleanup_type": "archive",
                    "retention_days": 30,
                    "description": "System backups",
                },
                "old_datasets": {
                    "path": os.path.join(PROJECT_ROOT, "data", "models"),
                    "max_size_gb": 20.0,
                    "cleanup_priority": 2,
                    "cleanup_type": "archive",
                    "retention_days": 180,
                    "description": "Old ML models and datasets",
                },
                "duplicate_configs": {
                    "path": os.path.join(PROJECT_ROOT, "api", "config"),
                    "max_size_gb": 0.1,
                    "cleanup_priority": 1,
                    "cleanup_type": "delete_duplicates",
                    "retention_days": 0,
                    "description": "Remove duplicate configuration files",
                },
            },
            "thresholds": {
                "disk_usage_warning": 80.0,  # Percentage
                "disk_usage_critical": 90.0,  # Percentage
                "cleanup_trigger_size_gb": 1.0,  # Minimum size to trigger cleanup
                "max_cleanup_time_seconds": 300,  # Maximum time for cleanup operations
            },
            "notifications": {
                "enabled": True,
                "email": None,
                "slack_webhook": None,
                "log_file": os.path.join(LOGS_DIR, "cleanup.log"),
            },
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                    # Merge with defaults
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    return config
            except Exception as e:
                logger.error(f"Error loading config: {e}, using defaults")
                return default_config
        else:
            # Create default config file
            self._save_config(default_config)
            return default_config

    def _save_config(self, config: dict):
        """Save configuration to file"""
        try:
            with open(self.config_path, "w") as f:
                json.dump(config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _setup_logging(self):
        """Setup logging to file"""
        log_dir = os.path.dirname(self.config["notifications"]["log_file"])
        os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.FileHandler(self.config["notifications"]["log_file"])
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    def get_disk_usage(self, path: str = "/") -> tuple[float, float, float]:
        """Get disk usage statistics for a path"""
        try:
            stat = shutil.disk_usage(path)
            total_gb = stat.total / (1024**3)
            used_gb = (stat.total - stat.free) / (1024**3)
            free_gb = stat.free / (1024**3)
            usage_percent = (used_gb / total_gb) * 100
            return total_gb, used_gb, free_gb, usage_percent
        except Exception as e:
            logger.error(f"Error getting disk usage for {path}: {e}")
            return 0, 0, 0, 0

    def get_directory_size(self, path: str) -> float:
        """Get directory size in GB"""
        try:
            if not os.path.exists(path):
                return 0.0

            total_size = 0
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    if os.path.exists(filepath):
                        total_size += os.path.getsize(filepath)

            return total_size / (1024**3)  # Convert to GB
        except Exception as e:
            logger.error(f"Error calculating directory size for {path}: {e}")
            return 0.0

    def cleanup_docker(self) -> CleanupResult:
        """Clean up Docker resources"""
        if not self.docker_client:
            return CleanupResult(
                target=CleanupTarget(
                    "docker", "docker", 0, 0, 1, "docker_cleanup", 7, "Docker cleanup"
                ),
                action_taken="skipped",
                space_freed_gb=0.0,
                success=False,
                error_message="Docker client not available",
            )

        try:
            # Get current Docker usage
            docker_df = self.docker_client.containers.prune()
            containers_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.images.prune()
            images_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.networks.prune()
            networks_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            docker_df = self.docker_client.volumes.prune()
            volumes_freed = docker_df.get("SpaceReclaimed", 0) / (1024**3)

            # Clean build cache
            try:
                result = subprocess.run(
                    ["docker", "builder", "prune", "-f"], capture_output=True, text=True, timeout=60
                )
                if result.returncode == 0:
                    logger.info("Docker build cache cleaned")
            except Exception as e:
                logger.warning(f"Docker build cache cleanup failed: {e}")

            total_freed = containers_freed + images_freed + networks_freed + volumes_freed

            return CleanupResult(
                target=CleanupTarget(
                    "docker", "docker", 0, 0, 1, "docker_cleanup", 7, "Docker cleanup"
                ),
                action_taken="docker_cleanup",
                space_freed_gb=total_freed,
                success=True,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Docker cleanup failed: {e}")
            return CleanupResult(
                target=CleanupTarget(
                    "docker", "docker", 0, 0, 1, "docker_cleanup", 7, "Docker cleanup"
                ),
                action_taken="failed",
                space_freed_gb=0.0,
                success=False,
                error_message=str(e),
                timestamp=datetime.now(),
            )

    def cleanup_directory(self, target: CleanupTarget) -> CleanupResult:
        """Clean up a specific directory based on cleanup type"""
        try:
            if not os.path.exists(target.path):
                return CleanupResult(
                    target=target,
                    action_taken="skipped",
                    space_freed_gb=0.0,
                    success=True,
                    error_message="Path does not exist",
                )

            current_size = self.get_directory_size(target.path)
            target.current_size_gb = current_size

            if current_size <= target.max_size_gb:
                return CleanupResult(
                    target=target, action_taken="no_action_needed", space_freed_gb=0.0, success=True
                )

            space_to_free = current_size - target.max_size_gb

            if target.cleanup_type == "delete":
                freed_space = self._cleanup_delete(target, space_to_free)
            elif target.cleanup_type == "archive":
                freed_space = self._cleanup_archive(target, space_to_free)
            elif target.cleanup_type == "compress":
                freed_space = self._cleanup_compress(target, space_to_free)
            elif target.cleanup_type == "delete_duplicates":
                freed_space = self._cleanup_delete_duplicates(target, space_to_free)
            else:
                freed_space = 0.0

            return CleanupResult(
                target=target,
                action_taken=target.cleanup_type,
                space_freed_gb=freed_space,
                success=True,
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Directory cleanup failed for {target.path}: {e}")
            return CleanupResult(
                target=target,
                action_taken="failed",
                space_freed_gb=0.0,
                success=False,
                error_message=str(e),
                timestamp=datetime.now(),
            )

    def _cleanup_delete(self, target: CleanupTarget, space_to_free: float) -> float:
        """Delete old files to free space"""
        freed_space = 0.0
        cutoff_time = datetime.now() - timedelta(days=target.retention_days)

        try:
            for root, dirs, files in os.walk(target.path, topdown=False):
                for file in files:
                    if freed_space >= space_to_free:
                        break

                    filepath = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(filepath) / (1024**3)  # GB
                            os.remove(filepath)
                            freed_space += file_size
                            logger.debug(f"Deleted old file: {filepath}")
                    except Exception as e:
                        logger.debug(f"Could not delete {filepath}: {e}")

                # Remove empty directories
                for dir in dirs:
                    dirpath = os.path.join(root, dir)
                    try:
                        if not os.listdir(dirpath):
                            os.rmdir(dirpath)
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Error during delete cleanup: {e}")

        return freed_space

    def _cleanup_archive(self, target: CleanupTarget, space_to_free: float) -> float:
        """Archive old files to free space"""
        freed_space = 0.0
        cutoff_time = datetime.now() - timedelta(days=target.retention_days)
        archive_dir = os.path.join(target.path, "archived")
        os.makedirs(archive_dir, exist_ok=True)

        try:
            for root, dirs, files in os.walk(target.path):
                if "archived" in root:
                    continue

                for file in files:
                    if freed_space >= space_to_free:
                        break

                    filepath = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(filepath) / (1024**3)  # GB

                            # Create archive filename
                            rel_path = os.path.relpath(filepath, target.path)
                            archive_path = os.path.join(archive_dir, rel_path.replace("/", "_"))

                            # Move to archive
                            shutil.move(filepath, archive_path)
                            freed_space += file_size
                            logger.debug(f"Archived: {filepath} -> {archive_path}")
                    except Exception as e:
                        logger.debug(f"Could not archive {filepath}: {e}")

        except Exception as e:
            logger.error(f"Error during archive cleanup: {e}")

        return freed_space

    def _cleanup_compress(self, target: CleanupTarget, space_to_free: float) -> float:
        """Compress old files to free space"""
        freed_space = 0.0
        cutoff_time = datetime.now() - timedelta(days=target.retention_days)

        try:
            for root, dirs, files in os.walk(target.path):
                for file in files:
                    if freed_space >= space_to_free:
                        break

                    if file.endswith((".gz", ".zip", ".tar", ".7z")):
                        continue  # Already compressed

                    filepath = os.path.join(root, file)
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                        if file_time < cutoff_time:
                            file_size = os.path.getsize(filepath) / (1024**3)  # GB

                            # Compress file
                            compressed_path = filepath + ".gz"
                            with open(filepath, "rb") as f_in:
                                with open(compressed_path, "wb") as f_out:
                                    import gzip

                                    with gzip.open(f_out, "wb") as gz:
                                        shutil.copyfileobj(f_in, gz)

                            # Remove original
                            os.remove(filepath)
                            freed_space += file_size * 0.7  # Assume 30% compression
                            logger.debug(f"Compressed: {filepath} -> {compressed_path}")
                    except Exception as e:
                        logger.debug(f"Could not compress {filepath}: {e}")

        except Exception as e:
            logger.error(f"Error during compress cleanup: {e}")

        return freed_space

    def _cleanup_delete_duplicates(self, target: CleanupTarget, space_to_free: float) -> float:
        """Remove duplicate configuration files based on architectural standards"""
        freed_space = 0.0

        try:
            # Define duplicate patterns based on architectural standards
            duplicate_patterns = ["robust_database.py", "unified_database.py", "connection.py"]

            # Keep only the main database.py file
            main_file = os.path.join(target.path, "database.py")

            for pattern in duplicate_patterns:
                file_path = os.path.join(target.path, pattern)
                if os.path.exists(file_path) and file_path != main_file:
                    try:
                        file_size = os.path.getsize(file_path) / (1024**3)  # GB
                        os.remove(file_path)
                        freed_space += file_size
                        logger.info(f"Removed duplicate config file: {file_path}")
                    except Exception as e:
                        logger.debug(f"Could not remove {file_path}: {e}")

            # Check for duplicate docker-compose files
            compose_files = [
                "docker-compose.dev.yml",
                "docker-compose.prod.yml",
                "configs/docker-compose.backend.yml",
                "configs/docker-compose.frontend.yml",
                "configs/docker-compose.monitoring.yml",
            ]

            for compose_file in compose_files:
                file_path = os.path.join(PROJECT_ROOT, compose_file)
                if os.path.exists(file_path):
                    try:
                        file_size = os.path.getsize(file_path) / (1024**3)  # GB
                        os.remove(file_path)
                        freed_space += file_size
                        logger.info(f"Removed duplicate compose file: {file_path}")
                    except Exception as e:
                        logger.debug(f"Could not remove {file_path}: {e}")

        except Exception as e:
            logger.error(f"Error during duplicate cleanup: {e}")

        return freed_space

    def run_cleanup(self, cleanup_type: str = "auto") -> dict:
        """Run cleanup based on type or automatically"""
        start_time = time.time()
        results = []
        total_freed = 0.0

        logger.info(f"Starting {cleanup_type} cleanup")

        # Check disk usage first
        total_gb, used_gb, free_gb, usage_percent = self.get_disk_usage()
        logger.info(f"Disk usage: {usage_percent:.1f}% ({used_gb:.1f}GB / {total_gb:.1f}GB)")

        # Determine what to clean
        if cleanup_type == "auto":
            if usage_percent > self.config["thresholds"]["disk_usage_critical"]:
                cleanup_targets = ["logs", "temp_files", "docker_cache", "backups", "exports"]
            elif usage_percent > self.config["thresholds"]["disk_usage_warning"]:
                cleanup_targets = ["logs", "temp_files", "docker_cache"]
            else:
                cleanup_targets = ["logs", "temp_files"]
        elif cleanup_type == "daily":
            cleanup_targets = self.config["cleanup_schedule"]["daily"]
        elif cleanup_type == "weekly":
            cleanup_targets = self.config["cleanup_schedule"]["weekly"]
        elif cleanup_type == "monthly":
            cleanup_targets = self.config["cleanup_schedule"]["monthly"]
        else:
            cleanup_targets = [cleanup_type]

        # Run cleanup for each target
        for target_name in cleanup_targets:
            if target_name in self.config["targets"]:
                target_config = self.config["targets"][target_name]
                target = CleanupTarget(
                    name=target_name,
                    path=target_config["path"],
                    max_size_gb=target_config["max_size_gb"],
                    current_size_gb=0,
                    cleanup_priority=target_config["cleanup_priority"],
                    cleanup_type=target_config["cleanup_type"],
                    retention_days=target_config["retention_days"],
                    description=target_config["description"],
                )

                if target.cleanup_type == "docker_cleanup":
                    result = self.cleanup_docker()
                else:
                    result = self.cleanup_directory(target)

                results.append(result)
                if result.success:
                    total_freed += result.space_freed_gb

                # Check timeout
                if time.time() - start_time > self.config["thresholds"]["max_cleanup_time_seconds"]:
                    logger.warning("Cleanup timeout reached, stopping")
                    break

        # Update statistics
        self.stats["total_cleanups"] += 1
        self.stats["total_space_freed"] += total_freed
        self.stats["last_cleanup"] = datetime.now()

        # Log results
        cleanup_time = time.time() - start_time
        logger.info(f"Cleanup completed in {cleanup_time:.1f}s, freed {total_freed:.2f}GB")

        # Save cleanup history
        self.cleanup_history.extend(results)
        if len(self.cleanup_history) > 1000:  # Keep last 1000 results
            self.cleanup_history = self.cleanup_history[-1000:]

        return {
            "cleanup_type": cleanup_type,
            "total_space_freed_gb": total_freed,
            "cleanup_time_seconds": cleanup_time,
            "results": [vars(r) for r in results],
            "disk_usage_percent": usage_percent,
            "timestamp": datetime.now().isoformat(),
        }

    def get_cleanup_stats(self) -> dict:
        """Get cleanup statistics"""
        return {
            "stats": self.stats,
            "recent_results": [vars(r) for r in self.cleanup_history[-10:]],
            "config": self.config,
        }

    def create_cleanup_script(self, script_path: str = None) -> str:
        """Create a shell script for automated cleanup"""
        if not script_path:
            script_path = os.path.join(SCRIPTS_DIR, "run_cleanup.sh")

        script_content = f"""#!/bin/bash
# Automated Cleanup Script for News Intelligence System
# Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

cd {PROJECT_ROOT}

# Run cleanup based on day of week
DAY_OF_WEEK=$(date +%u)

case $DAY_OF_WEEK in
    1) # Monday - Weekly cleanup
        python3 api/scripts/automated_cleanup.py weekly
        ;;
    2|3|4|5|6) # Tuesday-Friday - Daily cleanup
        python3 api/scripts/automated_cleanup.py daily
        ;;
    7) # Sunday - Light cleanup
        python3 api/scripts/automated_cleanup.py auto
        ;;
esac

# Log completion
echo "$(date): Cleanup completed" >> /var/log/news-system-cleanup.log
"""

        try:
            os.makedirs(os.path.dirname(script_path), exist_ok=True)
            with open(script_path, "w") as f:
                f.write(script_content)

            # Make executable
            os.chmod(script_path, 0o755)
            logger.info(f"Cleanup script created: {script_path}")
            return script_path
        except Exception as e:
            logger.error(f"Error creating cleanup script: {e}")
            return ""


def main():
    """Main function for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(description="Automated Cleanup System")
    parser.add_argument(
        "cleanup_type",
        nargs="?",
        default="auto",
        choices=["auto", "daily", "weekly", "monthly", "logs", "temp_files", "docker_cache"],
        help="Type of cleanup to run",
    )
    parser.add_argument("--config", help="Path to configuration file")
    parser.add_argument("--create-script", action="store_true", help="Create cleanup script")
    parser.add_argument("--stats", action="store_true", help="Show cleanup statistics")

    args = parser.parse_args()

    # Initialize cleanup system
    cleanup_system = AutomatedCleanupSystem(args.config)

    if args.create_script:
        script_path = cleanup_system.create_cleanup_script()
        if script_path:
            print(f"Cleanup script created: {script_path}")
            print("Add to crontab with: 0 2 * * * /path/to/script")
        return

    if args.stats:
        stats = cleanup_system.get_cleanup_stats()
        print(json.dumps(stats, indent=2, default=str))
        return

    # Run cleanup
    try:
        result = cleanup_system.run_cleanup(args.cleanup_type)
        print(json.dumps(result, indent=2, default=str))
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
