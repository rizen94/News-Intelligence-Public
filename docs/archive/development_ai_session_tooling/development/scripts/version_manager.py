#!/usr/bin/env python3
"""
Version Manager for News Intelligence System v3.0
Handles versioning, build tracking, and deployment management
"""

import os
import json
import time
from datetime import datetime
from pathlib import Path

class VersionManager:
    def __init__(self, project_root="."):
        self.project_root = Path(project_root)
        self.version_file = self.project_root / ".version"
        self.build_info_file = self.project_root / "logs" / "build_info.json"
        self.deployment_file = self.project_root / "logs" / "deployments.json"
        
        # Ensure logs directory exists
        (self.project_root / "logs").mkdir(exist_ok=True)
        
        # Initialize files if they don't exist
        self._init_files()
    
    def _init_files(self):
        """Initialize version and build tracking files"""
        if not self.version_file.exists():
            self.version_file.write_text("1.0.0")
        
        if not self.build_info_file.exists():
            self.build_info_file.write_text(json.dumps({
                "builds": [],
                "last_build": None,
                "total_builds": 0
            }, indent=2))
        
        if not self.deployment_file.exists():
            self.deployment_file.write_text(json.dumps({
                "deployments": [],
                "last_deployment": None,
                "total_deployments": 0
            }, indent=2))
    
    def get_current_version(self):
        """Get current version"""
        return self.version_file.read_text().strip()
    
    def increment_version(self, increment_type="patch"):
        """Increment version number"""
        current_version = self.get_current_version()
        major, minor, patch = map(int, current_version.split('.'))
        
        if increment_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif increment_type == "minor":
            minor += 1
            patch = 0
        else:  # patch
            patch += 1
        
        new_version = f"{major}.{minor}.{patch}"
        self.version_file.write_text(new_version)
        return new_version
    
    def record_build(self, build_type="development", success=True, duration=None):
        """Record a build event"""
        build_info = json.loads(self.build_info_file.read_text())
        
        build_record = {
            "timestamp": datetime.now().isoformat(),
            "version": self.get_current_version(),
            "type": build_type,
            "success": success,
            "duration": duration,
            "build_id": f"build_{int(time.time())}"
        }
        
        build_info["builds"].append(build_record)
        build_info["last_build"] = build_record
        build_info["total_builds"] += 1
        
        # Keep only last 50 builds
        if len(build_info["builds"]) > 50:
            build_info["builds"] = build_info["builds"][-50:]
        
        self.build_info_file.write_text(json.dumps(build_info, indent=2))
        return build_record
    
    def record_deployment(self, environment="production", success=True, version=None):
        """Record a deployment event"""
        deployment_info = json.loads(self.deployment_file.read_text())
        
        deployment_record = {
            "timestamp": datetime.now().isoformat(),
            "version": version or self.get_current_version(),
            "environment": environment,
            "success": success,
            "deployment_id": f"deploy_{int(time.time())}"
        }
        
        deployment_info["deployments"].append(deployment_record)
        deployment_info["last_deployment"] = deployment_record
        deployment_info["total_deployments"] += 1
        
        # Keep only last 50 deployments
        if len(deployment_info["deployments"]) > 50:
            deployment_info["deployments"] = deployment_info["deployments"][-50:]
        
        self.deployment_file.write_text(json.dumps(deployment_info, indent=2))
        return deployment_record
    
    def get_build_stats(self):
        """Get build statistics"""
        build_info = json.loads(self.build_info_file.read_text())
        
        total_builds = build_info["total_builds"]
        successful_builds = sum(1 for build in build_info["builds"] if build["success"])
        failed_builds = total_builds - successful_builds
        
        return {
            "total_builds": total_builds,
            "successful_builds": successful_builds,
            "failed_builds": failed_builds,
            "success_rate": (successful_builds / total_builds * 100) if total_builds > 0 else 0,
            "last_build": build_info["last_build"]
        }
    
    def get_deployment_stats(self):
        """Get deployment statistics"""
        deployment_info = json.loads(self.deployment_file.read_text())
        
        total_deployments = deployment_info["total_deployments"]
        successful_deployments = sum(1 for deploy in deployment_info["deployments"] if deploy["success"])
        failed_deployments = total_deployments - successful_deployments
        
        return {
            "total_deployments": total_deployments,
            "successful_deployments": successful_deployments,
            "failed_deployments": failed_deployments,
            "success_rate": (successful_deployments / total_deployments * 100) if total_deployments > 0 else 0,
            "last_deployment": deployment_info["last_deployment"]
        }
    
    def get_system_status(self):
        """Get overall system status"""
        build_stats = self.get_build_stats()
        deployment_stats = self.get_deployment_stats()
        
        return {
            "current_version": self.get_current_version(),
            "build_stats": build_stats,
            "deployment_stats": deployment_stats,
            "status": "healthy" if build_stats["success_rate"] > 80 and deployment_stats["success_rate"] > 80 else "degraded"
        }
    
    def print_status(self):
        """Print formatted system status"""
        status = self.get_system_status()
        
        print("News Intelligence System v3.0 - Version Management Status")
        print("=" * 60)
        print(f"Current Version: {status['current_version']}")
        print(f"System Status: {status['status'].upper()}")
        print()
        
        print("Build Statistics:")
        build_stats = status['build_stats']
        print(f"  Total Builds: {build_stats['total_builds']}")
        print(f"  Successful: {build_stats['successful_builds']}")
        print(f"  Failed: {build_stats['failed_builds']}")
        print(f"  Success Rate: {build_stats['success_rate']:.1f}%")
        
        if build_stats['last_build']:
            last_build = build_stats['last_build']
            print(f"  Last Build: {last_build['timestamp']} ({last_build['type']})")
        
        print()
        print("Deployment Statistics:")
        deploy_stats = status['deployment_stats']
        print(f"  Total Deployments: {deploy_stats['total_deployments']}")
        print(f"  Successful: {deploy_stats['successful_deployments']}")
        print(f"  Failed: {deploy_stats['failed_deployments']}")
        print(f"  Success Rate: {deploy_stats['success_rate']:.1f}%")
        
        if deploy_stats['last_deployment']:
            last_deploy = deploy_stats['last_deployment']
            print(f"  Last Deployment: {last_deploy['timestamp']} ({last_deploy['environment']})")

def main():
    """Main function for command line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Version Manager for News Intelligence System')
    parser.add_argument('--increment', choices=['major', 'minor', 'patch'], 
                       help='Increment version number')
    parser.add_argument('--build', action='store_true', 
                       help='Record a build event')
    parser.add_argument('--deploy', action='store_true', 
                       help='Record a deployment event')
    parser.add_argument('--status', action='store_true', 
                       help='Show system status')
    parser.add_argument('--version', action='store_true', 
                       help='Show current version')
    
    args = parser.parse_args()
    
    vm = VersionManager()
    
    if args.increment:
        new_version = vm.increment_version(args.increment)
        print(f"Version incremented to: {new_version}")
    
    if args.build:
        vm.record_build("manual", True)
        print("Build event recorded")
    
    if args.deploy:
        vm.record_deployment("manual", True)
        print("Deployment event recorded")
    
    if args.status:
        vm.print_status()
    
    if args.version:
        print(vm.get_current_version())
    
    if not any([args.increment, args.build, args.deploy, args.status, args.version]):
        vm.print_status()

if __name__ == "__main__":
    main()
