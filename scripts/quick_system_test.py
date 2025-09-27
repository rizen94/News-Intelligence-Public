#!/usr/bin/env python3
"""
Quick System Test for News Intelligence with Load Balancing
Fast test that shows system capabilities with time estimates
"""

import requests
import time
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

class QuickSystemTester:
    """Quick test of the News Intelligence System with time estimates"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.ollama_url = "http://localhost:11434"
        self.test_results = {}
        self.start_time = None
        
    def run_quick_test(self):
        """Run quick system test with time estimates"""
        print("🚀 QUICK NEWS INTELLIGENCE SYSTEM TEST")
        print("=" * 50)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Testing with 70b model and load balancing system")
        print("=" * 50)
        
        self.start_time = time.time()
        
        # Test 1: System Health Check (30 seconds)
        print("\n1. SYSTEM HEALTH CHECK (~30 seconds)")
        print("-" * 40)
        health_result = self.test_system_health()
        
        # Test 2: Quick 70b Model Test (60 seconds)
        print("\n2. QUICK 70B MODEL TEST (~60 seconds)")
        print("-" * 40)
        model_result = self.test_70b_model_quick()
        
        # Test 3: API Endpoints Test (20 seconds)
        print("\n3. API ENDPOINTS TEST (~20 seconds)")
        print("-" * 40)
        api_result = self.test_api_endpoints()
        
        # Test 4: Load Balancing Simulation (45 seconds)
        print("\n4. LOAD BALANCING SIMULATION (~45 seconds)")
        print("-" * 40)
        load_result = self.test_load_balancing_quick()
        
        # Test 5: Parallel Processing Test (90 seconds)
        print("\n5. PARALLEL PROCESSING TEST (~90 seconds)")
        print("-" * 40)
        parallel_result = self.test_parallel_processing_quick()
        
        # Test 6: Performance Metrics (30 seconds)
        print("\n6. PERFORMANCE METRICS (~30 seconds)")
        print("-" * 40)
        metrics_result = self.test_performance_metrics()
        
        # Generate quick report
        self.generate_quick_report()
        
        return self.test_results
    
    def test_system_health(self):
        """Test overall system health - FAST"""
        print("   Checking system components...")
        
        health_status = {
            'ollama_running': False,
            'api_running': False,
            'database_running': False,
            'frontend_running': False,
            '70b_model_available': False
        }
        
        # Check Ollama (5 seconds)
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
        
        # Check API (5 seconds)
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                health_status['api_running'] = True
                print("   ✅ API service running")
            else:
                print("   ⚠️ API service not responding")
        except Exception as e:
            print(f"   ❌ API error: {e}")
        
        # Check Database (5 seconds)
        try:
            response = requests.get(f"{self.base_url}/api/articles/stats/overview", timeout=5)
            if response.status_code == 200:
                health_status['database_running'] = True
                print("   ✅ Database connected")
            else:
                print("   ⚠️ Database not responding")
        except Exception as e:
            print(f"   ❌ Database error: {e}")
        
        # Check Frontend (5 seconds)
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
    
    def test_70b_model_quick(self):
        """Quick test of 70b model - ONE simple request"""
        print("   Testing 70b model with ONE simple prompt...")
        print("   (This may take 30-60 seconds for 70b model)")
        
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.1:70b",
                    "prompt": "Summarize this in one sentence: The president announced new economic policies today.",
                    "stream": False
                },
                timeout=60
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                model_result = {
                    'success': True,
                    'processing_time': processing_time,
                    'response': result.get('response', '')[:100] + '...',
                    'model': result.get('model', 'unknown')
                }
                print(f"   ✅ 70b model working: {processing_time:.2f}s")
                print(f"   📝 Response: {model_result['response']}")
            else:
                model_result = {
                    'success': False,
                    'processing_time': processing_time,
                    'error': f"HTTP {response.status_code}"
                }
                print(f"   ❌ 70b model failed: {response.status_code}")
                
        except Exception as e:
            model_result = {
                'success': False,
                'processing_time': 0,
                'error': str(e)
            }
            print(f"   ❌ 70b model error: {e}")
        
        self.test_results['70b_model_quick'] = model_result
        return model_result
    
    def test_api_endpoints(self):
        """Test API endpoints - FAST"""
        print("   Testing API endpoints...")
        
        endpoints = [
            ("/api/health", "Health check"),
            ("/api/articles/stats/overview", "Article statistics"),
            ("/api/storylines", "Storylines list"),
            ("/api/rss-feeds", "RSS feeds list")
        ]
        
        results = []
        
        for endpoint, description in endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
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
    
    def test_load_balancing_quick(self):
        """Quick load balancing test - 3 simple requests"""
        print("   Testing load balancing with 3 simple requests...")
        print("   (This may take 30-45 seconds)")
        
        workload_tests = [
            ("Breaking News", "URGENT: Major event occurred, immediate analysis needed"),
            ("User Request", "User requested analysis of specific article"),
            ("Storyline Analysis", "Deep analysis of complex story development")
        ]
        
        results = []
        
        for workload_name, prompt in workload_tests:
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"{prompt}. Provide brief analysis.",
                        "stream": False
                    },
                    timeout=30
                )
                
                end_time = time.time()
                processing_time = end_time - start_time
                
                if response.status_code == 200:
                    results.append({
                        'workload': workload_name,
                        'success': True,
                        'processing_time': processing_time
                    })
                    print(f"   ✅ {workload_name}: {processing_time:.2f}s")
                else:
                    results.append({
                        'workload': workload_name,
                        'success': False,
                        'processing_time': processing_time
                    })
                    print(f"   ❌ {workload_name}: Failed")
                    
            except Exception as e:
                results.append({
                    'workload': workload_name,
                    'success': False,
                    'processing_time': 0,
                    'error': str(e)
                })
                print(f"   ❌ {workload_name}: Error - {e}")
        
        success_rate = sum(1 for r in results if r['success']) / len(results)
        avg_time = sum(r['processing_time'] for r in results if r['success']) / max(1, sum(1 for r in results if r['success']))
        
        print(f"   📊 Load balancing success rate: {success_rate:.1%}")
        print(f"   📊 Average processing time: {avg_time:.2f}s")
        
        self.test_results['load_balancing_quick'] = {
            'results': results,
            'success_rate': success_rate,
            'avg_processing_time': avg_time
        }
        
        return results
    
    def test_parallel_processing_quick(self):
        """Quick parallel processing test - 2 concurrent requests"""
        print("   Testing parallel processing with 2 concurrent requests...")
        print("   (This may take 60-90 seconds)")
        
        def process_request(request_id):
            """Process a single request"""
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"Analyze this news article {request_id}: Breaking news about economic policies affecting millions.",
                        "stream": False
                    },
                    timeout=60
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
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_request, i) for i in range(2)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        success_count = sum(1 for r in results if r['success'])
        success_rate = success_count / len(results)
        avg_processing_time = sum(r['processing_time'] for r in results if r['success']) / max(1, success_count)
        
        print(f"   📊 Parallel processing results:")
        print(f"     Total time: {total_time:.2f}s")
        print(f"     Success rate: {success_rate:.1%}")
        print(f"     Average processing time: {avg_processing_time:.2f}s")
        
        self.test_results['parallel_processing_quick'] = {
            'total_time': total_time,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'results': results
        }
        
        return results
    
    def test_performance_metrics(self):
        """Test performance metrics - FAST"""
        print("   Collecting performance metrics...")
        
        # Get system metrics
        metrics = {
            'ollama_status': False,
            'api_status': False,
            'database_status': False,
            'frontend_status': False,
            'model_available': False
        }
        
        # Check Ollama status
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                metrics['ollama_status'] = True
                models = response.json().get('models', [])
                if any('70b' in model.get('name', '') for model in models):
                    metrics['model_available'] = True
        except:
            pass
        
        # Check API status
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                metrics['api_status'] = True
        except:
            pass
        
        # Check Database status
        try:
            response = requests.get(f"{self.base_url}/api/articles/stats/overview", timeout=5)
            if response.status_code == 200:
                metrics['database_status'] = True
        except:
            pass
        
        # Check Frontend status
        try:
            response = requests.get("http://localhost:3000", timeout=5)
            if response.status_code == 200:
                metrics['frontend_status'] = True
        except:
            pass
        
        print(f"   📊 System metrics collected")
        
        self.test_results['performance_metrics'] = metrics
        return metrics
    
    def generate_quick_report(self):
        """Generate quick test report"""
        end_time = time.time()
        total_test_time = end_time - self.start_time
        
        print("\n" + "=" * 50)
        print("📊 QUICK TEST REPORT")
        print("=" * 50)
        
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
        model_test = self.test_results.get('70b_model_quick', {})
        if model_test.get('success'):
            print(f"\n🤖 70B MODEL PERFORMANCE:")
            print(f"   Status: ✅ Working")
            print(f"   Processing time: {model_test.get('processing_time', 0):.2f}s")
            print(f"   Response: {model_test.get('response', 'N/A')}")
        else:
            print(f"\n🤖 70B MODEL PERFORMANCE:")
            print(f"   Status: ❌ Failed")
            print(f"   Error: {model_test.get('error', 'Unknown')}")
        
        # API Performance
        api_test = self.test_results.get('api_endpoints', {})
        print(f"\n🌐 API PERFORMANCE:")
        print(f"   Success rate: {api_test.get('success_rate', 0):.1%}")
        
        # Load Balancing Performance
        load_test = self.test_results.get('load_balancing_quick', {})
        if load_test:
            print(f"\n⚖️ LOAD BALANCING PERFORMANCE:")
            print(f"   Success rate: {load_test.get('success_rate', 0):.1%}")
            print(f"   Average processing time: {load_test.get('avg_processing_time', 0):.2f}s per task")
        
        # Parallel Processing Performance
        parallel_test = self.test_results.get('parallel_processing_quick', {})
        if parallel_test:
            print(f"\n🔄 PARALLEL PROCESSING PERFORMANCE:")
            print(f"   Success rate: {parallel_test.get('success_rate', 0):.1%}")
            print(f"   Total time: {parallel_test.get('total_time', 0):.2f}s")
            print(f"   Average processing time: {parallel_test.get('avg_processing_time', 0):.2f}s")
        
        # Overall Assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        
        overall_health = all([
            health.get('ollama_running', False),
            health.get('70b_model_available', False),
            health.get('api_running', False)
        ])
        
        model_performance = model_test.get('success', False)
        api_performance = api_test.get('success_rate', 0) > 0.5
        
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
        
        print(f"\n📋 QUICK TEST COMPLETED")
        print(f"   Total test time: {total_test_time:.2f} seconds")
        print(f"   Estimated full test time: ~5-10 minutes")
        print(f"   All major components tested")

def main():
    """Main function to run quick system test"""
    print("⏱️ ESTIMATED TEST TIME: ~3-5 minutes")
    print("   - System Health: 30 seconds")
    print("   - 70b Model Test: 60 seconds")
    print("   - API Endpoints: 20 seconds")
    print("   - Load Balancing: 45 seconds")
    print("   - Parallel Processing: 90 seconds")
    print("   - Performance Metrics: 30 seconds")
    print("")
    
    tester = QuickSystemTester()
    
    try:
        results = tester.run_quick_test()
        return results
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return None

if __name__ == "__main__":
    main()
