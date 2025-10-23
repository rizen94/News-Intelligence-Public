#!/usr/bin/env python3
"""
Comprehensive test runner for News Intelligence System v4.0
Runs all tests with detailed reporting and analysis
"""

import pytest
import sys
import os
import json
import time
from datetime import datetime
from pathlib import Path

class TestRunner:
    """Comprehensive test runner with detailed reporting"""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = {
            "start_time": datetime.now().isoformat(),
            "test_suites": {},
            "summary": {}
        }
    
    def run_test_suite(self, suite_name, test_path, description):
        """Run a specific test suite"""
        print(f"\n🚀 Running {suite_name} Tests")
        print("=" * 50)
        print(f"Description: {description}")
        print(f"Path: {test_path}")
        
        start_time = time.time()
        
        # Run pytest with detailed output
        result = pytest.main([
            str(test_path),
            "-v",  # Verbose output
            "--tb=short",  # Short traceback format
            "--durations=10",  # Show 10 slowest tests
            "--junitxml", str(self.test_dir / f"results_{suite_name.lower()}.xml")
        ])
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Store results
        self.results["test_suites"][suite_name] = {
            "path": str(test_path),
            "description": description,
            "duration": duration,
            "exit_code": result,
            "status": "PASSED" if result == 0 else "FAILED"
        }
        
        status_emoji = "✅" if result == 0 else "❌"
        print(f"\n{status_emoji} {suite_name} Tests: {'PASSED' if result == 0 else 'FAILED'}")
        print(f"⏱️ Duration: {duration:.2f} seconds")
        
        return result == 0
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 COMPREHENSIVE TEST SUITE RUNNER")
        print("=" * 60)
        print("News Intelligence System v4.0 - Full Test Suite")
        print(f"Started at: {self.results['start_time']}")
        
        # Define test suites
        test_suites = [
            ("Unit", self.test_dir / "unit", "Individual component tests"),
            ("Integration", self.test_dir / "integration", "Component integration tests"),
            ("End-to-End", self.test_dir / "e2e", "Complete workflow tests"),
        ]
        
        passed_suites = 0
        total_suites = len(test_suites)
        
        for suite_name, suite_path, description in test_suites:
            if suite_path.exists():
                if self.run_test_suite(suite_name, suite_path, description):
                    passed_suites += 1
            else:
                print(f"⚠️ {suite_name} test directory not found: {suite_path}")
        
        # Generate summary
        self.results["summary"] = {
            "total_suites": total_suites,
            "passed_suites": passed_suites,
            "failed_suites": total_suites - passed_suites,
            "success_rate": (passed_suites / total_suites) * 100 if total_suites > 0 else 0,
            "end_time": datetime.now().isoformat()
        }
        
        # Print final summary
        self.print_final_summary()
        
        # Save results
        self.save_results()
        
        return passed_suites == total_suites
    
    def print_final_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "=" * 60)
        print("📊 COMPREHENSIVE TEST RESULTS SUMMARY")
        print("=" * 60)
        
        summary = self.results["summary"]
        print(f"🎯 Overall Result: {summary['passed_suites']}/{summary['total_suites']} test suites passed")
        print(f"📈 Success Rate: {summary['success_rate']:.1f}%")
        print(f"⏱️ Total Duration: {self.calculate_total_duration():.2f} seconds")
        
        print(f"\n📋 Test Suite Results:")
        for suite_name, suite_data in self.results["test_suites"].items():
            status_emoji = "✅" if suite_data["status"] == "PASSED" else "❌"
            print(f"  {status_emoji} {suite_name}: {suite_data['status']} ({suite_data['duration']:.2f}s)")
        
        if summary["success_rate"] == 100:
            print(f"\n🎉 ALL TESTS PASSED! System is fully functional.")
        elif summary["success_rate"] >= 80:
            print(f"\n⚠️ Most tests passed. System is mostly functional with minor issues.")
        else:
            print(f"\n❌ Multiple test failures. System needs significant attention.")
    
    def calculate_total_duration(self):
        """Calculate total test duration"""
        total = 0
        for suite_data in self.results["test_suites"].values():
            total += suite_data["duration"]
        return total
    
    def save_results(self):
        """Save test results to file"""
        results_file = self.test_dir / "test_results.json"
        with open(results_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n💾 Test results saved to: {results_file}")
    
    def run_specific_tests(self, test_pattern):
        """Run specific tests matching a pattern"""
        print(f"🔍 Running tests matching: {test_pattern}")
        
        result = pytest.main([
            str(self.test_dir),
            "-k", test_pattern,
            "-v",
            "--tb=short"
        ])
        
        return result == 0

def main():
    """Main test runner entry point"""
    runner = TestRunner()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print("Usage:")
            print("  python run_tests.py                    # Run all tests")
            print("  python run_tests.py --pattern <pattern> # Run specific tests")
            print("  python run_tests.py --help             # Show this help")
            return
        
        if sys.argv[1] == "--pattern" and len(sys.argv) > 2:
            success = runner.run_specific_tests(sys.argv[2])
        else:
            print("Invalid arguments. Use --help for usage information.")
            return
    else:
        success = runner.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
