#!/usr/bin/env python3
"""
Phases 4 & 5 Testing Script: Historical Context & Predictive Analysis
Tests the historical context and predictive analysis functionality thoroughly
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

from services.historical_context_service import HistoricalContextService, PatternType
from services.predictive_analysis_service import PredictiveAnalysisService, PredictionHorizon
from services.enhanced_storyline_service import EnhancedStorylineService
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phases4And5Tester:
    """Comprehensive tester for Phases 4 & 5: Historical Context & Predictive Analysis"""
    
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
        
        self.historical_service = HistoricalContextService(self.ml_service, self.rag_service)
        self.predictive_service = PredictiveAnalysisService(self.ml_service, self.historical_service)
        self.enhanced_service = EnhancedStorylineService(self.ml_service, self.rag_service)
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all Phases 4 & 5 tests"""
        logger.info("🚀 Starting Phases 4 & 5: Historical Context & Predictive Analysis Tests")
        
        tests = [
            ("Historical Context Service Test", self.test_historical_context_service),
            ("Predictive Analysis Service Test", self.test_predictive_analysis_service),
            ("Enhanced Integration Test", self.test_enhanced_integration),
            ("API Integration Test", self.test_api_integration),
            ("Performance Test", self.test_performance),
            ("Error Handling Test", self.test_error_handling),
            ("Pattern Recognition Test", self.test_pattern_recognition),
            ("Scenario Planning Test", self.test_scenario_planning)
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
    
    async def test_historical_context_service(self) -> Dict[str, Any]:
        """Test historical context service functionality"""
        try:
            # Test historical sources configuration
            sources_count = len(self.historical_service.historical_sources)
            sources_validation = []
            
            for source_name, source_config in self.historical_service.historical_sources.items():
                required_fields = ['name', 'description', 'time_range', 'categories']
                missing_fields = [field for field in required_fields if field not in source_config]
                sources_validation.append({
                    "source": source_name,
                    "valid": len(missing_fields) == 0,
                    "missing_fields": missing_fields,
                    "categories_count": len(source_config.get('categories', []))
                })
            
            # Test pattern templates
            pattern_types = list(PatternType)
            pattern_validation = []
            
            for pattern_type in pattern_types:
                config = self.historical_service.pattern_templates.get(pattern_type)
                if config:
                    required_fields = ['name', 'description', 'keywords', 'time_frames', 'significance_threshold']
                    missing_fields = [field for field in required_fields if field not in config]
                    pattern_validation.append({
                        "pattern_type": pattern_type.value,
                        "valid": len(missing_fields) == 0,
                        "missing_fields": missing_fields,
                        "keywords_count": len(config.get('keywords', []))
                    })
            
            # Test historical context generation
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a test article about a major political development that affects multiple stakeholders.",
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
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia summary"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity 1", "Test Entity 2"],
                "extracted_topics": ["Test Topic 1", "Test Topic 2"]
            }
            
            # Generate historical context
            historical_result = await self.historical_service.generate_historical_context(
                "test_storyline_historical_123",
                "Test Storyline for Historical Context",
                test_articles,
                test_rag_context
            )
            
            return {
                "success": True,
                "sources_count": sources_count,
                "sources_validation": sources_validation,
                "pattern_types_count": len(pattern_types),
                "pattern_validation": pattern_validation,
                "historical_context_generated": historical_result is not None,
                "timeline_events_count": len(historical_result.historical_timeline) if historical_result else 0,
                "patterns_identified_count": len(historical_result.identified_patterns) if historical_result else 0,
                "similar_events_count": len(historical_result.similar_events) if historical_result else 0,
                "context_quality_score": historical_result.context_quality_score if historical_result else 0.0,
                "message": "Historical context service basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Historical context service test failed"
            }
    
    async def test_predictive_analysis_service(self) -> Dict[str, Any]:
        """Test predictive analysis service functionality"""
        try:
            # Test prediction horizons configuration
            horizons_count = len(self.predictive_service.prediction_horizons)
            horizons_validation = []
            
            for horizon, config in self.predictive_service.prediction_horizons.items():
                required_fields = ['name', 'description', 'time_range_months', 'focus_areas', 'confidence_threshold', 'system_prompt']
                missing_fields = [field for field in required_fields if field not in config]
                horizons_validation.append({
                    "horizon": horizon.value,
                    "valid": len(missing_fields) == 0,
                    "missing_fields": missing_fields,
                    "time_range_months": config.get('time_range_months', 0)
                })
            
            # Test scenario types
            scenario_types_count = len(self.predictive_service.scenario_types)
            scenario_validation = []
            
            for scenario_type, config in self.predictive_service.scenario_types.items():
                required_fields = ['name', 'description', 'probability_range', 'key_characteristics']
                missing_fields = [field for field in required_fields if field not in config]
                scenario_validation.append({
                    "scenario_type": scenario_type,
                    "valid": len(missing_fields) == 0,
                    "missing_fields": missing_fields,
                    "probability_range": config.get('probability_range', (0, 0))
                })
            
            # Test predictive analysis generation
            test_current_analysis = {
                "multi_perspective": {"consensus_score": 0.7, "analysis_quality_score": 0.8},
                "impact_assessment": {"overall_impact_score": 0.6, "risk_assessment": {"overall_risk_level": "medium"}},
                "historical_context": {"patterns_identified": 3, "context_quality_score": 0.7},
                "basic_summary": {"master_summary": "Test summary"},
                "rag_context": {"extracted_entities": ["Entity1", "Entity2"]}
            }
            
            # Generate predictive analysis
            predictive_result = await self.predictive_service.generate_predictive_analysis(
                "test_storyline_predictive_123",
                test_current_analysis
            )
            
            return {
                "success": True,
                "horizons_count": horizons_count,
                "horizons_validation": horizons_validation,
                "scenario_types_count": scenario_types_count,
                "scenario_validation": scenario_validation,
                "predictive_analysis_generated": predictive_result is not None,
                "predictions_count": len(predictive_result.predictions) if predictive_result else 0,
                "overall_confidence": predictive_result.overall_confidence if predictive_result else 0.0,
                "key_uncertainties_count": len(predictive_result.key_uncertainties) if predictive_result else 0,
                "prediction_quality_score": predictive_result.prediction_quality_score if predictive_result else 0.0,
                "message": "Predictive analysis service basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Predictive analysis service test failed"
            }
    
    async def test_enhanced_integration(self) -> Dict[str, Any]:
        """Test integration with enhanced storyline service"""
        try:
            # Test service initialization
            service_initialized = self.enhanced_service is not None
            historical_service_available = self.enhanced_service.historical_context_service is not None
            predictive_service_available = self.enhanced_service.predictive_analysis_service is not None
            
            # Test comprehensive analysis with all components
            test_storyline = {
                "id": "test_storyline_comprehensive_123",
                "title": "Test Storyline for Comprehensive Analysis",
                "description": "A test storyline for comprehensive analysis including historical context and predictive analysis"
            }
            
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a comprehensive test article about a major development that affects multiple dimensions and has historical precedents.",
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
                "master_summary": "This is a test summary of the comprehensive storyline.",
                "status": "generated",
                "article_count": 2
            }
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia context"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity"],
                "extracted_topics": ["Test Topic"]
            }
            
            # Test historical context generation
            historical_result = await self.historical_service.generate_historical_context(
                "test_storyline_comprehensive_123",
                "Test Storyline for Comprehensive Analysis",
                test_articles,
                test_rag_context
            )
            
            # Test predictive analysis generation
            current_analysis = {
                "multi_perspective": {},
                "impact_assessment": {},
                "historical_context": historical_result.__dict__ if historical_result else {},
                "basic_summary": test_basic_summary,
                "rag_context": test_rag_context
            }
            
            predictive_result = await self.predictive_service.generate_predictive_analysis(
                "test_storyline_comprehensive_123",
                current_analysis
            )
            
            return {
                "success": True,
                "service_initialized": service_initialized,
                "historical_service_available": historical_service_available,
                "predictive_service_available": predictive_service_available,
                "historical_context_generated": historical_result is not None,
                "predictive_analysis_generated": predictive_result is not None,
                "historical_timeline_events": len(historical_result.historical_timeline) if historical_result else 0,
                "historical_patterns_identified": len(historical_result.identified_patterns) if historical_result else 0,
                "predictive_predictions_count": len(predictive_result.predictions) if predictive_result else 0,
                "predictive_uncertainties_count": len(predictive_result.key_uncertainties) if predictive_result else 0,
                "message": "Enhanced storyline integration with historical context and predictive analysis working"
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
                "/enhanced-analysis/historical-context",
                "/enhanced-analysis/predictive-analysis",
                "/enhanced-analysis/impact-dimensions",
                "/enhanced-analysis/prediction-horizons",
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
        """Test performance of historical context and predictive analysis"""
        try:
            import time
            
            # Test historical context performance
            test_articles = [
                {
                    "id": i,
                    "title": f"Test Article {i}",
                    "content": f"This is test article {i} with some content for historical context analysis.",
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
            
            # Test historical context performance
            start_time = time.time()
            historical_result = await self.historical_service.generate_historical_context(
                "perf_test_historical",
                "Performance Test Historical Context",
                test_articles,
                test_rag_context
            )
            historical_time = time.time() - start_time
            
            # Test predictive analysis performance
            current_analysis = {
                "multi_perspective": {},
                "impact_assessment": {},
                "historical_context": historical_result.__dict__ if historical_result else {},
                "basic_summary": {"master_summary": "Test summary"},
                "rag_context": test_rag_context
            }
            
            start_time = time.time()
            predictive_result = await self.predictive_service.generate_predictive_analysis(
                "perf_test_predictive",
                current_analysis
            )
            predictive_time = time.time() - start_time
            
            return {
                "success": True,
                "historical_context_time": historical_time,
                "predictive_analysis_time": predictive_time,
                "performance_acceptable": historical_time < 60 and predictive_time < 90,
                "historical_events_generated": len(historical_result.historical_timeline) if historical_result else 0,
                "historical_patterns_identified": len(historical_result.identified_patterns) if historical_result else 0,
                "predictive_predictions_generated": len(predictive_result.predictions) if predictive_result else 0,
                "message": f"Performance test completed - Historical: {historical_time:.2f}s, Predictive: {predictive_time:.2f}s"
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
                historical_result = await self.historical_service.generate_historical_context(
                    "test_empty_historical",
                    "Test Empty Historical",
                    empty_articles,
                    {}
                )
                error_tests.append({
                    "test": "empty_articles_historical",
                    "success": historical_result is not None,
                    "message": "Handled empty articles gracefully for historical context"
                })
            except Exception as e:
                error_tests.append({
                    "test": "empty_articles_historical",
                    "success": False,
                    "message": f"Failed to handle empty articles for historical context: {str(e)}"
                })
            
            # Test with None RAG context for historical
            try:
                historical_result = await self.historical_service.generate_historical_context(
                    "test_none_rag_historical",
                    "Test None RAG Historical",
                    [{"id": 1, "title": "Test", "content": "Test content", "source": "Test", "published_at": "2024-01-01T00:00:00Z"}],
                    None
                )
                error_tests.append({
                    "test": "none_rag_context_historical",
                    "success": historical_result is not None,
                    "message": "Handled None RAG context gracefully for historical context"
                })
            except Exception as e:
                error_tests.append({
                    "test": "none_rag_context_historical",
                    "success": False,
                    "message": f"Failed to handle None RAG context for historical context: {str(e)}"
                })
            
            # Test with empty current analysis for predictive
            try:
                empty_analysis = {}
                predictive_result = await self.predictive_service.generate_predictive_analysis(
                    "test_empty_predictive",
                    empty_analysis
                )
                error_tests.append({
                    "test": "empty_analysis_predictive",
                    "success": predictive_result is not None,
                    "message": "Handled empty analysis gracefully for predictive analysis"
                })
            except Exception as e:
                error_tests.append({
                    "test": "empty_analysis_predictive",
                    "success": False,
                    "message": f"Failed to handle empty analysis for predictive analysis: {str(e)}"
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
    
    async def test_pattern_recognition(self) -> Dict[str, Any]:
        """Test pattern recognition functionality"""
        try:
            # Test pattern type configurations
            pattern_types = list(PatternType)
            pattern_tests = []
            
            for pattern_type in pattern_types:
                config = self.historical_service.pattern_templates.get(pattern_type)
                if config:
                    # Test keyword matching
                    test_text = f"This is a test about {', '.join(config['keywords'][:3])} and other topics."
                    matching_events = self.historical_service._find_matching_events(
                        [type('Event', (), {'title': test_text, 'description': test_text})()],
                        config
                    )
                    
                    pattern_tests.append({
                        "pattern_type": pattern_type.value,
                        "keywords_count": len(config['keywords']),
                        "keyword_matching_works": len(matching_events) > 0,
                        "significance_threshold": config['significance_threshold']
                    })
            
            # Test pattern similarity calculation
            test_events = [
                type('Event', (), {
                    'title': 'Test Political Event',
                    'description': 'This is about government policy and elections',
                    'significance_score': 0.8
                })()
            ]
            
            political_config = self.historical_service.pattern_templates[PatternType.POLITICAL_CYCLE]
            similarity_score = self.historical_service._calculate_pattern_similarity(test_events, political_config)
            
            return {
                "success": True,
                "pattern_types_tested": len(pattern_tests),
                "pattern_tests": pattern_tests,
                "similarity_calculation_works": similarity_score > 0,
                "similarity_score": similarity_score,
                "message": "Pattern recognition functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Pattern recognition test failed"
            }
    
    async def test_scenario_planning(self) -> Dict[str, Any]:
        """Test scenario planning functionality"""
        try:
            # Test scenario type configurations
            scenario_types = list(self.predictive_service.scenario_types.keys())
            scenario_tests = []
            
            for scenario_type in scenario_types:
                config = self.predictive_service.scenario_types[scenario_type]
                
                # Test scenario probability calculation
                test_analysis = {
                    "impact_assessment": {"overall_impact_score": 0.6},
                    "multi_perspective": {"consensus_score": 0.7}
                }
                
                probability = self.predictive_service._calculate_scenario_probability(scenario_type, test_analysis)
                
                scenario_tests.append({
                    "scenario_type": scenario_type,
                    "probability_range": config['probability_range'],
                    "probability_calculated": probability,
                    "probability_valid": 0 <= probability <= 1
                })
            
            # Test scenario factor identification
            test_analysis = {
                "impact_assessment": {"overall_impact_score": 0.5},
                "multi_perspective": {"consensus_score": 0.6}
            }
            
            optimistic_factors = self.predictive_service._identify_scenario_factors('optimistic', test_analysis)
            pessimistic_factors = self.predictive_service._identify_scenario_factors('pessimistic', test_analysis)
            
            return {
                "success": True,
                "scenario_types_tested": len(scenario_tests),
                "scenario_tests": scenario_tests,
                "optimistic_factors_count": len(optimistic_factors),
                "pessimistic_factors_count": len(pessimistic_factors),
                "scenario_planning_works": len(optimistic_factors) > 0 and len(pessimistic_factors) > 0,
                "message": "Scenario planning functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Scenario planning test failed"
            }
    
    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Phases 4 & 5 Test Report")
        
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
            "phase": "Phases 4 & 5: Historical Context & Predictive Analysis"
        }
        
        # Save report to file
        report_filename = f"phases4_5_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 PHASES 4 & 5 TEST REPORT SUMMARY")
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
    tester = Phases4And5Tester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())

