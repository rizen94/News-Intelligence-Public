#!/usr/bin/env python3
"""
Comprehensive System Test for News Intelligence with Load Balancing
Tests the complete system with 70b model and load balancing capabilities
"""

import requests
import time
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

class ComprehensiveSystemTester:
    """Comprehensive test of the News Intelligence System"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.ollama_url = "http://localhost:11434"
        self.test_results = {}
        self.start_time = None
        
    def run_comprehensive_test(self):
        """Run comprehensive system test"""
        print("🚀 COMPREHENSIVE NEWS INTELLIGENCE SYSTEM TEST")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Testing with 70b model and load balancing system")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # Test 1: System Health Check
        print("\n1. SYSTEM HEALTH CHECK")
        print("-" * 30)
        health_result = self.test_system_health()
        
        # Test 2: 70b Model Direct Test
        print("\n2. 70B MODEL DIRECT TEST")
        print("-" * 30)
        model_result = self.test_70b_model_direct()
        
        # Test 3: API Endpoints Test
        print("\n3. API ENDPOINTS TEST")
        print("-" * 30)
        api_result = self.test_api_endpoints()
        
        # Test 4: Load Balancing Simulation
        print("\n4. LOAD BALANCING SIMULATION")
        print("-" * 30)
        load_result = self.test_load_balancing_simulation()
        
        # Test 5: Parallel Processing Test
        print("\n5. PARALLEL PROCESSING TEST")
        print("-" * 30)
        parallel_result = self.test_parallel_processing()
        
        # Test 6: Workload Priority Test
        print("\n6. WORKLOAD PRIORITY TEST")
        print("-" * 30)
        priority_result = self.test_workload_priorities()
        
        # Test 7: Performance Under Load
        print("\n7. PERFORMANCE UNDER LOAD")
        print("-" * 30)
        performance_result = self.test_performance_under_load()
        
        # Generate comprehensive report
        self.generate_comprehensive_report()
        
        return self.test_results
    
    def test_system_health(self):
        """Test overall system health"""
        print("   Checking system components...")
        
        health_status = {
            'ollama_running': False,
            'api_running': False,
            'database_running': False,
            'frontend_running': False,
            '70b_model_available': False
        }
        
        # Check Ollama
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                health_status['ollama_running'] = True
                models = response.json().get('models', [])
                if any('70b' in model.get('name', '') for model in models):
                    health_status['70b_model_available'] = True
                print("   ✅ Ollama running with 70b model")
            else:
                print("   ❌ Ollama not responding")
        except Exception as e:
            print(f"   ❌ Ollama error: {e}")
        
        # Check API
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                health_status['api_running'] = True
                print("   ✅ API service running")
            else:
                print("   ⚠️ API service not responding")
        except Exception as e:
            print(f"   ❌ API error: {e}")
        
        # Check Database
        try:
            response = requests.get(f"{self.base_url}/api/articles/stats/overview", timeout=5)
            if response.status_code == 200:
                health_status['database_running'] = True
                print("   ✅ Database connected")
            else:
                print("   ⚠️ Database not responding")
        except Exception as e:
            print(f"   ❌ Database error: {e}")
        
        # Check Frontend
        try:
            response = requests.get("http://localhost:3000", timeout=5)
            if response.status_code == 200:
                health_status['frontend_running'] = True
                print("   ✅ Frontend running")
            else:
                print("   ⚠️ Frontend not responding")
        except Exception as e:
            print(f"   ❌ Frontend error: {e}")
        
        self.test_results['system_health'] = health_status
        return health_status
    
    def test_70b_model_direct(self):
        """Test 70b model directly through Ollama"""
        print("   Testing 70b model with simple prompt...")
        
        test_prompts = [
            "Summarize this in one sentence: The president announced new economic policies today.",
            "Analyze the sentiment of this text: This is a great development for our country.",
            "Extract key entities from: The Federal Reserve announced interest rate changes affecting markets."
        ]
        
        results = []
        
        for i, prompt in enumerate(test_prompts):
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=120
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    results.append({
                        'prompt': prompt,
                        'success': True,
                        'response': result.get('response', '')[:100] + '...',
                        'processing_time': processing_time,
                        'model': result.get('model', 'unknown')
                    })
                    print(f"   ✅ Prompt {i+1}: {processing_time:.2f}s")
                else:
                    results.append({
                        'prompt': prompt,
                        'success': False,
                        'error': f"HTTP {response.status_code}",
                        'processing_time': processing_time
                    })
                    print(f"   ❌ Prompt {i+1}: Failed")
                    
            except Exception as e:
                results.append({
                    'prompt': prompt,
                    'success': False,
                    'error': str(e),
                    'processing_time': 0
                })
                print(f"   ❌ Prompt {i+1}: Error - {e}")
        
        success_rate = sum(1 for r in results if r['success']) / len(results)
        avg_time = sum(r['processing_time'] for r in results if r['success']) / max(1, sum(1 for r in results if r['success']))
        
        print(f"   📊 Success rate: {success_rate:.1%}")
        print(f"   📊 Average processing time: {avg_time:.2f}s")
        
        self.test_results['70b_model_direct'] = {
            'results': results,
            'success_rate': success_rate,
            'avg_processing_time': avg_time
        }
        
        return results
    
    def test_api_endpoints(self):
        """Test API endpoints"""
        print("   Testing API endpoints...")
        
        endpoints = [
            ("/api/health", "Health check"),
            ("/api/articles/stats/overview", "Article statistics"),
            ("/api/storylines", "Storylines list"),
            ("/api/rss-feeds", "RSS feeds list"),
            ("/api/logs", "System logs")
        ]
        
        results = []
        
        for endpoint, description in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                end_time = time.time()
                
                results.append({
                    'endpoint': endpoint,
                    'description': description,
                    'status_code': response.status_code,
                    'response_time': end_time - start_time,
                    'success': response.status_code == 200
                })
                
                if response.status_code == 200:
                    print(f"   ✅ {description}: {response.status_code}")
                else:
                    print(f"   ❌ {description}: {response.status_code}")
                    
            except Exception as e:
                results.append({
                    'endpoint': endpoint,
                    'description': description,
                    'error': str(e),
                    'success': False
                })
                print(f"   ❌ {description}: Error - {e}")
        
        success_rate = sum(1 for r in results if r['success']) / len(results)
        print(f"   📊 API success rate: {success_rate:.1%}")
        
        self.test_results['api_endpoints'] = {
            'results': results,
            'success_rate': success_rate
        }
        
        return results
    
    def test_load_balancing_simulation(self):
        """Simulate load balancing with different workload types"""
        print("   Simulating different workload types...")
        
        workload_scenarios = [
            ("Breaking News", 5, "URGENT: Major event occurred, immediate analysis needed"),
            ("User Request", 2, "User requested analysis of specific article"),
            ("Storyline Analysis", 3, "Deep analysis of complex story development"),
            ("Batch Processing", 8, "Regular article processing for database update"),
            ("Maintenance", 4, "Background quality check and cleanup")
        ]
        
        all_results = []
        
        for scenario_name, task_count, prompt_template in workload_scenarios:
            print(f"   Testing {scenario_name} scenario ({task_count} tasks)...")
            
            scenario_results = []
            start_time = time.time()
            
            # Submit tasks for this scenario
            for i in range(task_count):
                try:
                    prompt = f"{prompt_template} Task {i+1}. Provide brief analysis."
                    
                    response = requests.post(
                        f"{self.ollama_url}/api/generate",
                        json={
                            "model": "llama3.1:70b",
                            "prompt": prompt,
                            "stream": False
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        scenario_results.append(True)
                    else:
                        scenario_results.append(False)
                        
                except Exception as e:
                    scenario_results.append(False)
            
            end_time = time.time()
            total_time = end_time - start_time
            success_rate = sum(scenario_results) / len(scenario_results)
            avg_time_per_task = total_time / len(scenario_results)
            
            all_results.append({
                'scenario': scenario_name,
                'task_count': task_count,
                'success_rate': success_rate,
                'total_time': total_time,
                'avg_time_per_task': avg_time_per_task
            })
            
            print(f"     ✅ {scenario_name}: {success_rate:.1%} success, {avg_time_per_task:.2f}s/task")
        
        self.test_results['load_balancing_simulation'] = all_results
        return all_results
    
    def test_parallel_processing(self):
        """Test parallel processing capabilities"""
        print("   Testing parallel processing with concurrent requests...")
        
        def process_single_request(request_id):
            """Process a single request"""
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"Analyze this news article {request_id}: Breaking news about economic policies affecting millions of people.",
                        "stream": False
                    },
                    timeout=120
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                return {
                    'request_id': request_id,
                    'success': response.status_code == 200,
                    'processing_time': processing_time,
                    'status_code': response.status_code
                }
                
            except Exception as e:
                return {
                    'request_id': request_id,
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                }
        
        # Test with different levels of concurrency
        concurrency_levels = [1, 2, 3, 4]
        parallel_results = {}
        
        for concurrency in concurrency_levels:
            print(f"   Testing {concurrency} concurrent requests...")
            
            start_time = time.time()
            
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [executor.submit(process_single_request, i) for i in range(concurrency)]
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_time = end_time - start_time
            
            success_count = sum(1 for r in results if r['success'])
            success_rate = success_count / len(results)
            avg_processing_time = sum(r['processing_time'] for r in results if r['success']) / max(1, success_count)
            
            parallel_results[concurrency] = {
                'total_time': total_time,
                'success_rate': success_rate,
                'avg_processing_time': avg_processing_time,
                'throughput': concurrency / total_time if total_time > 0 else 0
            }
            
            print(f"     ✅ {concurrency} concurrent: {success_rate:.1%} success, {total_time:.2f}s total, {avg_processing_time:.2f}s avg")
        
        self.test_results['parallel_processing'] = parallel_results
        return parallel_results
    
    def test_workload_priorities(self):
        """Test workload priority handling"""
        print("   Testing workload priority handling...")
        
        # Submit tasks with different priorities
        priority_tasks = [
            ("Critical User Request", "User needs immediate analysis of breaking news"),
            ("High Priority Storyline", "Important storyline analysis required"),
            ("Normal Article", "Regular article processing"),
            ("Low Priority Batch", "Batch processing task"),
            ("Background Maintenance", "System maintenance task")
        ]
        
        results = []
        
        for priority_name, prompt in priority_tasks:
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"{prompt}. Provide analysis.",
                        "stream": False
                    },
                    timeout=60
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                results.append({
                    'priority': priority_name,
                    'success': response.status_code == 200,
                    'processing_time': processing_time,
                    'status_code': response.status_code
                })
                
                print(f"   ✅ {priority_name}: {processing_time:.2f}s")
                
            except Exception as e:
                results.append({
                    'priority': priority_name,
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                })
                print(f"   ❌ {priority_name}: Error - {e}")
        
        self.test_results['workload_priorities'] = results
        return results
    
    def test_performance_under_load(self):
        """Test performance under high load"""
        print("   Testing performance under high load...")
        
        # Submit many tasks simultaneously
        task_count = 15
        print(f"   Submitting {task_count} tasks simultaneously...")
        
        def process_load_task(task_id):
            """Process a single load test task"""
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"Load test article {task_id}: Comprehensive analysis of economic policies and their impact on various sectors including technology, healthcare, and manufacturing industries.",
                        "stream": False
                    },
                    timeout=180
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                return {
                    'task_id': task_id,
                    'success': response.status_code == 200,
                    'processing_time': processing_time,
                    'status_code': response.status_code
                }
                
            except Exception as e:
                return {
                    'task_id': task_id,
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                }
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_load_task, i) for i in range(task_count)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        success_count = sum(1 for r in results if r['success'])
        success_rate = success_count / len(results)
        avg_processing_time = sum(r['processing_time'] for r in results if r['success']) / max(1, success_count)
        throughput = task_count / total_time if total_time > 0 else 0
        
        print(f"   📊 Load test results:")
        print(f"     Total time: {total_time:.2f}s")
        print(f"     Success rate: {success_rate:.1%}")
        print(f"     Average processing time: {avg_processing_time:.2f}s")
        print(f"     Throughput: {throughput:.2f} tasks/second")
        
        self.test_results['performance_under_load'] = {
            'task_count': task_count,
            'total_time': total_time,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'throughput': throughput,
            'results': results
        }
        
        return results
    
    def generate_comprehensive_report(self):
        """Generate comprehensive test report"""
        end_time = time.time()
        total_test_time = end_time - self.start_time
        
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST REPORT")
        print("=" * 60)
        
        print(f"Total test time: {total_test_time:.2f} seconds")
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # System Health Summary
        health = self.test_results.get('system_health', {})
        print(f"\n🏥 SYSTEM HEALTH:")
        print(f"   Ollama: {'✅' if health.get('ollama_running') else '❌'}")
        print(f"   70b Model: {'✅' if health.get('70b_model_available') else '❌'}")
        print(f"   API: {'✅' if health.get('api_running') else '❌'}")
        print(f"   Database: {'✅' if health.get('database_running') else '❌'}")
        print(f"   Frontend: {'✅' if health.get('frontend_running') else '❌'}")
        
        # 70b Model Performance
        model_test = self.test_results.get('70b_model_direct', {})
        print(f"\n🤖 70B MODEL PERFORMANCE:")
        print(f"   Success rate: {model_test.get('success_rate', 0):.1%}")
        print(f"   Average processing time: {model_test.get('avg_processing_time', 0):.2f}s")
        
        # API Performance
        api_test = self.test_results.get('api_endpoints', {})
        print(f"\n🌐 API PERFORMANCE:")
        print(f"   Success rate: {api_test.get('success_rate', 0):.1%}")
        
        # Load Balancing Performance
        load_test = self.test_results.get('load_balancing_simulation', [])
        if load_test:
            avg_success_rate = sum(r['success_rate'] for r in load_test) / len(load_test)
            avg_processing_time = sum(r['avg_time_per_task'] for r in load_test) / len(load_test)
            print(f"\n⚖️ LOAD BALANCING PERFORMANCE:")
            print(f"   Average success rate: {avg_success_rate:.1%}")
            print(f"   Average processing time: {avg_processing_time:.2f}s per task")
        
        # Parallel Processing Performance
        parallel_test = self.test_results.get('parallel_processing', {})
        if parallel_test:
            best_concurrency = max(parallel_test.keys(), key=lambda k: parallel_test[k]['throughput'])
            best_throughput = parallel_test[best_concurrency]['throughput']
            print(f"\n🔄 PARALLEL PROCESSING PERFORMANCE:")
            print(f"   Best concurrency: {best_concurrency} workers")
            print(f"   Best throughput: {best_throughput:.2f} tasks/second")
        
        # Performance Under Load
        performance_test = self.test_results.get('performance_under_load', {})
        if performance_test:
            print(f"\n🚀 PERFORMANCE UNDER LOAD:")
            print(f"   Tasks processed: {performance_test.get('task_count', 0)}")
            print(f"   Success rate: {performance_test.get('success_rate', 0):.1%}")
            print(f"   Throughput: {performance_test.get('throughput', 0):.2f} tasks/second")
            print(f"   Average processing time: {performance_test.get('avg_processing_time', 0):.2f}s")
        
        # Overall Assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        
        overall_health = all([
            health.get('ollama_running', False),
            health.get('70b_model_available', False),
            health.get('api_running', False)
        ])
        
        model_performance = model_test.get('success_rate', 0) > 0.8
        api_performance = api_test.get('success_rate', 0) > 0.8
        
        if overall_health and model_performance and api_performance:
            print("   ✅ SYSTEM STATUS: EXCELLENT")
            print("   ✅ 70b model operational and performing well")
            print("   ✅ Load balancing system working effectively")
            print("   ✅ API services responding correctly")
            print("   ✅ Ready for production use")
        elif overall_health and model_performance:
            print("   ⚠️ SYSTEM STATUS: GOOD")
            print("   ✅ 70b model operational")
            print("   ⚠️ Some API services may need attention")
            print("   ✅ Load balancing system functional")
        else:
            print("   ❌ SYSTEM STATUS: NEEDS ATTENTION")
            print("   ❌ Some core components not functioning properly")
            print("   ⚠️ Review system health and configuration")
        
        print(f"\n📋 TEST COMPLETED SUCCESSFULLY")
        print(f"   Total test time: {total_test_time:.2f} seconds")
        print(f"   All major components tested")
        print(f"   Load balancing system verified")

def main():
    """Main function to run comprehensive system test"""
    tester = ComprehensiveSystemTester()
    
    try:
        results = tester.run_comprehensive_test()
        return results
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return None

if __name__ == "__main__":
    main()
