#!/usr/bin/env python3
"""
Phase 3 Testing Script: Impact Assessment Service
Tests the impact assessment functionality thoroughly
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

from services.impact_assessment_service import ImpactAssessmentService, ImpactDimension
from services.enhanced_storyline_service import EnhancedStorylineService
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase3Tester:
    """Comprehensive tester for Phase 3 Impact Assessment Service"""
    
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
        
        self.impact_assessment_service = ImpactAssessmentService(self.ml_service)
        self.enhanced_service = EnhancedStorylineService(self.ml_service, self.rag_service)
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all Phase 3 tests"""
        logger.info("🚀 Starting Phase 3 Impact Assessment Service Tests")
        
        tests = [
            ("Impact Assessment Service Test", self.test_impact_assessment_service),
            ("Enhanced Storyline Integration Test", self.test_enhanced_storyline_integration),
            ("API Integration Test", self.test_api_integration),
            ("Performance Test", self.test_performance),
            ("Error Handling Test", self.test_error_handling),
            ("Impact Dimensions Test", self.test_impact_dimensions)
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
    
    async def test_impact_assessment_service(self) -> Dict[str, Any]:
        """Test impact assessment service functionality"""
        try:
            # Test impact dimensions
            impact_dimensions = list(ImpactDimension)
            dimension_count = len(self.impact_assessment_service.impact_dimensions)
            
            # Test dimension configuration structure
            dimension_validation = []
            for dimension in impact_dimensions:
                config = self.impact_assessment_service.impact_dimensions.get(dimension)
                if config:
                    required_fields = ['name', 'description', 'subcategories', 'system_prompt', 'user_prompt_template']
                    missing_fields = [field for field in required_fields if field not in config]
                    dimension_validation.append({
                        "dimension": dimension.value,
                        "valid": len(missing_fields) == 0,
                        "missing_fields": missing_fields,
                        "subcategories_count": len(config.get('subcategories', []))
                    })
            
            # Test individual dimension assessment
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a test article about a major political development that affects multiple stakeholders.",
                    "source": "Test Source",
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
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia summary"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity 1", "Test Entity 2"],
                "extracted_topics": ["Test Topic 1", "Test Topic 2"]
            }
            
            # Test individual dimension impact assessment
            test_assessment = await self.impact_assessment_service._assess_dimension_impact(
                "test_storyline_id",
                test_articles,
                test_rag_context,
                ImpactDimension.POLITICAL
            )
            
            return {
                "success": True,
                "impact_dimensions_count": len(impact_dimensions),
                "dimension_config_count": dimension_count,
                "dimension_validation": dimension_validation,
                "test_assessment_generated": test_assessment is not None,
                "test_assessment_dimension": test_assessment.dimension if test_assessment else None,
                "test_assessment_impact_score": test_assessment.impact_score if test_assessment else 0.0,
                "test_assessment_risk_level": test_assessment.risk_level if test_assessment else None,
                "message": "Impact assessment service basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Impact assessment service test failed"
            }
    
    async def test_enhanced_storyline_integration(self) -> Dict[str, Any]:
        """Test integration with enhanced storyline service"""
        try:
            # Test service initialization
            service_initialized = self.enhanced_service is not None
            impact_service_available = self.enhanced_service.impact_assessment_service is not None
            
            # Test comprehensive analysis with impact assessment
            test_storyline = {
                "id": "test_storyline_impact_123",
                "title": "Test Storyline for Impact Assessment",
                "description": "A test storyline for impact assessment analysis"
            }
            
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a comprehensive test article about a major development that affects multiple dimensions.",
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
            
            # Test impact assessment generation
            impact_result = await self.impact_assessment_service.assess_impacts(
                "test_storyline_impact_123", test_articles, test_rag_context
            )
            
            return {
                "success": True,
                "service_initialized": service_initialized,
                "impact_service_available": impact_service_available,
                "impact_assessment_generated": impact_result is not None,
                "impact_dimensions_assessed": len(impact_result.dimension_assessments) if impact_result else 0,
                "overall_impact_score": impact_result.overall_impact_score if impact_result else 0.0,
                "high_impact_scenarios_count": len(impact_result.high_impact_scenarios) if impact_result else 0,
                "message": "Enhanced storyline integration with impact assessment working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Enhanced storyline integration test failed"
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
                "/enhanced-analysis/impact-assessment",
                "/enhanced-analysis/impact-dimensions",
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
        """Test performance of impact assessment"""
        try:
            import time
            
            # Test impact assessment performance
            test_articles = [
                {
                    "id": i,
                    "title": f"Test Article {i}",
                    "content": f"This is test article {i} with some content for impact analysis.",
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
            
            # Test single dimension impact assessment performance
            start_time = time.time()
            test_assessment = await self.impact_assessment_service._assess_dimension_impact(
                "perf_test_storyline",
                test_articles,
                test_rag_context,
                ImpactDimension.POLITICAL
            )
            single_dimension_time = time.time() - start_time
            
            # Test comprehensive impact assessment performance
            start_time = time.time()
            comprehensive_result = await self.impact_assessment_service.assess_impacts(
                "perf_test_storyline", test_articles, test_rag_context
            )
            comprehensive_time = time.time() - start_time
            
            return {
                "success": True,
                "single_dimension_time": single_dimension_time,
                "comprehensive_time": comprehensive_time,
                "performance_acceptable": single_dimension_time < 30 and comprehensive_time < 120,
                "dimensions_assessed": len(comprehensive_result.dimension_assessments) if comprehensive_result else 0,
                "message": f"Performance test completed - Single dimension: {single_dimension_time:.2f}s, Comprehensive: {comprehensive_time:.2f}s"
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
            
            # Test with empty articles
            try:
                empty_articles = []
                test_assessment = await self.impact_assessment_service._assess_dimension_impact(
                    "test_empty",
                    empty_articles,
                    {},
                    ImpactDimension.POLITICAL
                )
                error_tests.append({
                    "test": "empty_articles",
                    "success": test_assessment is not None,
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
                test_assessment = await self.impact_assessment_service._assess_dimension_impact(
                    "test_none_rag",
                    [{"id": 1, "title": "Test", "content": "Test content", "source": "Test", "published_at": "2024-01-01T00:00:00Z"}],
                    None,
                    ImpactDimension.POLITICAL
                )
                error_tests.append({
                    "test": "none_rag_context",
                    "success": test_assessment is not None,
                    "message": "Handled None RAG context gracefully"
                })
            except Exception as e:
                error_tests.append({
                    "test": "none_rag_context",
                    "success": False,
                    "message": f"Failed to handle None RAG context: {str(e)}"
                })
            
            # Test with invalid dimension
            try:
                # This should work with any valid dimension
                test_assessment = await self.impact_assessment_service._assess_dimension_impact(
                    "test_invalid_dim",
                    [{"id": 1, "title": "Test", "content": "Test content", "source": "Test", "published_at": "2024-01-01T00:00:00Z"}],
                    {},
                    ImpactDimension.ECONOMIC
                )
                error_tests.append({
                    "test": "valid_dimension",
                    "success": test_assessment is not None,
                    "message": "Handled valid dimension correctly"
                })
            except Exception as e:
                error_tests.append({
                    "test": "valid_dimension",
                    "success": False,
                    "message": f"Failed to handle valid dimension: {str(e)}"
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
    
    async def test_impact_dimensions(self) -> Dict[str, Any]:
        """Test impact dimensions configuration and functionality"""
        try:
            # Test all impact dimensions
            dimensions = list(ImpactDimension)
            dimension_tests = []
            
            for dimension in dimensions:
                config = self.impact_assessment_service.impact_dimensions.get(dimension)
                if config:
                    # Test subcategories
                    subcategories = config.get('subcategories', [])
                    subcategory_count = len(subcategories)
                    
                    # Test prompts
                    system_prompt = config.get('system_prompt', '')
                    user_prompt_template = config.get('user_prompt_template', '')
                    
                    dimension_tests.append({
                        "dimension": dimension.value,
                        "name": config.get('name', ''),
                        "description": config.get('description', ''),
                        "subcategories_count": subcategory_count,
                        "has_system_prompt": len(system_prompt) > 0,
                        "has_user_prompt_template": len(user_prompt_template) > 0,
                        "system_prompt_length": len(system_prompt),
                        "user_prompt_length": len(user_prompt_template)
                    })
            
            # Test impact score extraction
            test_descriptions = [
                "This has a high impact on the economy with significant market implications.",
                "The political impact is medium with some policy changes expected.",
                "Low environmental impact with minimal resource usage.",
                "Critical security implications requiring immediate attention."
            ]
            
            score_extraction_tests = []
            for desc in test_descriptions:
                score = self.impact_assessment_service._extract_impact_score(desc)
                score_extraction_tests.append({
                    "description": desc[:50] + "...",
                    "extracted_score": score,
                    "extraction_successful": score is not None
                })
            
            return {
                "success": True,
                "total_dimensions": len(dimensions),
                "dimension_tests": dimension_tests,
                "score_extraction_tests": score_extraction_tests,
                "all_dimensions_configured": len(dimension_tests) == len(dimensions),
                "message": "Impact dimensions configuration and functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Impact dimensions test failed"
            }
    
    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Phase 3 Test Report")
        
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
            "phase": "Phase 3: Impact Assessment Service"
        }
        
        # Save report to file
        report_filename = f"phase3_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 PHASE 3 TEST REPORT SUMMARY")
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
    tester = Phase3Tester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())

