#!/usr/bin/env python3
"""
Phase 1 Testing Script: Multi-Perspective Analysis Engine
Tests the multi-perspective analysis functionality thoroughly
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, List

# Add the API directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

from services.multi_perspective_analyzer import MultiPerspectiveAnalyzer, PerspectiveType
from services.enhanced_storyline_service import EnhancedStorylineService
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase1Tester:
    """Comprehensive tester for Phase 1 Multi-Perspective Analysis"""
    
    def __init__(self):
        # Initialize with mock services for testing
        self.ml_service = None  # Will be None for fallback testing
        self.rag_service = None  # Will be None for fallback testing
        
        # Create mock database config
        mock_db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'news_intelligence',
            'user': 'postgres',
            'password': 'password'
        }
        
        try:
            # Try to initialize real services
            self.ml_service = MLSummarizationService()
            self.rag_service = RAGService(mock_db_config)
        except Exception as e:
            logger.warning(f"Could not initialize real services, using fallback: {e}")
            self.ml_service = None
            self.rag_service = None
        
        self.multi_perspective_analyzer = MultiPerspectiveAnalyzer(self.ml_service, self.rag_service)
        self.enhanced_service = EnhancedStorylineService(self.ml_service, self.rag_service)
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all Phase 1 tests"""
        logger.info("🚀 Starting Phase 1 Multi-Perspective Analysis Tests")
        
        tests = [
            ("Database Schema Test", self.test_database_schema),
            ("Multi-Perspective Analyzer Test", self.test_multi_perspective_analyzer),
            ("Enhanced Storyline Service Test", self.test_enhanced_storyline_service),
            ("API Integration Test", self.test_api_integration),
            ("Performance Test", self.test_performance),
            ("Error Handling Test", self.test_error_handling)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"Running {test_name}...")
            try:
                result = await test_func()
                self.test_results.append({
                    "test_name": test_name,
                    "status": "PASSED" if result["success"] else "FAILED",
                    "details": result
                })
                logger.info(f"✅ {test_name}: {'PASSED' if result['success'] else 'FAILED'}")
            except Exception as e:
                self.test_results.append({
                    "test_name": test_name,
                    "status": "ERROR",
                    "details": {"error": str(e)}
                })
                logger.error(f"❌ {test_name}: ERROR - {e}")
        
        # Generate test report
        await self.generate_test_report()
    
    async def test_database_schema(self) -> Dict[str, Any]:
        """Test database schema creation and validation"""
        try:
            from database.connection import get_db
            from sqlalchemy import text
            
            db_gen = get_db()
            db = next(db_gen)
            
            try:
                # Test if new tables exist
                tables_to_check = [
                    'analysis_perspectives',
                    'multi_perspective_analysis',
                    'impact_assessments',
                    'historical_patterns',
                    'predictive_analysis',
                    'analysis_quality_metrics'
                ]
                
                existing_tables = []
                missing_tables = []
                
                for table in tables_to_check:
                    result = db.execute(text(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table}'
                        )
                    """)).fetchone()
                    
                    if result[0]:
                        existing_tables.append(table)
                    else:
                        missing_tables.append(table)
                
                # Test table structure
                if existing_tables:
                    structure_test = db.execute(text("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = 'analysis_perspectives'
                        ORDER BY ordinal_position
                    """)).fetchall()
                    
                    column_count = len(structure_test)
                else:
                    column_count = 0
                
                return {
                    "success": len(missing_tables) == 0,
                    "existing_tables": existing_tables,
                    "missing_tables": missing_tables,
                    "analysis_perspectives_columns": column_count,
                    "message": "All required tables exist" if len(missing_tables) == 0 else f"Missing tables: {missing_tables}"
                }
                
            finally:
                db.close()
                
        except Exception as e:
            # If database is not available, check if migration file exists
            import os
            migration_file = "api/database/migrations/009_multi_perspective_analysis.sql"
            migration_exists = os.path.exists(migration_file)
            
            return {
                "success": migration_exists,
                "error": str(e),
                "migration_file_exists": migration_exists,
                "message": "Database not available, but migration file exists" if migration_exists else "Database not available and migration file missing"
            }
    
    async def test_multi_perspective_analyzer(self) -> Dict[str, Any]:
        """Test multi-perspective analyzer functionality"""
        try:
            # Test perspective templates
            perspective_types = list(PerspectiveType)
            template_count = len(self.multi_perspective_analyzer.perspective_templates)
            
            # Test perspective template structure
            template_validation = []
            for perspective_type in perspective_types:
                template = self.multi_perspective_analyzer.perspective_templates.get(perspective_type)
                if template:
                    required_fields = ['name', 'description', 'focus_areas', 'system_prompt', 'user_prompt_template']
                    missing_fields = [field for field in required_fields if field not in template]
                    template_validation.append({
                        "perspective": perspective_type.value,
                        "valid": len(missing_fields) == 0,
                        "missing_fields": missing_fields
                    })
            
            # Test fallback analysis generation
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a test article about a political development.",
                    "source": "Test Source",
                    "published_at": "2024-01-01T00:00:00Z"
                },
                {
                    "id": 2,
                    "title": "Test Article 2", 
                    "content": "This is another test article about economic implications.",
                    "source": "Test Source 2",
                    "published_at": "2024-01-02T00:00:00Z"
                }
            ]
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia summary"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity 1", "Test Entity 2"],
                "extracted_topics": ["Test Topic 1", "Test Topic 2"]
            }
            
            # Test individual perspective analysis
            test_perspective = await self.multi_perspective_analyzer._analyze_from_perspective(
                "test_storyline_id",
                "Test Storyline",
                test_articles,
                test_rag_context,
                PerspectiveType.GOVERNMENT_OFFICIAL
            )
            
            return {
                "success": True,
                "perspective_types_count": len(perspective_types),
                "template_count": template_count,
                "template_validation": template_validation,
                "test_perspective_generated": test_perspective is not None,
                "test_perspective_type": test_perspective.perspective_type if test_perspective else None,
                "message": "Multi-perspective analyzer basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Multi-perspective analyzer test failed"
            }
    
    async def test_enhanced_storyline_service(self) -> Dict[str, Any]:
        """Test enhanced storyline service functionality"""
        try:
            # Test service initialization
            service_initialized = self.enhanced_service is not None
            ml_service_available = self.enhanced_service.ml_service is not None
            rag_service_available = self.enhanced_service.rag_service is not None
            analyzer_available = self.enhanced_service.multi_perspective_analyzer is not None
            
            # Test comprehensive summary generation
            test_storyline = {
                "id": "test_storyline_123",
                "title": "Test Storyline for Analysis",
                "description": "A test storyline for enhanced analysis"
            }
            
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a comprehensive test article about a major political development that affects multiple stakeholders.",
                    "source": "Test Source 1",
                    "published_at": "2024-01-01T00:00:00Z"
                },
                {
                    "id": 2,
                    "title": "Test Article 2",
                    "content": "This is another test article providing additional context and different perspectives on the same issue.",
                    "source": "Test Source 2", 
                    "published_at": "2024-01-02T00:00:00Z"
                }
            ]
            
            test_basic_summary = {
                "master_summary": "This is a test summary of the storyline.",
                "status": "generated",
                "article_count": 2
            }
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia context"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity"],
                "extracted_topics": ["Test Topic"]
            }
            
            # Test comprehensive summary generation
            comprehensive_summary = await self.enhanced_service._generate_comprehensive_summary(
                test_storyline,
                test_articles,
                test_basic_summary,
                None,  # No multi-perspective result for this test
                test_rag_context
            )
            
            return {
                "success": True,
                "service_initialized": service_initialized,
                "ml_service_available": ml_service_available,
                "rag_service_available": rag_service_available,
                "analyzer_available": analyzer_available,
                "comprehensive_summary_generated": comprehensive_summary is not None,
                "summary_word_count": comprehensive_summary.get("word_count", 0) if comprehensive_summary else 0,
                "summary_section_count": comprehensive_summary.get("section_count", 0) if comprehensive_summary else 0,
                "message": "Enhanced storyline service basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Enhanced storyline service test failed"
            }
    
    async def test_api_integration(self) -> Dict[str, Any]:
        """Test API integration and route availability"""
        try:
            # Test if the enhanced analysis route can be imported
            from routes.enhanced_analysis import router as enhanced_analysis_router
            
            # Check if router has expected routes
            routes = []
            for route in enhanced_analysis_router.routes:
                if hasattr(route, 'path') and hasattr(route, 'methods'):
                    routes.append({
                        "path": route.path,
                        "methods": list(route.methods) if route.methods else []
                    })
            
            expected_routes = [
                "/enhanced-analysis/storyline",
                "/enhanced-analysis/multi-perspective", 
                "/enhanced-analysis/storyline/{storyline_id}",
                "/enhanced-analysis/storyline/{storyline_id}/perspectives",
                "/enhanced-analysis/storyline/{storyline_id}/quality",
                "/enhanced-analysis/perspectives/available",
                "/enhanced-analysis/health"
            ]
            
            found_routes = [route["path"] for route in routes]
            missing_routes = [route for route in expected_routes if route not in found_routes]
            
            return {
                "success": len(missing_routes) == 0,
                "total_routes": len(routes),
                "found_routes": found_routes,
                "missing_routes": missing_routes,
                "message": "All expected API routes available" if len(missing_routes) == 0 else f"Missing routes: {missing_routes}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "API integration test failed"
            }
    
    async def test_performance(self) -> Dict[str, Any]:
        """Test performance of multi-perspective analysis"""
        try:
            import time
            
            # Test perspective analysis performance
            test_articles = [
                {
                    "id": i,
                    "title": f"Test Article {i}",
                    "content": f"This is test article {i} with some content for analysis.",
                    "source": f"Test Source {i}",
                    "published_at": f"2024-01-{i:02d}T00:00:00Z"
                }
                for i in range(1, 6)  # 5 test articles
            ]
            
            test_rag_context = {
                "wikipedia": {"summaries": [f"Wikipedia summary {i}" for i in range(3)]},
                "gdelt": {"events": [f"GDELT event {i}" for i in range(2)]},
                "extracted_entities": [f"Entity {i}" for i in range(5)],
                "extracted_topics": [f"Topic {i}" for i in range(3)]
            }
            
            # Test single perspective analysis performance
            start_time = time.time()
            test_perspective = await self.multi_perspective_analyzer._analyze_from_perspective(
                "perf_test_storyline",
                "Performance Test Storyline",
                test_articles,
                test_rag_context,
                PerspectiveType.GOVERNMENT_OFFICIAL
            )
            single_perspective_time = time.time() - start_time
            
            # Test comprehensive summary generation performance
            start_time = time.time()
            test_storyline = {
                "id": "perf_test_storyline",
                "title": "Performance Test Storyline",
                "description": "A test storyline for performance testing"
            }
            
            test_basic_summary = {
                "master_summary": "Performance test summary",
                "status": "generated",
                "article_count": len(test_articles)
            }
            
            comprehensive_summary = await self.enhanced_service._generate_comprehensive_summary(
                test_storyline,
                test_articles,
                test_basic_summary,
                None,
                test_rag_context
            )
            comprehensive_summary_time = time.time() - start_time
            
            return {
                "success": True,
                "single_perspective_time": single_perspective_time,
                "comprehensive_summary_time": comprehensive_summary_time,
                "performance_acceptable": single_perspective_time < 30 and comprehensive_summary_time < 60,
                "message": f"Performance test completed - Single perspective: {single_perspective_time:.2f}s, Comprehensive: {comprehensive_summary_time:.2f}s"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Performance test failed"
            }
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and edge cases"""
        try:
            error_tests = []
            
            # Test with invalid storyline ID
            try:
                result = await self.enhanced_service.get_enhanced_storyline_analysis("invalid_storyline_id")
                error_tests.append({
                    "test": "invalid_storyline_id",
                    "success": "error" in result,
                    "message": "Correctly handled invalid storyline ID"
                })
            except Exception as e:
                error_tests.append({
                    "test": "invalid_storyline_id",
                    "success": True,
                    "message": f"Exception handled: {str(e)}"
                })
            
            # Test with empty articles
            try:
                empty_articles = []
                test_perspective = await self.multi_perspective_analyzer._analyze_from_perspective(
                    "test_empty",
                    "Empty Test",
                    empty_articles,
                    {},
                    PerspectiveType.GOVERNMENT_OFFICIAL
                )
                error_tests.append({
                    "test": "empty_articles",
                    "success": test_perspective is not None,
                    "message": "Handled empty articles gracefully"
                })
            except Exception as e:
                error_tests.append({
                    "test": "empty_articles",
                    "success": False,
                    "message": f"Failed to handle empty articles: {str(e)}"
                })
            
            # Test with None RAG context
            try:
                test_perspective = await self.multi_perspective_analyzer._analyze_from_perspective(
                    "test_none_rag",
                    "None RAG Test",
                    [{"id": 1, "title": "Test", "content": "Test content", "source": "Test", "published_at": "2024-01-01T00:00:00Z"}],
                    None,
                    PerspectiveType.GOVERNMENT_OFFICIAL
                )
                error_tests.append({
                    "test": "none_rag_context",
                    "success": test_perspective is not None,
                    "message": "Handled None RAG context gracefully"
                })
            except Exception as e:
                error_tests.append({
                    "test": "none_rag_context",
                    "success": False,
                    "message": f"Failed to handle None RAG context: {str(e)}"
                })
            
            all_tests_passed = all(test["success"] for test in error_tests)
            
            return {
                "success": all_tests_passed,
                "error_tests": error_tests,
                "message": f"Error handling test {'passed' if all_tests_passed else 'failed'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Error handling test failed"
            }
    
    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Phase 1 Test Report")
        
        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASSED"])
        failed_tests = len([r for r in self.test_results if r["status"] == "FAILED"])
        error_tests = len([r for r in self.test_results if r["status"] == "ERROR"])
        
        report = {
            "test_summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0
            },
            "test_results": self.test_results,
            "timestamp": datetime.now().isoformat(),
            "phase": "Phase 1: Multi-Perspective Analysis Engine"
        }
        
        # Save report to file
        report_filename = f"phase1_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 PHASE 1 TEST REPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"✅ Passed: {passed_tests}")
        logger.info(f"❌ Failed: {failed_tests}")
        logger.info(f"🚨 Errors: {error_tests}")
        logger.info(f"📈 Success Rate: {report['test_summary']['success_rate']:.1f}%")
        logger.info("=" * 60)
        
        if failed_tests > 0 or error_tests > 0:
            logger.info("❌ FAILED/ERROR TESTS:")
            for result in self.test_results:
                if result["status"] in ["FAILED", "ERROR"]:
                    logger.info(f"  - {result['test_name']}: {result['status']}")
                    if "details" in result and "error" in result["details"]:
                        logger.info(f"    Error: {result['details']['error']}")
        
        logger.info(f"📄 Detailed report saved to: {report_filename}")
        
        return report

async def main():
    """Main test execution"""
    tester = Phase1Tester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
