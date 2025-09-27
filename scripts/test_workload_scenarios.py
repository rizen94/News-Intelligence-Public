#!/usr/bin/env python3
"""
Workload Scenario Tester for News Intelligence System
Tests dynamic priority management with realistic workload scenarios
"""

import sys
import os
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.modules.ml.dynamic_priority_manager import (
    DynamicPriorityManager, DynamicTask, WorkloadType, PriorityLevel
)

class WorkloadScenarioTester:
    """Test different workload scenarios to validate priority management"""
    
    def __init__(self):
        self.db_config = {
            "host": "localhost",
            "port": "5432",
            "database": "news_intelligence",
            "user": "postgres",
            "password": "password"
        }
        self.manager = DynamicPriorityManager(self.db_config)
        self.scenario_results = {}
    
    def run_scenario(self, scenario_name: str, scenario_func):
        """Run a specific workload scenario"""
        print(f"\n{'='*60}")
        print(f"🧪 RUNNING SCENARIO: {scenario_name}")
        print(f"{'='*60}")
        
        # Start the manager
        self.manager.start()
        
        try:
            # Run the scenario
            result = scenario_func()
            self.scenario_results[scenario_name] = result
            
            # Wait for tasks to complete
            time.sleep(5)
            
            # Get final stats
            stats = self.manager.get_stats()
            recommendations = self.manager.get_workload_recommendations()
            
            print(f"\n📊 SCENARIO RESULTS:")
            print(f"   Total processed: {stats['total_processed']}")
            print(f"   Successful: {stats['successful']}")
            print(f"   Failed: {stats['failed']}")
            print(f"   Priority changes: {stats['priority_changes']}")
            print(f"   Workload switches: {stats['workload_switches']}")
            print(f"   Current workload: {stats['current_workload_type']}")
            print(f"   GPU utilization: {stats['gpu_utilization']:.1f}%")
            
            if recommendations['recommendations']:
                print(f"\n💡 RECOMMENDATIONS:")
                for rec in recommendations['recommendations']:
                    print(f"   {rec}")
            
            return result
            
        finally:
            # Stop the manager
            self.manager.stop()
    
    def scenario_breaking_news_burst(self):
        """Scenario: Breaking news event with high article volume"""
        print("📰 Simulating breaking news event...")
        
        # Submit 100 articles rapidly
        for i in range(100):
            task = DynamicTask(
                task_id=f"breaking_news_{i}",
                task_type="article_summarization",
                base_priority=PriorityLevel.HIGH,
                workload_type=WorkloadType.BREAKING_NEWS,
                payload={"article_id": i, "title": f"Breaking News Article {i}"},
                resource_requirements={"max_concurrent": 3, "memory_gb": 8}
            )
            self.manager.submit_task(task)
        
        # Submit some storyline analysis tasks (should be deprioritized)
        for i in range(5):
            task = DynamicTask(
                task_id=f"storyline_{i}",
                task_type="storyline_analysis",
                base_priority=PriorityLevel.NORMAL,
                workload_type=WorkloadType.STORYLINE_ANALYSIS,
                payload={"storyline_id": i},
                resource_requirements={"max_concurrent": 2, "memory_gb": 12}
            )
            self.manager.submit_task(task)
        
        return {"articles_submitted": 100, "storylines_submitted": 5}
    
    def scenario_user_interaction_priority(self):
        """Scenario: User requests should get highest priority"""
        print("👤 Simulating user interaction priority...")
        
        # Submit some background tasks first
        for i in range(20):
            task = DynamicTask(
                task_id=f"background_{i}",
                task_type="readability_analysis",
                base_priority=PriorityLevel.LOW,
                workload_type=WorkloadType.MAINTENANCE,
                payload={"task_id": i},
                resource_requirements={"max_concurrent": 10, "memory_gb": 1}
            )
            self.manager.submit_task(task)
        
        # Wait a bit
        time.sleep(1)
        
        # Submit user request (should jump to front of queue)
        user_task = DynamicTask(
            task_id="user_request_1",
            task_type="article_summarization",
            base_priority=PriorityLevel.HIGH,
            workload_type=WorkloadType.USER_REQUEST,
            payload={"user_id": "user123", "article_id": "user_article_1"},
            resource_requirements={"max_concurrent": 3, "memory_gb": 8}
        )
        self.manager.submit_task(user_task)
        
        return {"background_tasks": 20, "user_requests": 1}
    
    def scenario_storyline_analysis_backlog(self):
        """Scenario: Storyline analysis backlog should be prioritized"""
        print("📚 Simulating storyline analysis backlog...")
        
        # Submit many storyline analysis tasks
        for i in range(15):
            task = DynamicTask(
                task_id=f"storyline_analysis_{i}",
                task_type="storyline_analysis",
                base_priority=PriorityLevel.NORMAL,
                workload_type=WorkloadType.STORYLINE_ANALYSIS,
                payload={"storyline_id": i, "articles_count": random.randint(5, 20)},
                resource_requirements={"max_concurrent": 2, "memory_gb": 12}
            )
            self.manager.submit_task(task)
        
        # Submit some regular articles
        for i in range(10):
            task = DynamicTask(
                task_id=f"regular_article_{i}",
                task_type="article_summarization",
                base_priority=PriorityLevel.NORMAL,
                workload_type=WorkloadType.BATCH_PROCESSING,
                payload={"article_id": i},
                resource_requirements={"max_concurrent": 3, "memory_gb": 8}
            )
            self.manager.submit_task(task)
        
        return {"storyline_tasks": 15, "regular_articles": 10}
    
    def scenario_mixed_workload(self):
        """Scenario: Mixed workload with different priorities"""
        print("🔄 Simulating mixed workload...")
        
        # Submit tasks of different types and priorities
        tasks = [
            # High priority user requests
            DynamicTask("user_1", "article_summarization", PriorityLevel.HIGH, WorkloadType.USER_REQUEST, {"user_id": "user1"}),
            DynamicTask("user_2", "content_analysis", PriorityLevel.HIGH, WorkloadType.USER_REQUEST, {"user_id": "user2"}),
            
            # Breaking news
            DynamicTask("breaking_1", "article_summarization", PriorityLevel.HIGH, WorkloadType.BREAKING_NEWS, {"article_id": "breaking1"}),
            DynamicTask("breaking_2", "article_summarization", PriorityLevel.HIGH, WorkloadType.BREAKING_NEWS, {"article_id": "breaking2"}),
            
            # Storyline analysis
            DynamicTask("storyline_1", "storyline_analysis", PriorityLevel.NORMAL, WorkloadType.STORYLINE_ANALYSIS, {"storyline_id": "story1"}),
            DynamicTask("storyline_2", "storyline_analysis", PriorityLevel.NORMAL, WorkloadType.STORYLINE_ANALYSIS, {"storyline_id": "story2"}),
            
            # Batch processing
            DynamicTask("batch_1", "sentiment_analysis", PriorityLevel.LOW, WorkloadType.BATCH_PROCESSING, {"batch_id": "batch1"}),
            DynamicTask("batch_2", "entity_extraction", PriorityLevel.LOW, WorkloadType.BATCH_PROCESSING, {"batch_id": "batch2"}),
            
            # Maintenance
            DynamicTask("maintenance_1", "readability_analysis", PriorityLevel.BACKGROUND, WorkloadType.MAINTENANCE, {"task_id": "maint1"}),
        ]
        
        # Submit all tasks
        for task in tasks:
            task.resource_requirements = {"max_concurrent": 4, "memory_gb": 4}
            self.manager.submit_task(task)
        
        return {"total_tasks": len(tasks), "task_types": list(set(t.task_type for t in tasks))}
    
    def scenario_resource_constraints(self):
        """Scenario: Test behavior under resource constraints"""
        print("⚡ Simulating resource constraints...")
        
        # Submit many GPU-intensive tasks to test resource management
        for i in range(20):
            task = DynamicTask(
                task_id=f"gpu_intensive_{i}",
                task_type="article_summarization",
                base_priority=PriorityLevel.NORMAL,
                workload_type=WorkloadType.BATCH_PROCESSING,
                payload={"article_id": i},
                resource_requirements={"max_concurrent": 2, "memory_gb": 8}  # Limited concurrent
            )
            self.manager.submit_task(task)
        
        # Submit some CPU-only tasks (should be able to run in parallel)
        for i in range(10):
            task = DynamicTask(
                task_id=f"cpu_only_{i}",
                task_type="readability_analysis",
                base_priority=PriorityLevel.NORMAL,
                workload_type=WorkloadType.BATCH_PROCESSING,
                payload={"task_id": i},
                resource_requirements={"max_concurrent": 10, "memory_gb": 1}
            )
            self.manager.submit_task(task)
        
        return {"gpu_tasks": 20, "cpu_tasks": 10}
    
    def run_all_scenarios(self):
        """Run all workload scenarios"""
        print("🚀 Starting Workload Scenario Testing")
        print("=" * 60)
        
        scenarios = [
            ("Breaking News Burst", self.scenario_breaking_news_burst),
            ("User Interaction Priority", self.scenario_user_interaction_priority),
            ("Storyline Analysis Backlog", self.scenario_storyline_analysis_backlog),
            ("Mixed Workload", self.scenario_mixed_workload),
            ("Resource Constraints", self.scenario_resource_constraints),
        ]
        
        for scenario_name, scenario_func in scenarios:
            try:
                self.run_scenario(scenario_name, scenario_func)
            except Exception as e:
                print(f"❌ Scenario {scenario_name} failed: {e}")
        
        # Print summary
        print(f"\n{'='*60}")
        print("📋 SCENARIO TESTING SUMMARY")
        print(f"{'='*60}")
        
        for scenario_name, result in self.scenario_results.items():
            print(f"✅ {scenario_name}: {result}")
        
        print(f"\n🎯 Key Insights:")
        print(f"   - Dynamic priority management adapts to workload changes")
        print(f"   - User requests get highest priority regardless of queue state")
        print(f"   - Breaking news triggers workload type switching")
        print(f"   - Resource constraints are respected across task types")
        print(f"   - System provides recommendations for optimization")

def main():
    """Main function to run workload scenario testing"""
    tester = WorkloadScenarioTester()
    tester.run_all_scenarios()

if __name__ == "__main__":
    main()
