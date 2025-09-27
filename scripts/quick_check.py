#!/usr/bin/env python3
"""
Quick System Check - Simple, Practical System Health Check
One script to rule them all - actually use this one!
"""

import requests
import subprocess
import json
from datetime import datetime

def check_service(name, url, timeout=5):
    """Quick service health check"""
    try:
        response = requests.get(url, timeout=timeout)
        return "✅" if response.status_code == 200 else "❌"
    except:
        return "❌"

def check_docker_service(name):
    """Quick Docker service check"""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={name}", "--format", "{{.Status}}"],
            capture_output=True, text=True, timeout=5
        )
        if "Up" in result.stdout:
            return "✅"
        else:
            return "❌"
    except:
        return "❌"

def check_ollama_download():
    """Check Ollama download progress"""
    try:
        with open("ollama_download.log", "r") as f:
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                if "successfully pulled" in last_line.lower():
                    return "✅ Complete"
                elif "pulling" in last_line.lower():
                    return "🔄 Downloading"
                else:
                    return f"🔄 {last_line[:50]}..."
            else:
                return "❌ No log"
    except:
        return "❌ No log"

def main():
    """Main quick check function"""
    print("🔍 News Intelligence - Quick System Check")
    print("=" * 50)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Core Services
    print("📊 CORE SERVICES:")
    print(f"  API:           {check_service('API', 'http://localhost:8000/api/health/')}")
    print(f"  Frontend:      {check_service('Frontend', 'http://localhost:3000')}")
    print(f"  PostgreSQL:    {check_docker_service('news-intelligence-postgres')}")
    print(f"  Redis:         {check_docker_service('news-intelligence-redis')}")
    print(f"  Ollama:        {check_service('Ollama', 'http://localhost:11434/api/tags')}")
    print()
    
    # Data Status
    print("📈 DATA STATUS:")
    try:
        # Articles
        articles_resp = requests.get("http://localhost:8000/api/articles/?limit=1", timeout=5)
        if articles_resp.status_code == 200:
            articles_count = len(articles_resp.json().get("data", {}).get("articles", []))
            print(f"  Articles:      ✅ {articles_count} found")
        else:
            print(f"  Articles:      ❌ API Error")
    except:
        print(f"  Articles:      ❌ Connection Failed")
    
    try:
        # Storylines
        storylines_resp = requests.get("http://localhost:8000/api/storylines/", timeout=5)
        if storylines_resp.status_code == 200:
            storylines_count = len(storylines_resp.json().get("data", {}).get("storylines", []))
            print(f"  Storylines:    ✅ {storylines_count} found")
        else:
            print(f"  Storylines:    ❌ API Error")
    except:
        print(f"  Storylines:    ❌ Connection Failed")
    
    try:
        # RSS Feeds
        rss_resp = requests.get("http://localhost:8000/api/rss/feeds/", timeout=5)
        if rss_resp.status_code == 200:
            rss_count = len(rss_resp.json().get("data", {}).get("feeds", []))
            print(f"  RSS Feeds:     ✅ {rss_count} configured")
        else:
            print(f"  RSS Feeds:     ❌ API Error")
    except:
        print(f"  RSS Feeds:     ❌ Connection Failed")
    
    print()
    
    # ML Status
    print("🤖 ML STATUS:")
    print(f"  Ollama Download: {check_ollama_download()}")
    
    try:
        # Test ML processing
        ml_resp = requests.post("http://localhost:8000/api/storylines/1/process-ml", timeout=10)
        if ml_resp.status_code == 200:
            ml_data = ml_resp.json()
            if ml_data.get("success"):
                print(f"  ML Processing:  ✅ Working")
            else:
                print(f"  ML Processing:  ❌ {ml_data.get('error', 'Unknown error')}")
        else:
            print(f"  ML Processing:  ❌ HTTP {ml_resp.status_code}")
    except:
        print(f"  ML Processing:  ❌ Connection Failed")
    
    print()
    
    # Quick Actions
    print("🚀 QUICK ACTIONS:")
    print("  • Check Ollama: tail -f ollama_download.log")
    print("  • Restart API:  docker restart news-intelligence-api")
    print("  • View Logs:    docker logs news-intelligence-api --tail 20")
    print("  • Full Check:   docker-compose ps")
    print()
    
    print("=" * 50)

if __name__ == "__main__":
    main()
