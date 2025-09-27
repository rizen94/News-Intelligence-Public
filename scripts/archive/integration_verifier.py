#!/usr/bin/env python3
"""
Integration Verifier for News Intelligence System
Verifies all components work together as designed
"""

import requests
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IntegrationVerifier:
    """Verifies system integration and workflow consistency"""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        self.frontend_base = "http://localhost:3000"
        self.workflows = {
            "article_collection": self._verify_article_collection_workflow,
            "storyline_creation": self._verify_storyline_creation_workflow,
            "ml_processing": self._verify_ml_processing_workflow,
            "frontend_display": self._verify_frontend_display_workflow,
            "rss_management": self._verify_rss_management_workflow
        }
    
    def _verify_article_collection_workflow(self) -> Dict[str, Any]:
        """Verify article collection workflow"""
        logger.info("🔍 Verifying article collection workflow...")
        
        try:
            # Step 1: Check articles endpoint
            response = requests.get(f"{self.api_base}/api/articles/?limit=5", timeout=5)
            if response.status_code != 200:
                return {"status": "fail", "error": f"Articles endpoint failed: {response.status_code}"}
            
            articles = response.json().get("data", {}).get("articles", [])
            if not articles:
                return {"status": "fail", "error": "No articles found in system"}
            
            # Step 2: Check article structure
            article = articles[0]
            required_fields = ["id", "title", "content", "source", "published_at"]
            missing_fields = [field for field in required_fields if field not in article]
            if missing_fields:
                return {"status": "fail", "error": f"Article missing fields: {missing_fields}"}
            
            # Step 3: Check article stats
            stats_response = requests.get(f"{self.api_base}/api/articles/stats", timeout=5)
            if stats_response.status_code != 200:
                return {"status": "fail", "error": f"Article stats endpoint failed: {stats_response.status_code}"}
            
            return {
                "status": "pass",
                "details": f"Found {len(articles)} articles, all required fields present",
                "article_count": len(articles),
                "sample_article": {
                    "id": article["id"],
                    "title": article["title"][:50] + "...",
                    "source": article["source"]
                }
            }
            
        except Exception as e:
            return {"status": "fail", "error": str(e)}
    
    def _verify_storyline_creation_workflow(self) -> Dict[str, Any]:
        """Verify storyline creation workflow"""
        logger.info("🔍 Verifying storyline creation workflow...")
        
        try:
            # Step 1: Check storylines endpoint
            response = requests.get(f"{self.api_base}/api/storylines/", timeout=5)
            if response.status_code != 200:
                return {"status": "fail", "error": f"Storylines endpoint failed: {response.status_code}"}
            
            storylines = response.json().get("data", {}).get("storylines", [])
            if not storylines:
                return {"status": "fail", "error": "No storylines found in system"}
            
            # Step 2: Check storyline structure
            storyline = storylines[0]
            required_fields = ["id", "title", "description", "status"]
            missing_fields = [field for field in required_fields if field not in storyline]
            if missing_fields:
                return {"status": "fail", "error": f"Storyline missing fields: {missing_fields}"}
            
            # Step 3: Check storyline articles
            storyline_id = storyline["id"]
            articles_response = requests.get(f"{self.api_base}/api/storylines/{storyline_id}/articles", timeout=5)
            if articles_response.status_code != 200:
                return {"status": "fail", "error": f"Storyline articles endpoint failed: {articles_response.status_code}"}
            
            storyline_articles = articles_response.json().get("data", {}).get("articles", [])
            
            return {
                "status": "pass",
                "details": f"Found {len(storylines)} storylines, {len(storyline_articles)} articles in first storyline",
                "storyline_count": len(storylines),
                "sample_storyline": {
                    "id": storyline["id"],
                    "title": storyline["title"],
                    "article_count": len(storyline_articles)
                }
            }
            
        except Exception as e:
            return {"status": "fail", "error": str(e)}
    
    def _verify_ml_processing_workflow(self) -> Dict[str, Any]:
        """Verify ML processing workflow"""
        logger.info("🔍 Verifying ML processing workflow...")
        
        try:
            # Step 1: Check ML service status
            ml_response = requests.post(f"{self.api_base}/api/storylines/1/process-ml", timeout=10)
            if ml_response.status_code != 200:
                return {"status": "fail", "error": f"ML processing endpoint failed: {ml_response.status_code}"}
            
            ml_data = ml_response.json()
            
            # Step 2: Check ML response structure
            if not ml_data.get("success"):
                return {
                    "status": "fail", 
                    "error": f"ML processing failed: {ml_data.get('error', 'Unknown error')}",
                    "details": "ML service not available - this is expected if Ollama is not running"
                }
            
            # Step 3: Check ML response data
            ml_result = ml_data.get("data", {})
            required_fields = ["master_summary", "timeline_summary", "key_entities"]
            missing_fields = [field for field in required_fields if field not in ml_result]
            if missing_fields:
                return {"status": "fail", "error": f"ML result missing fields: {missing_fields}"}
            
            return {
                "status": "pass",
                "details": "ML processing successful",
                "ml_result": {
                    "summary_length": len(ml_result.get("master_summary", "")),
                    "entities_count": len(ml_result.get("key_entities", {})),
                    "sources": ml_result.get("source_diversity", {}).get("sources", [])
                }
            }
            
        except Exception as e:
            return {"status": "fail", "error": str(e)}
    
    def _verify_frontend_display_workflow(self) -> Dict[str, Any]:
        """Verify frontend display workflow"""
        logger.info("🔍 Verifying frontend display workflow...")
        
        try:
            # Step 1: Check frontend accessibility
            response = requests.get(self.frontend_base, timeout=5)
            if response.status_code != 200:
                return {"status": "fail", "error": f"Frontend not accessible: {response.status_code}"}
            
            # Step 2: Check API proxy (if frontend is running)
            try:
                api_response = requests.get(f"{self.frontend_base}/api/health/", timeout=5)
                if api_response.status_code == 200:
                    proxy_status = "working"
                else:
                    proxy_status = f"failed ({api_response.status_code})"
            except:
                proxy_status = "not accessible"
            
            return {
                "status": "pass",
                "details": f"Frontend accessible, API proxy: {proxy_status}",
                "frontend_status": response.status_code,
                "proxy_status": proxy_status
            }
            
        except Exception as e:
            return {"status": "fail", "error": str(e)}
    
    def _verify_rss_management_workflow(self) -> Dict[str, Any]:
        """Verify RSS management workflow"""
        logger.info("🔍 Verifying RSS management workflow...")
        
        try:
            # Step 1: Check RSS feeds endpoint
            response = requests.get(f"{self.api_base}/api/rss/feeds/", timeout=5)
            if response.status_code != 200:
                return {"status": "fail", "error": f"RSS feeds endpoint failed: {response.status_code}"}
            
            feeds = response.json().get("data", {}).get("feeds", [])
            if not feeds:
                return {"status": "fail", "error": "No RSS feeds found in system"}
            
            # Step 2: Check RSS feed structure
            feed = feeds[0]
            required_fields = ["id", "name", "url", "status"]
            missing_fields = [field for field in required_fields if field not in feed]
            if missing_fields:
                return {"status": "fail", "error": f"RSS feed missing fields: {missing_fields}"}
            
            # Step 3: Test RSS feed refresh
            feed_id = feed["id"]
            refresh_response = requests.post(f"{self.api_base}/api/rss/feeds/{feed_id}/refresh", timeout=10)
            if refresh_response.status_code != 200:
                return {"status": "fail", "error": f"RSS feed refresh failed: {refresh_response.status_code}"}
            
            return {
                "status": "pass",
                "details": f"Found {len(feeds)} RSS feeds, refresh test successful",
                "feed_count": len(feeds),
                "sample_feed": {
                    "id": feed["id"],
                    "name": feed["name"],
                    "url": feed["url"],
                    "status": feed["status"]
                }
            }
            
        except Exception as e:
            return {"status": "fail", "error": str(e)}
    
    def run_all_verifications(self) -> Dict[str, Any]:
        """Run all integration verifications"""
        logger.info("🚀 Starting comprehensive integration verification...")
        
        results = {}
        total_tests = len(self.workflows)
        passed_tests = 0
        
        for workflow_name, workflow_func in self.workflows.items():
            logger.info(f"Running {workflow_name} verification...")
            result = workflow_func()
            results[workflow_name] = result
            
            if result["status"] == "pass":
                passed_tests += 1
                logger.info(f"✅ {workflow_name}: PASSED")
            else:
                logger.error(f"❌ {workflow_name}: FAILED - {result.get('error', 'Unknown error')}")
        
        overall_status = "pass" if passed_tests == total_tests else "fail"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "success_rate": f"{(passed_tests/total_tests)*100:.1f}%"
            },
            "results": results
        }
    
    def display_verification_report(self, report: Dict[str, Any]):
        """Display formatted verification report"""
        print("\n" + "="*80)
        print(f"NEWS INTELLIGENCE INTEGRATION VERIFICATION - {report['timestamp']}")
        print("="*80)
        
        # Overall status
        status_emoji = "✅" if report["overall_status"] == "pass" else "❌"
        print(f"\n{status_emoji} OVERALL STATUS: {report['overall_status'].upper()}")
        print(f"📊 SUCCESS RATE: {report['summary']['success_rate']} ({report['summary']['passed_tests']}/{report['summary']['total_tests']})")
        
        # Individual test results
        print(f"\n🔍 WORKFLOW VERIFICATION RESULTS:")
        for workflow_name, result in report["results"].items():
            status_emoji = "✅" if result["status"] == "pass" else "❌"
            print(f"  {status_emoji} {workflow_name.replace('_', ' ').title()}: {result['status'].upper()}")
            print(f"    Details: {result.get('details', 'No details')}")
            if result.get("error"):
                print(f"    Error: {result['error']}")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        if report["overall_status"] == "pass":
            print("  ✅ All workflows are functioning correctly!")
            print("  ✅ System integration is healthy!")
        else:
            failed_workflows = [name for name, result in report["results"].items() if result["status"] == "fail"]
            print(f"  ⚠️ Focus on fixing: {', '.join(failed_workflows)}")
            print("  ⚠️ Review error messages above for specific issues")
        
        print("\n" + "="*80)

def main():
    """Main function"""
    verifier = IntegrationVerifier()
    
    print("🔍 News Intelligence Integration Verifier")
    print("=" * 50)
    
    while True:
        try:
            user_input = input("\nOptions:\n1. Run full verification\n2. Run specific workflow\n3. Exit\n\nChoice: ").strip()
            
            if user_input == "1":
                report = verifier.run_all_verifications()
                verifier.display_verification_report(report)
                
            elif user_input == "2":
                print("\nAvailable workflows:")
                for i, workflow_name in enumerate(verifier.workflows.keys(), 1):
                    print(f"  {i}. {workflow_name.replace('_', ' ').title()}")
                
                try:
                    choice = int(input("\nSelect workflow (number): ")) - 1
                    workflow_names = list(verifier.workflows.keys())
                    if 0 <= choice < len(workflow_names):
                        workflow_name = workflow_names[choice]
                        result = verifier.workflows[workflow_name]()
                        print(f"\n{workflow_name.replace('_', ' ').title()} Result:")
                        print(f"Status: {result['status'].upper()}")
                        print(f"Details: {result.get('details', 'No details')}")
                        if result.get('error'):
                            print(f"Error: {result['error']}")
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Please enter a valid number.")
                    
            elif user_input == "3":
                print("Exiting integration verifier.")
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nExiting integration verifier.")
            break
        except Exception as e:
            logger.error(f"Error in integration verifier: {e}")

if __name__ == "__main__":
    main()
