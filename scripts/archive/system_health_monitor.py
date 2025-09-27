#!/usr/bin/env python3
"""
System Health Monitor for News Intelligence System
Comprehensive monitoring of all components and their integration
"""

import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import subprocess
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SystemHealthMonitor:
    """Comprehensive system health monitoring"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.services = {
            "api": "http://localhost:8000/api/health/",
            "frontend": "http://localhost:3000",
            "postgres": "localhost:5432",
            "redis": "localhost:6379",
            "ollama": "http://localhost:11434/api/tags",
            "nginx": "http://localhost:80"
        }
        self.health_status = {}
        self.integration_tests = []
        
    def check_service_health(self, service_name: str, endpoint: str) -> Dict[str, Any]:
        """Check individual service health"""
        try:
            if service_name == "postgres":
                return self._check_postgres()
            elif service_name == "redis":
                return self._check_redis()
            elif service_name == "ollama":
                return self._check_ollama()
            else:
                response = requests.get(endpoint, timeout=5)
                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "response_time": response.elapsed.total_seconds(),
                    "status_code": response.status_code,
                    "error": None
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "response_time": None,
                "status_code": None,
                "error": str(e)
            }
    
    def _check_postgres(self) -> Dict[str, Any]:
        """Check PostgreSQL health"""
        try:
            result = subprocess.run([
                "docker", "exec", "news-intelligence-postgres", 
                "pg_isready", "-U", "newsapp", "-d", "news_intelligence"
            ], capture_output=True, text=True, timeout=5)
            
            return {
                "status": "healthy" if result.returncode == 0 else "unhealthy",
                "response_time": None,
                "status_code": result.returncode,
                "error": result.stderr if result.returncode != 0 else None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "response_time": None,
                "status_code": None,
                "error": str(e)
            }
    
    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis health"""
        try:
            result = subprocess.run([
                "docker", "exec", "news-intelligence-redis", 
                "redis-cli", "ping"
            ], capture_output=True, text=True, timeout=5)
            
            return {
                "status": "healthy" if "PONG" in result.stdout else "unhealthy",
                "response_time": None,
                "status_code": 0 if "PONG" in result.stdout else 1,
                "error": result.stderr if "PONG" not in result.stdout else None
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "response_time": None,
                "status_code": None,
                "error": str(e)
            }
    
    def _check_ollama(self) -> Dict[str, Any]:
        """Check Ollama health"""
        try:
            response = requests.get(self.services["ollama"], timeout=10)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model['name'] for model in models]
                return {
                    "status": "healthy",
                    "response_time": response.elapsed.total_seconds(),
                    "status_code": response.status_code,
                    "error": None,
                    "available_models": model_names,
                    "target_model_available": "llama3.1:70b-instruct-q4_K_M" in model_names
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time": response.elapsed.total_seconds(),
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}"
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "response_time": None,
                "status_code": None,
                "error": str(e)
            }
    
    def run_integration_tests(self) -> List[Dict[str, Any]]:
        """Run integration tests to verify components work together"""
        tests = []
        
        # Test 1: API -> Database
        try:
            response = requests.get(f"{self.api_base}/api/articles/?limit=1", timeout=5)
            tests.append({
                "test": "API -> Database",
                "status": "pass" if response.status_code == 200 else "fail",
                "details": f"Status: {response.status_code}",
                "error": None
            })
        except Exception as e:
            tests.append({
                "test": "API -> Database",
                "status": "fail",
                "details": "Connection failed",
                "error": str(e)
            })
        
        # Test 2: API -> RSS Feeds
        try:
            response = requests.get(f"{self.api_base}/api/rss/feeds/", timeout=5)
            tests.append({
                "test": "API -> RSS Feeds",
                "status": "pass" if response.status_code == 200 else "fail",
                "details": f"Status: {response.status_code}",
                "error": None
            })
        except Exception as e:
            tests.append({
                "test": "API -> RSS Feeds",
                "status": "fail",
                "details": "Connection failed",
                "error": str(e)
            })
        
        # Test 3: API -> Storylines
        try:
            response = requests.get(f"{self.api_base}/api/storylines/", timeout=5)
            tests.append({
                "test": "API -> Storylines",
                "status": "pass" if response.status_code == 200 else "fail",
                "details": f"Status: {response.status_code}",
                "error": None
            })
        except Exception as e:
            tests.append({
                "test": "API -> Storylines",
                "status": "fail",
                "details": "Connection failed",
                "error": str(e)
            })
        
        # Test 4: Frontend -> API
        try:
            response = requests.get("http://localhost:3000", timeout=5)
            tests.append({
                "test": "Frontend -> API",
                "status": "pass" if response.status_code == 200 else "fail",
                "details": f"Status: {response.status_code}",
                "error": None
            })
        except Exception as e:
            tests.append({
                "test": "Frontend -> API",
                "status": "fail",
                "details": "Connection failed",
                "error": str(e)
            })
        
        # Test 5: ML Service Integration
        try:
            response = requests.post(f"{self.api_base}/api/storylines/1/process-ml", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    tests.append({
                        "test": "ML Service Integration",
                        "status": "pass",
                        "details": "ML processing successful",
                        "error": None
                    })
                else:
                    tests.append({
                        "test": "ML Service Integration",
                        "status": "fail",
                        "details": f"ML processing failed: {data.get('error')}",
                        "error": data.get('error')
                    })
            else:
                tests.append({
                    "test": "ML Service Integration",
                    "status": "fail",
                    "details": f"HTTP {response.status_code}",
                    "error": None
                })
        except Exception as e:
            tests.append({
                "test": "ML Service Integration",
                "status": "fail",
                "details": "Connection failed",
                "error": str(e)
            })
        
        return tests
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Generate comprehensive health report"""
        logger.info("🔍 Starting comprehensive system health check...")
        
        # Check all services
        service_health = {}
        for service_name, endpoint in self.services.items():
            logger.info(f"Checking {service_name}...")
            service_health[service_name] = self.check_service_health(service_name, endpoint)
        
        # Run integration tests
        logger.info("Running integration tests...")
        integration_tests = self.run_integration_tests()
        
        # Calculate overall health
        healthy_services = sum(1 for health in service_health.values() if health["status"] == "healthy")
        total_services = len(service_health)
        passed_tests = sum(1 for test in integration_tests if test["status"] == "pass")
        total_tests = len(integration_tests)
        
        overall_health = "healthy" if healthy_services == total_services and passed_tests == total_tests else "degraded"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_health": overall_health,
            "service_health": service_health,
            "integration_tests": integration_tests,
            "summary": {
                "healthy_services": f"{healthy_services}/{total_services}",
                "passed_tests": f"{passed_tests}/{total_tests}",
                "critical_issues": self._identify_critical_issues(service_health, integration_tests)
            }
        }
        
        return report
    
    def _identify_critical_issues(self, service_health: Dict, integration_tests: List) -> List[str]:
        """Identify critical issues that need immediate attention"""
        issues = []
        
        # Check for unhealthy services
        for service_name, health in service_health.items():
            if health["status"] != "healthy":
                issues.append(f"Service {service_name} is unhealthy: {health.get('error', 'Unknown error')}")
        
        # Check for failed integration tests
        for test in integration_tests:
            if test["status"] != "pass":
                issues.append(f"Integration test failed: {test['test']} - {test.get('error', test['details'])}")
        
        return issues
    
    def display_health_report(self, report: Dict[str, Any]):
        """Display formatted health report"""
        print("\n" + "="*80)
        print(f"NEWS INTELLIGENCE SYSTEM HEALTH REPORT - {report['timestamp']}")
        print("="*80)
        
        # Overall health
        health_emoji = "✅" if report["overall_health"] == "healthy" else "⚠️"
        print(f"\n{health_emoji} OVERALL HEALTH: {report['overall_health'].upper()}")
        
        # Service health
        print(f"\n📊 SERVICE HEALTH ({report['summary']['healthy_services']}):")
        for service_name, health in report["service_health"].items():
            status_emoji = "✅" if health["status"] == "healthy" else "❌"
            print(f"  {status_emoji} {service_name.upper()}: {health['status']}")
            if health.get("error"):
                print(f"    Error: {health['error']}")
            if health.get("available_models"):
                print(f"    Models: {', '.join(health['available_models'])}")
        
        # Integration tests
        print(f"\n🔗 INTEGRATION TESTS ({report['summary']['passed_tests']}):")
        for test in report["integration_tests"]:
            status_emoji = "✅" if test["status"] == "pass" else "❌"
            print(f"  {status_emoji} {test['test']}: {test['status']}")
            if test.get("error"):
                print(f"    Error: {test['error']}")
        
        # Critical issues
        if report["summary"]["critical_issues"]:
            print(f"\n🚨 CRITICAL ISSUES:")
            for issue in report["summary"]["critical_issues"]:
                print(f"  ❌ {issue}")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    monitor = SystemHealthMonitor()
    
    print("🔍 News Intelligence System Health Monitor")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\nOptions:\n1. Run health check\n2. Continuous monitoring (5s intervals)\n3. Exit\n\nChoice: ").strip()
            
            if user_input == "1":
                report = monitor.generate_health_report()
                monitor.display_health_report(report)
                
            elif user_input == "2":
                print("Starting continuous monitoring. Press Ctrl+C to stop.")
                try:
                    while True:
                        report = monitor.generate_health_report()
                        monitor.display_health_report(report)
                        time.sleep(5)
                except KeyboardInterrupt:
                    print("\nMonitoring stopped.")
                    
            elif user_input == "3":
                print("Exiting health monitor.")
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nExiting health monitor.")
            break
        except Exception as e:
            logger.error(f"Error in health monitor: {e}")

if __name__ == "__main__":
    main()
