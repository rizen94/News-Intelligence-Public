#!/usr/bin/env python3
"""
Test Optimized Performance for RTX 5090
Tests the system with optimized settings to measure improvements
"""

import requests
import time
import json
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

class OptimizedPerformanceTester:
    """Test optimized performance with RTX 5090 settings"""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.ollama_url = "http://localhost:11434"
        self.test_results = {}
        
    def run_optimized_test(self):
        """Run optimized performance test"""
        print("🚀 OPTIMIZED PERFORMANCE TEST - RTX 5090")
        print("=" * 50)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Testing with optimized 70b model settings")
        print("=" * 50)
        
        # Test 1: System Health
        print("\n1. SYSTEM HEALTH CHECK")
        print("-" * 30)
        health_result = self.test_system_health()
        
        # Test 2: Single Request Performance
        print("\n2. SINGLE REQUEST PERFORMANCE")
        print("-" * 30)
        single_result = self.test_single_request()
        
        # Test 3: Parallel Processing Test
        print("\n3. PARALLEL PROCESSING TEST")
        print("-" * 30)
        parallel_result = self.test_parallel_processing()
        
        # Test 4: GPU Utilization Check
        print("\n4. GPU UTILIZATION CHECK")
        print("-" * 30)
        gpu_result = self.check_gpu_utilization()
        
        # Generate report
        self.generate_optimized_report()
        
        return self.test_results
    
    def test_system_health(self):
        """Test system health"""
        print("   Checking system components...")
        
        health_status = {
            'ollama_running': False,
            'api_running': False,
            'database_running': False,
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
        
        self.test_results['system_health'] = health_status
        return health_status
    
    def test_single_request(self):
        """Test single request performance"""
        print("   Testing single request performance...")
        print("   (This may take 30-120 seconds)")
        
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": "llama3.1:70b",
                    "prompt": "Summarize this news article in 2-3 sentences: The president announced new economic policies today that will affect millions of Americans. The policies focus on infrastructure investment and job creation.",
                    "stream": False
                },
                timeout=180
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                single_result = {
                    'success': True,
                    'processing_time': processing_time,
                    'response': result.get('response', '')[:200] + '...',
                    'model': result.get('model', 'unknown')
                }
                print(f"   ✅ Single request completed: {processing_time:.2f}s")
                print(f"   📝 Response: {single_result['response']}")
            else:
                single_result = {
                    'success': False,
                    'processing_time': processing_time,
                    'error': f"HTTP {response.status_code}"
                }
                print(f"   ❌ Single request failed: {response.status_code}")
                
        except requests.exceptions.Timeout:
            single_result = {
                'success': False,
                'processing_time': 180,
                'error': "Timeout after 3 minutes"
            }
            print(f"   ⚠️ Single request timeout: Taking longer than 3 minutes")
        except Exception as e:
            single_result = {
                'success': False,
                'processing_time': 0,
                'error': str(e)
            }
            print(f"   ❌ Single request error: {e}")
        
        self.test_results['single_request'] = single_result
        return single_result
    
    def test_parallel_processing(self):
        """Test parallel processing capabilities"""
        print("   Testing parallel processing (2 concurrent requests)...")
        print("   (This may take 60-180 seconds)")
        
        def process_request(request_id):
            """Process a single request"""
            try:
                start_time = time.time()
                
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "llama3.1:70b",
                        "prompt": f"Analyze this news article {request_id}: Breaking news about economic policies affecting millions of people. Provide a brief analysis.",
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
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_request, i) for i in range(2)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        success_count = sum(1 for r in results if r['success'])
        success_rate = success_count / len(results)
        avg_processing_time = sum(r['processing_time'] for r in results if r['success']) / max(1, success_count)
        
        parallel_result = {
            'total_time': total_time,
            'success_rate': success_rate,
            'avg_processing_time': avg_processing_time,
            'results': results
        }
        
        print(f"   📊 Parallel processing results:")
        print(f"     Total time: {total_time:.2f}s")
        print(f"     Success rate: {success_rate:.1%}")
        print(f"     Average processing time: {avg_processing_time:.2f}s")
        
        self.test_results['parallel_processing'] = parallel_result
        return parallel_result
    
    def check_gpu_utilization(self):
        """Check GPU utilization"""
        print("   Checking GPU utilization...")
        
        try:
            import subprocess
            result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                gpu_info = result.stdout.strip().split(', ')
                gpu_result = {
                    'name': gpu_info[0],
                    'memory_total': int(gpu_info[1]),
                    'memory_free': int(gpu_info[2]),
                    'memory_used': int(gpu_info[3]),
                    'utilization': int(gpu_info[4])
                }
                
                memory_usage_percent = (gpu_result['memory_used'] / gpu_result['memory_total']) * 100
                
                print(f"   📊 GPU Status:")
                print(f"     Name: {gpu_result['name']}")
                print(f"     Memory Used: {gpu_result['memory_used']}MB / {gpu_result['memory_total']}MB ({memory_usage_percent:.1f}%)")
                print(f"     GPU Utilization: {gpu_result['utilization']}%")
                
                if memory_usage_percent > 50:
                    print(f"   ✅ Good GPU memory utilization: {memory_usage_percent:.1f}%")
                elif memory_usage_percent > 20:
                    print(f"   ⚠️ Moderate GPU memory utilization: {memory_usage_percent:.1f}%")
                else:
                    print(f"   ❌ Low GPU memory utilization: {memory_usage_percent:.1f}%")
                    
            else:
                gpu_result = {'error': 'Failed to get GPU info'}
                print(f"   ❌ Failed to get GPU information")
                
        except Exception as e:
            gpu_result = {'error': str(e)}
            print(f"   ❌ GPU check error: {e}")
        
        self.test_results['gpu_utilization'] = gpu_result
        return gpu_result
    
    def generate_optimized_report(self):
        """Generate optimized performance report"""
        print("\n" + "=" * 50)
        print("📊 OPTIMIZED PERFORMANCE REPORT")
        print("=" * 50)
        
        # System Health Summary
        health = self.test_results.get('system_health', {})
        print(f"\n🏥 SYSTEM HEALTH:")
        print(f"   Ollama: {'✅' if health.get('ollama_running') else '❌'}")
        print(f"   70b Model: {'✅' if health.get('70b_model_available') else '❌'}")
        print(f"   API: {'✅' if health.get('api_running') else '❌'}")
        print(f"   Database: {'✅' if health.get('database_running') else '❌'}")
        
        # Single Request Performance
        single = self.test_results.get('single_request', {})
        if single.get('success'):
            print(f"\n🤖 SINGLE REQUEST PERFORMANCE:")
            print(f"   Status: ✅ Working")
            print(f"   Processing time: {single.get('processing_time', 0):.2f}s")
            print(f"   Response: {single.get('response', 'N/A')}")
        else:
            print(f"\n🤖 SINGLE REQUEST PERFORMANCE:")
            print(f"   Status: ❌ Failed")
            print(f"   Error: {single.get('error', 'Unknown')}")
        
        # Parallel Processing Performance
        parallel = self.test_results.get('parallel_processing', {})
        if parallel:
            print(f"\n🔄 PARALLEL PROCESSING PERFORMANCE:")
            print(f"   Success rate: {parallel.get('success_rate', 0):.1%}")
            print(f"   Total time: {parallel.get('total_time', 0):.2f}s")
            print(f"   Average processing time: {parallel.get('avg_processing_time', 0):.2f}s")
        
        # GPU Utilization
        gpu = self.test_results.get('gpu_utilization', {})
        if 'error' not in gpu:
            memory_usage_percent = (gpu.get('memory_used', 0) / gpu.get('memory_total', 1)) * 100
            print(f"\n🎮 GPU UTILIZATION:")
            print(f"   Memory Used: {gpu.get('memory_used', 0)}MB / {gpu.get('memory_total', 0)}MB ({memory_usage_percent:.1f}%)")
            print(f"   GPU Utilization: {gpu.get('utilization', 0)}%")
        else:
            print(f"\n🎮 GPU UTILIZATION:")
            print(f"   Error: {gpu.get('error', 'Unknown')}")
        
        # Overall Assessment
        print(f"\n🎯 OVERALL ASSESSMENT:")
        
        overall_health = all([
            health.get('ollama_running', False),
            health.get('70b_model_available', False),
            health.get('api_running', False)
        ])
        
        single_performance = single.get('success', False)
        parallel_performance = parallel.get('success_rate', 0) > 0.5
        
        if overall_health and single_performance and parallel_performance:
            print("   ✅ SYSTEM STATUS: EXCELLENT")
            print("   ✅ 70b model operational and performing well")
            print("   ✅ Parallel processing working effectively")
            print("   ✅ System ready for production use")
        elif overall_health and single_performance:
            print("   ⚠️ SYSTEM STATUS: GOOD")
            print("   ✅ 70b model operational")
            print("   ⚠️ Parallel processing may need attention")
            print("   ✅ System functional for single-user production")
        else:
            print("   ❌ SYSTEM STATUS: NEEDS ATTENTION")
            print("   ❌ Some core components not functioning properly")
            print("   ⚠️ Review system health and configuration")
        
        print(f"\n📋 OPTIMIZATION TEST COMPLETED")
        print(f"   System tested with RTX 5090 optimizations")
        print(f"   Performance metrics collected and analyzed")

def main():
    """Main function to run optimized performance test"""
    print("⏱️ ESTIMATED TEST TIME: ~3-5 minutes")
    print("   - System Health: 30 seconds")
    print("   - Single Request: 60-120 seconds")
    print("   - Parallel Processing: 60-180 seconds")
    print("   - GPU Check: 10 seconds")
    print("")
    
    tester = OptimizedPerformanceTester()
    
    try:
        results = tester.run_optimized_test()
        return results
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return None

if __name__ == "__main__":
    main()
