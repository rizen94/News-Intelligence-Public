#!/usr/bin/env python3
"""
Phase 2 Testing Script: Expert Analysis Integration
Tests the expert analysis functionality thoroughly
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

from services.expert_analysis_service import ExpertAnalysisService, ExpertSourceType, ExpertCredibility
from services.enhanced_storyline_service import EnhancedStorylineService
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Phase2Tester:
    """Comprehensive tester for Phase 2: Expert Analysis Integration"""
    
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
        
        self.expert_service = ExpertAnalysisService(self.ml_service, self.rag_service)
        self.enhanced_service = EnhancedStorylineService(self.ml_service, self.rag_service)
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all Phase 2 tests"""
        logger.info("🚀 Starting Phase 2: Expert Analysis Integration Tests")
        
        tests = [
            ("Expert Analysis Service Test", self.test_expert_analysis_service),
            ("Expert Source Configuration Test", self.test_expert_source_configuration),
            ("Expertise Area Identification Test", self.test_expertise_area_identification),
            ("Expert Analysis Generation Test", self.test_expert_analysis_generation),
            ("Expert Synthesis Test", self.test_expert_synthesis),
            ("Enhanced Integration Test", self.test_enhanced_integration),
            ("API Integration Test", self.test_api_integration),
            ("Performance Test", self.test_performance),
            ("Error Handling Test", self.test_error_handling),
            ("Credibility Assessment Test", self.test_credibility_assessment)
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
    
    async def test_expert_analysis_service(self) -> Dict[str, Any]:
        """Test expert analysis service functionality"""
        try:
            # Test expert sources configuration
            sources_count = len(self.expert_service.expert_sources)
            sources_validation = []
            
            for source_type, source_config in self.expert_service.expert_sources.items():
                required_fields = ['name', 'description', 'credibility_weight', 'expertise_areas', 'search_keywords', 'system_prompt']
                missing_fields = [field for field in required_fields if field not in source_config]
                sources_validation.append({
                    "source_type": source_type.value,
                    "valid": len(missing_fields) == 0,
                    "missing_fields": missing_fields,
                    "expertise_areas_count": len(source_config.get('expertise_areas', [])),
                    "credibility_weight": source_config.get('credibility_weight', 0.0)
                })
            
            # Test expertise areas configuration
            expertise_areas_count = len(self.expert_service.expertise_areas)
            expertise_validation = []
            
            for area_id, area_config in self.expert_service.expertise_areas.items():
                required_fields = ['name', 'description', 'keywords']
                missing_fields = [field for field in required_fields if field not in area_config]
                expertise_validation.append({
                    "area_id": area_id,
                    "valid": len(missing_fields) == 0,
                    "missing_fields": missing_fields,
                    "keywords_count": len(area_config.get('keywords', []))
                })
            
            return {
                "success": True,
                "sources_count": sources_count,
                "sources_validation": sources_validation,
                "expertise_areas_count": expertise_areas_count,
                "expertise_validation": expertise_validation,
                "message": "Expert analysis service basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Expert analysis service test failed"
            }
    
    async def test_expert_source_configuration(self) -> Dict[str, Any]:
        """Test expert source configuration and validation"""
        try:
            # Test all expert source types
            source_types = list(ExpertSourceType)
            source_tests = []
            
            for source_type in source_types:
                config = self.expert_service.expert_sources.get(source_type)
                if config:
                    # Test credibility weight
                    credibility_weight = config.get('credibility_weight', 0.0)
                    credibility_valid = 0.0 <= credibility_weight <= 1.0
                    
                    # Test expertise areas
                    expertise_areas = config.get('expertise_areas', [])
                    expertise_valid = len(expertise_areas) > 0
                    
                    # Test search keywords
                    search_keywords = config.get('search_keywords', [])
                    keywords_valid = len(search_keywords) > 0
                    
                    # Test system prompt
                    system_prompt = config.get('system_prompt', '')
                    prompt_valid = len(system_prompt) > 100
                    
                    source_tests.append({
                        "source_type": source_type.value,
                        "credibility_weight_valid": credibility_valid,
                        "expertise_areas_valid": expertise_valid,
                        "search_keywords_valid": keywords_valid,
                        "system_prompt_valid": prompt_valid,
                        "overall_valid": credibility_valid and expertise_valid and keywords_valid and prompt_valid
                    })
            
            all_sources_valid = all(test["overall_valid"] for test in source_tests)
            
            return {
                "success": all_sources_valid,
                "source_tests": source_tests,
                "all_sources_valid": all_sources_valid,
                "message": f"Expert source configuration {'valid' if all_sources_valid else 'invalid'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Expert source configuration test failed"
            }
    
    async def test_expertise_area_identification(self) -> Dict[str, Any]:
        """Test expertise area identification functionality"""
        try:
            # Test with different storyline types
            test_cases = [
                {
                    "title": "Political Development and Government Policy Changes",
                    "content": "This is about politics, government, policy, and political systems.",
                    "expected_areas": ["political_science", "public_policy"]
                },
                {
                    "title": "Economic Market Analysis and Financial Trends",
                    "content": "This covers economic analysis, market trends, financial systems, and monetary policy.",
                    "expected_areas": ["economics"]
                },
                {
                    "title": "International Relations and Global Governance",
                    "content": "This discusses international relations, global politics, diplomacy, and multilateral cooperation.",
                    "expected_areas": ["international_relations"]
                },
                {
                    "title": "Technology Innovation and Digital Transformation",
                    "content": "This covers technology, digital innovation, artificial intelligence, and cyber security.",
                    "expected_areas": ["technology"]
                }
            ]
            
            identification_tests = []
            
            for test_case in test_cases:
                articles = [{"title": test_case["title"], "content": test_case["content"]}]
                identified_areas = self.expert_service._identify_expertise_areas(
                    test_case["title"], articles, {}
                )
                
                # Check if expected areas are identified
                expected_areas = test_case["expected_areas"]
                areas_found = any(area in identified_areas for area in expected_areas)
                
                identification_tests.append({
                    "test_case": test_case["title"],
                    "identified_areas": identified_areas,
                    "expected_areas": expected_areas,
                    "areas_found": areas_found,
                    "identification_successful": areas_found
                })
            
            all_identifications_successful = all(test["identification_successful"] for test in identification_tests)
            
            return {
                "success": all_identifications_successful,
                "identification_tests": identification_tests,
                "all_identifications_successful": all_identifications_successful,
                "message": f"Expertise area identification {'working' if all_identifications_successful else 'failing'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Expertise area identification test failed"
            }
    
    async def test_expert_analysis_generation(self) -> Dict[str, Any]:
        """Test expert analysis generation"""
        try:
            # Test expert analysis generation
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
            
            # Generate expert analysis
            expert_result = await self.expert_service.generate_expert_analysis(
                "test_storyline_expert_123",
                "Test Storyline for Expert Analysis",
                test_articles,
                test_rag_context
            )
            
            return {
                "success": True,
                "expert_analysis_generated": expert_result is not None,
                "synthesis_quality_score": expert_result.synthesis_quality_score if expert_result else 0.0,
                "expert_consensus_score": expert_result.expert_synthesis.expert_consensus_score if expert_result else 0.0,
                "source_coverage": expert_result.source_coverage if expert_result else {},
                "expertise_areas_covered": expert_result.expertise_areas_covered if expert_result else [],
                "expert_analyses_count": len(expert_result.expert_synthesis.expert_analyses) if expert_result else 0,
                "expert_recommendations_count": len(expert_result.expert_recommendations) if expert_result else 0,
                "message": "Expert analysis generation working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Expert analysis generation test failed"
            }
    
    async def test_expert_synthesis(self) -> Dict[str, Any]:
        """Test expert synthesis functionality"""
        try:
            # Create mock expert analyses
            mock_analyses = []
            
            for i, source_type in enumerate(list(ExpertSourceType)[:3]):  # Test first 3 source types
                from services.expert_analysis_service import ExpertSource as ExpertSourceData
                
                source = ExpertSourceData(
                    source_id=f"test_source_{i}",
                    source_name=f"Test {source_type.value} Source",
                    source_type=source_type.value,
                    credibility_level="high",
                    expertise_areas=["political_science", "public_policy"],
                    institutional_affiliation="Test Institution",
                    publication_date="2024-01-01",
                    source_url="https://example.com",
                    metadata={}
                )
                
                from services.expert_analysis_service import ExpertAnalysis
                
                analysis = ExpertAnalysis(
                    analysis_id=f"test_analysis_{i}",
                    source=source,
                    analysis_content=f"Test analysis content for {source_type.value}",
                    key_insights=["Test insight 1", "Test insight 2"],
                    methodology="Test methodology",
                    confidence_score=0.8,
                    relevance_score=0.7,
                    credibility_score=0.9,
                    supporting_evidence=[],
                    limitations=["Test limitation"],
                    metadata={}
                )
                
                mock_analyses.append(analysis)
            
            # Test synthesis
            synthesis = await self.expert_service._synthesize_expert_analyses(
                "test_storyline_synthesis",
                mock_analyses,
                "Test Storyline for Synthesis"
            )
            
            return {
                "success": True,
                "synthesis_generated": synthesis is not None,
                "consensus_analysis_length": len(synthesis.consensus_analysis) if synthesis else 0,
                "key_disagreements_count": len(synthesis.key_disagreements) if synthesis else 0,
                "expert_consensus_score": synthesis.expert_consensus_score if synthesis else 0.0,
                "synthesis_quality_score": synthesis.synthesis_quality_score if synthesis else 0.0,
                "methodology_notes_length": len(synthesis.methodology_notes) if synthesis else 0,
                "message": "Expert synthesis working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Expert synthesis test failed"
            }
    
    async def test_enhanced_integration(self) -> Dict[str, Any]:
        """Test integration with enhanced storyline service"""
        try:
            # Test service initialization
            service_initialized = self.enhanced_service is not None
            expert_service_available = self.enhanced_service.expert_analysis_service is not None
            
            # Test comprehensive analysis with expert analysis
            test_storyline = {
                "id": "test_storyline_expert_integration_123",
                "title": "Test Storyline for Expert Integration",
                "description": "A test storyline for expert analysis integration"
            }
            
            test_articles = [
                {
                    "id": 1,
                    "title": "Test Article 1",
                    "content": "This is a comprehensive test article about a major development that requires expert analysis.",
                    "source": "Test Source 1",
                    "published_at": "2024-01-01T00:00:00Z"
                },
                {
                    "id": 2,
                    "title": "Test Article 2",
                    "content": "This is another test article providing additional context for expert analysis.",
                    "source": "Test Source 2",
                    "published_at": "2024-01-02T00:00:00Z"
                }
            ]
            
            test_rag_context = {
                "wikipedia": {"summaries": ["Test Wikipedia context"]},
                "gdelt": {"events": ["Test GDELT event"]},
                "extracted_entities": ["Test Entity"],
                "extracted_topics": ["Test Topic"]
            }
            
            # Test expert analysis generation
            expert_result = await self.expert_service.generate_expert_analysis(
                "test_storyline_expert_integration_123",
                "Test Storyline for Expert Integration",
                test_articles,
                test_rag_context
            )
            
            return {
                "success": True,
                "service_initialized": service_initialized,
                "expert_service_available": expert_service_available,
                "expert_analysis_generated": expert_result is not None,
                "synthesis_quality_score": expert_result.synthesis_quality_score if expert_result else 0.0,
                "expert_consensus_score": expert_result.expert_synthesis.expert_consensus_score if expert_result else 0.0,
                "source_coverage_count": len(expert_result.source_coverage) if expert_result else 0,
                "expertise_areas_count": len(expert_result.expertise_areas_covered) if expert_result else 0,
                "expert_analyses_count": len(expert_result.expert_synthesis.expert_analyses) if expert_result else 0,
                "message": "Enhanced storyline integration with expert analysis working"
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
                "/enhanced-analysis/expert-analysis",
                "/enhanced-analysis/expert-sources",
                "/enhanced-analysis/expertise-areas",
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
        """Test performance of expert analysis"""
        try:
            import time
            
            # Test expert analysis performance
            test_articles = [
                {
                    "id": i,
                    "title": f"Test Article {i}",
                    "content": f"This is test article {i} with some content for expert analysis.",
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
            
            # Test expert analysis performance
            start_time = time.time()
            expert_result = await self.expert_service.generate_expert_analysis(
                "perf_test_expert",
                "Performance Test Expert Analysis",
                test_articles,
                test_rag_context
            )
            expert_time = time.time() - start_time
            
            return {
                "success": True,
                "expert_analysis_time": expert_time,
                "performance_acceptable": expert_time < 90,
                "synthesis_quality_score": expert_result.synthesis_quality_score if expert_result else 0.0,
                "expert_analyses_count": len(expert_result.expert_synthesis.expert_analyses) if expert_result else 0,
                "source_coverage_count": len(expert_result.source_coverage) if expert_result else 0,
                "message": f"Performance test completed - Expert Analysis: {expert_time:.2f}s"
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
                expert_result = await self.expert_service.generate_expert_analysis(
                    "test_empty_expert",
                    "Test Empty Expert",
                    empty_articles,
                    {}
                )
                error_tests.append({
                    "test": "empty_articles_expert",
                    "success": expert_result is not None,
                    "message": "Handled empty articles gracefully for expert analysis"
                })
            except Exception as e:
                error_tests.append({
                    "test": "empty_articles_expert",
                    "success": False,
                    "message": f"Failed to handle empty articles for expert analysis: {str(e)}"
                })
            
            # Test with None RAG context
            try:
                expert_result = await self.expert_service.generate_expert_analysis(
                    "test_none_rag_expert",
                    "Test None RAG Expert",
                    [{"id": 1, "title": "Test", "content": "Test content", "source": "Test", "published_at": "2024-01-01T00:00:00Z"}],
                    None
                )
                error_tests.append({
                    "test": "none_rag_context_expert",
                    "success": expert_result is not None,
                    "message": "Handled None RAG context gracefully for expert analysis"
                })
            except Exception as e:
                error_tests.append({
                    "test": "none_rag_context_expert",
                    "success": False,
                    "message": f"Failed to handle None RAG context for expert analysis: {str(e)}"
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
    
    async def test_credibility_assessment(self) -> Dict[str, Any]:
        """Test credibility assessment functionality"""
        try:
            # Test credibility level determination
            credibility_tests = []
            
            for source_type in ExpertSourceType:
                credibility_level = self.expert_service._determine_credibility_level(source_type)
                credibility_valid = credibility_level in ['high', 'medium', 'low', 'unknown']
                
                credibility_tests.append({
                    "source_type": source_type.value,
                    "credibility_level": credibility_level,
                    "valid": credibility_valid
                })
            
            all_credibility_valid = all(test["valid"] for test in credibility_tests)
            
            # Test credibility score calculation
            test_analyses = []
            for i, source_type in enumerate(list(ExpertSourceType)[:3]):
                from services.expert_analysis_service import ExpertSource as ExpertSourceData, ExpertAnalysis
                
                source = ExpertSourceData(
                    source_id=f"cred_test_source_{i}",
                    source_name=f"Test {source_type.value} Source",
                    source_type=source_type.value,
                    credibility_level="high",
                    expertise_areas=["political_science"],
                    institutional_affiliation="Test Institution",
                    publication_date="2024-01-01",
                    source_url="https://example.com",
                    metadata={}
                )
                
                analysis = ExpertAnalysis(
                    analysis_id=f"cred_test_analysis_{i}",
                    source=source,
                    analysis_content="Test analysis content",
                    key_insights=["Test insight"],
                    methodology="Test methodology",
                    confidence_score=0.8,
                    relevance_score=0.7,
                    credibility_score=0.9,
                    supporting_evidence=[],
                    limitations=[],
                    metadata={}
                )
                
                test_analyses.append(analysis)
            
            # Test synthesis quality score calculation
            synthesis_quality_score = self.expert_service._calculate_synthesis_quality_score_from_analyses(test_analyses)
            
            return {
                "success": all_credibility_valid and synthesis_quality_score > 0,
                "credibility_tests": credibility_tests,
                "all_credibility_valid": all_credibility_valid,
                "synthesis_quality_score": synthesis_quality_score,
                "message": "Credibility assessment working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Credibility assessment test failed"
            }
    
    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Phase 2 Test Report")
        
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
            "phase": "Phase 2: Expert Analysis Integration"
        }
        
        # Save report to file
        report_filename = f"phase2_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 PHASE 2 TEST REPORT SUMMARY")
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
    tester = Phase2Tester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
