#!/usr/bin/env python3
"""
Connect Pipeline - Simple, Direct Integration
Connects all moving parts from RSS collection to storyline dossier
"""

import requests
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_pipeline_health():
    """Check health of entire pipeline"""
    print("🔍 Checking Pipeline Health...")
    print("=" * 50)
    
    api_base = "http://localhost:8000"
    health_status = {}
    
    # Check RSS Collection
    try:
        rss_resp = requests.get(f"{api_base}/api/rss/feeds/", timeout=5)
        if rss_resp.status_code == 200:
            feeds = rss_resp.json().get("data", {}).get("feeds", [])
            health_status["rss_collection"] = {
                "status": "✅ Healthy",
                "feeds": len(feeds),
                "active": len([f for f in feeds if f.get("status") == "active"])
            }
        else:
            health_status["rss_collection"] = {"status": "❌ Unhealthy", "error": f"HTTP {rss_resp.status_code}"}
    except Exception as e:
        health_status["rss_collection"] = {"status": "❌ Unhealthy", "error": str(e)}
    
    # Check Article Processing
    try:
        articles_resp = requests.get(f"{api_base}/api/articles/?limit=1", timeout=5)
        if articles_resp.status_code == 200:
            articles = articles_resp.json().get("data", {}).get("articles", [])
            health_status["article_processing"] = {
                "status": "✅ Healthy",
                "articles": len(articles)
            }
        else:
            health_status["article_processing"] = {"status": "❌ Unhealthy", "error": f"HTTP {articles_resp.status_code}"}
    except Exception as e:
        health_status["article_processing"] = {"status": "❌ Unhealthy", "error": str(e)}
    
    # Check Storyline Creation
    try:
        storylines_resp = requests.get(f"{api_base}/api/storylines/", timeout=5)
        if storylines_resp.status_code == 200:
            storylines = storylines_resp.json().get("data", {}).get("storylines", [])
            health_status["storyline_creation"] = {
                "status": "✅ Healthy",
                "storylines": len(storylines)
            }
        else:
            health_status["storyline_creation"] = {"status": "❌ Unhealthy", "error": f"HTTP {storylines_resp.status_code}"}
    except Exception as e:
        health_status["storyline_creation"] = {"status": "❌ Unhealthy", "error": str(e)}
    
    # Check ML Processing
    try:
        ml_resp = requests.post(f"{api_base}/api/storylines/1/process-ml", timeout=10)
        if ml_resp.status_code == 200:
            ml_data = ml_resp.json()
            if ml_data.get("success"):
                health_status["ml_processing"] = {"status": "✅ Healthy", "note": "ML processing working"}
            else:
                health_status["ml_processing"] = {"status": "⚠️ Degraded", "error": ml_data.get("error")}
        else:
            health_status["ml_processing"] = {"status": "❌ Unhealthy", "error": f"HTTP {ml_resp.status_code}"}
    except Exception as e:
        health_status["ml_processing"] = {"status": "❌ Unhealthy", "error": str(e)}
    
    # Check Dossier Generation
    try:
        dossier_resp = requests.get(f"{api_base}/api/storylines/1/report", timeout=5)
        if dossier_resp.status_code == 200:
            health_status["dossier_generation"] = {"status": "✅ Healthy", "note": "Dossier generation working"}
        else:
            health_status["dossier_generation"] = {"status": "❌ Unhealthy", "error": f"HTTP {dossier_resp.status_code}"}
    except Exception as e:
        health_status["dossier_generation"] = {"status": "❌ Unhealthy", "error": str(e)}
    
    # Display results
    for component, status in health_status.items():
        print(f"{component.replace('_', ' ').title()}: {status['status']}")
        if "error" in status:
            print(f"  Error: {status['error']}")
        if "feeds" in status:
            print(f"  Feeds: {status['feeds']} total, {status['active']} active")
        if "articles" in status:
            print(f"  Articles: {status['articles']}")
        if "storylines" in status:
            print(f"  Storylines: {status['storylines']}")
        if "note" in status:
            print(f"  Note: {status['note']}")
        print()
    
    return health_status

def run_pipeline_workflow():
    """Run the complete pipeline workflow"""
    print("🚀 Running Complete Pipeline Workflow...")
    print("=" * 50)
    
    api_base = "http://localhost:8000"
    
    # Step 1: RSS Collection
    print("📰 Step 1: RSS Collection")
    try:
        feeds_resp = requests.get(f"{api_base}/api/rss/feeds/", timeout=5)
        if feeds_resp.status_code == 200:
            feeds = feeds_resp.json().get("data", {}).get("feeds", [])
            active_feeds = [f for f in feeds if f.get("status") == "active"]
            print(f"  Found {len(feeds)} feeds, {len(active_feeds)} active")
            
            # Collect from each active feed
            for feed in active_feeds:
                try:
                    refresh_resp = requests.post(f"{api_base}/api/rss/feeds/{feed['id']}/refresh", timeout=10)
                    if refresh_resp.status_code == 200:
                        print(f"  ✅ Refreshed {feed['name']}")
                    else:
                        print(f"  ❌ Failed to refresh {feed['name']}")
                except Exception as e:
                    print(f"  ❌ Error refreshing {feed['name']}: {e}")
        else:
            print(f"  ❌ Failed to get RSS feeds: {feeds_resp.status_code}")
    except Exception as e:
        print(f"  ❌ RSS collection failed: {e}")
    
    print()
    
    # Step 2: Article Processing
    print("📄 Step 2: Article Processing")
    try:
        articles_resp = requests.get(f"{api_base}/api/articles/?limit=10", timeout=5)
        if articles_resp.status_code == 200:
            articles = articles_resp.json().get("data", {}).get("articles", [])
            processed_count = sum(1 for article in articles if article.get("ml_processed"))
            print(f"  Found {len(articles)} articles, {processed_count} processed")
        else:
            print(f"  ❌ Failed to get articles: {articles_resp.status_code}")
    except Exception as e:
        print(f"  ❌ Article processing failed: {e}")
    
    print()
    
    # Step 3: ML Processing
    print("🤖 Step 3: ML Processing")
    try:
        ml_resp = requests.post(f"{api_base}/api/storylines/1/process-ml", timeout=30)
        if ml_resp.status_code == 200:
            ml_data = ml_resp.json()
            if ml_data.get("success"):
                print("  ✅ ML processing successful")
            else:
                print(f"  ❌ ML processing failed: {ml_data.get('error')}")
        else:
            print(f"  ❌ ML processing failed: HTTP {ml_resp.status_code}")
    except Exception as e:
        print(f"  ❌ ML processing failed: {e}")
    
    print()
    
    # Step 4: Dossier Generation
    print("📋 Step 4: Dossier Generation")
    try:
        dossier_resp = requests.get(f"{api_base}/api/storylines/1/report", timeout=10)
        if dossier_resp.status_code == 200:
            print("  ✅ Dossier generation successful")
        else:
            print(f"  ❌ Dossier generation failed: HTTP {dossier_resp.status_code}")
    except Exception as e:
        print(f"  ❌ Dossier generation failed: {e}")
    
    print()
    print("🎯 Pipeline workflow complete!")

def main():
    """Main function"""
    print("🔗 News Intelligence Pipeline Connector")
    print("=" * 50)
    
    # Check pipeline health
    health_status = check_pipeline_health()
    
    # Run pipeline workflow
    run_pipeline_workflow()
    
    print("=" * 50)
    print("✅ Pipeline connection check complete!")

if __name__ == "__main__":
    main()
