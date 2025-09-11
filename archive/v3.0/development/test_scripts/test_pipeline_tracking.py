#!/usr/bin/env python3
"""
Pipeline Tracking Test Script
Tests the comprehensive pipeline tracking and logging system
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

from services.pipeline_logger import PipelineLogger, PipelineStage, get_pipeline_logger
from collectors.enhanced_rss_collector_with_tracking import EnhancedRSSCollectorWithTracking, get_enhanced_rss_collector
from modules.ml.summarization_service import MLSummarizationService
from services.rag_service import RAGService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PipelineTrackingTester:
    """Comprehensive tester for pipeline tracking system"""
    
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
        
        self.pipeline_logger = get_pipeline_logger()
        self.rss_collector = get_enhanced_rss_collector(self.ml_service, self.rag_service, self.pipeline_logger)
        self.test_results = []
    
    async def run_all_tests(self):
        """Run all pipeline tracking tests"""
        logger.info("🚀 Starting Pipeline Tracking Tests")
        
        tests = [
            ("Pipeline Logger Test", self.test_pipeline_logger),
            ("Pipeline Checkpoint Test", self.test_pipeline_checkpoints),
            ("Pipeline Performance Test", self.test_pipeline_performance),
            ("RSS Collector Integration Test", self.test_rss_collector_integration),
            ("ML Step Logging Test", self.test_ml_step_logging),
            ("Database Operation Logging Test", self.test_database_operation_logging),
            ("Error Handling Test", self.test_error_handling),
            ("Live Monitoring Test", self.test_live_monitoring),
            ("Performance Metrics Test", self.test_performance_metrics),
            ("Trace Completion Test", self.test_trace_completion)
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
    
    async def test_pipeline_logger(self) -> Dict[str, Any]:
        """Test pipeline logger basic functionality"""
        try:
            # Test logger initialization
            logger_initialized = self.pipeline_logger is not None
            
            # Test trace creation
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="test_feed_123",
                article_id=None,
                storyline_id=None
            )
            
            trace_created = trace_id is not None
            trace_exists = self.pipeline_logger.get_trace(trace_id) is not None
            
            # Test trace completion
            trace = self.pipeline_logger.end_trace(trace_id, success=True)
            trace_completed = trace is not None and trace.success
            
            return {
                "success": logger_initialized and trace_created and trace_exists and trace_completed,
                "logger_initialized": logger_initialized,
                "trace_created": trace_created,
                "trace_exists": trace_exists,
                "trace_completed": trace_completed,
                "trace_id": trace_id,
                "message": "Pipeline logger basic functionality working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Pipeline logger test failed"
            }
    
    async def test_pipeline_checkpoints(self) -> Dict[str, Any]:
        """Test pipeline checkpoint functionality"""
        try:
            # Start a new trace
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="test_feed_checkpoints",
                article_id="test_article_123",
                storyline_id=None
            )
            
            # Test various checkpoint types
            checkpoint_tests = []
            
            # Test successful checkpoint
            checkpoint_id_1 = self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_DISCOVERY,
                status="started",
                input_data={"rss_url": "https://example.com/rss"},
                metadata={"test": "checkpoint_1"}
            )
            checkpoint_tests.append({
                "type": "successful_checkpoint",
                "checkpoint_id": checkpoint_id_1,
                "success": checkpoint_id_1 is not None
            })
            
            # Test failed checkpoint
            checkpoint_id_2 = self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.ARTICLE_EXTRACTION,
                status="failed",
                error_message="Test error message",
                metadata={"test": "checkpoint_2"}
            )
            checkpoint_tests.append({
                "type": "failed_checkpoint",
                "checkpoint_id": checkpoint_id_2,
                "success": checkpoint_id_2 is not None
            })
            
            # Test skipped checkpoint
            checkpoint_id_3 = self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.DEDUPLICATION,
                status="skipped",
                output_data={"reason": "duplicate_article"},
                metadata={"test": "checkpoint_3"}
            )
            checkpoint_tests.append({
                "type": "skipped_checkpoint",
                "checkpoint_id": checkpoint_id_3,
                "success": checkpoint_id_3 is not None
            })
            
            # Get trace and check checkpoints
            trace = self.pipeline_logger.get_trace(trace_id)
            checkpoint_count = len(trace.checkpoints) if trace else 0
            
            # End trace
            completed_trace = self.pipeline_logger.end_trace(trace_id, success=False, error_stage=PipelineStage.ARTICLE_EXTRACTION)
            
            all_checkpoints_created = all(test["success"] for test in checkpoint_tests)
            
            return {
                "success": all_checkpoints_created and checkpoint_count == 3,
                "checkpoint_tests": checkpoint_tests,
                "checkpoint_count": checkpoint_count,
                "trace_completed": completed_trace is not None,
                "message": "Pipeline checkpoints working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Pipeline checkpoints test failed"
            }
    
    async def test_pipeline_performance(self) -> Dict[str, Any]:
        """Test pipeline performance tracking"""
        try:
            # Create multiple traces to test performance
            trace_ids = []
            for i in range(5):
                trace_id = self.pipeline_logger.start_trace(
                    rss_feed_id=f"perf_test_feed_{i}",
                    article_id=f"perf_test_article_{i}",
                    storyline_id=None
                )
                trace_ids.append(trace_id)
                
                # Add some checkpoints with varying durations
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="started",
                    metadata={"test": "performance"}
                )
                
                # Simulate some processing time
                await asyncio.sleep(0.1)
                
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="completed",
                    metadata={"test": "performance"}
                )
                
                # End trace
                self.pipeline_logger.end_trace(trace_id, success=True)
            
            # Get performance summary
            performance_summary = self.pipeline_logger.get_performance_summary()
            
            return {
                "success": True,
                "traces_created": len(trace_ids),
                "performance_summary": performance_summary,
                "message": "Pipeline performance tracking working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Pipeline performance test failed"
            }
    
    async def test_rss_collector_integration(self) -> Dict[str, Any]:
        """Test RSS collector integration with pipeline tracking"""
        try:
            # Test RSS collector with tracking
            test_rss_url = "https://feeds.bbci.co.uk/news/rss.xml"  # BBC News RSS feed
            
            result = await self.rss_collector.process_rss_feed_with_tracking(
                rss_feed_id="test_rss_integration_123",
                rss_url=test_rss_url,
                feed_name="BBC News Test"
            )
            
            # Check if tracking was successful
            tracking_successful = "trace_id" in result
            
            # Get performance metrics
            performance_metrics = self.rss_collector.get_performance_metrics()
            
            # Get pipeline summary
            pipeline_summary = self.rss_collector.get_pipeline_summary()
            
            return {
                "success": tracking_successful,
                "rss_processing_result": result,
                "performance_metrics": performance_metrics,
                "pipeline_summary": pipeline_summary,
                "message": "RSS collector integration with tracking working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "RSS collector integration test failed"
            }
    
    async def test_ml_step_logging(self) -> Dict[str, Any]:
        """Test ML step logging functionality"""
        try:
            # Start a trace
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="test_ml_logging",
                article_id="test_article_ml",
                storyline_id=None
            )
            
            # Test ML step logging
            self.pipeline_logger.log_ml_step(
                trace_id=trace_id,
                stage=PipelineStage.ML_SUMMARIZATION,
                model_name="llama-3.1-70b",
                input_tokens=1000,
                output_tokens=200,
                processing_time_ms=5000.0,
                success=True
            )
            
            # Test failed ML step logging
            self.pipeline_logger.log_ml_step(
                trace_id=trace_id,
                stage=PipelineStage.SENTIMENT_ANALYSIS,
                model_name="sentiment-model",
                input_tokens=500,
                output_tokens=0,
                processing_time_ms=2000.0,
                success=False,
                error="Model connection failed"
            )
            
            # Get trace and check ML checkpoints
            trace = self.pipeline_logger.get_trace(trace_id)
            ml_checkpoints = [c for c in trace.checkpoints if "ml_model" in c.metadata]
            
            # End trace
            self.pipeline_logger.end_trace(trace_id, success=True)
            
            return {
                "success": len(ml_checkpoints) == 2,
                "ml_checkpoints_count": len(ml_checkpoints),
                "ml_checkpoints": [
                    {
                        "stage": c.stage.value,
                        "model_name": c.metadata.get("ml_model"),
                        "success": c.status == "completed"
                    }
                    for c in ml_checkpoints
                ],
                "message": "ML step logging working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "ML step logging test failed"
            }
    
    async def test_database_operation_logging(self) -> Dict[str, Any]:
        """Test database operation logging"""
        try:
            # Start a trace
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="test_db_logging",
                article_id="test_article_db",
                storyline_id=None
            )
            
            # Test successful database operation
            self.pipeline_logger.log_database_operation(
                trace_id=trace_id,
                operation="INSERT",
                table="articles",
                record_count=1,
                duration_ms=150.0,
                success=True
            )
            
            # Test failed database operation
            self.pipeline_logger.log_database_operation(
                trace_id=trace_id,
                operation="UPDATE",
                table="storylines",
                record_count=0,
                duration_ms=50.0,
                success=False,
                error="Connection timeout"
            )
            
            # Get trace and check database checkpoints
            trace = self.pipeline_logger.get_trace(trace_id)
            db_checkpoints = [c for c in trace.checkpoints if "db_operation" in c.metadata]
            
            # End trace
            self.pipeline_logger.end_trace(trace_id, success=True)
            
            return {
                "success": len(db_checkpoints) == 2,
                "db_checkpoints_count": len(db_checkpoints),
                "db_checkpoints": [
                    {
                        "operation": c.metadata.get("db_operation"),
                        "table": c.metadata.get("table"),
                        "success": c.status == "completed"
                    }
                    for c in db_checkpoints
                ],
                "message": "Database operation logging working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Database operation logging test failed"
            }
    
    async def test_error_handling(self) -> Dict[str, Any]:
        """Test error handling in pipeline tracking"""
        try:
            error_tests = []
            
            # Test invalid trace ID
            try:
                invalid_checkpoint = self.pipeline_logger.add_checkpoint(
                    trace_id="invalid_trace_id",
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="started"
                )
                error_tests.append({
                    "test": "invalid_trace_id",
                    "success": invalid_checkpoint is None,
                    "message": "Handled invalid trace ID gracefully"
                })
            except Exception as e:
                error_tests.append({
                    "test": "invalid_trace_id",
                    "success": False,
                    "message": f"Failed to handle invalid trace ID: {str(e)}"
                })
            
            # Test error in trace completion
            try:
                trace_id = self.pipeline_logger.start_trace(
                    rss_feed_id="test_error_handling",
                    article_id="test_article_error",
                    storyline_id=None
                )
                
                # Add a failed checkpoint
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.ARTICLE_EXTRACTION,
                    status="failed",
                    error_message="Test error for error handling"
                )
                
                # End trace with error
                trace = self.pipeline_logger.end_trace(trace_id, success=False, error_stage=PipelineStage.ARTICLE_EXTRACTION)
                
                error_tests.append({
                    "test": "error_trace_completion",
                    "success": trace is not None and not trace.success,
                    "message": "Error trace completion working"
                })
            except Exception as e:
                error_tests.append({
                    "test": "error_trace_completion",
                    "success": False,
                    "message": f"Failed error trace completion: {str(e)}"
                })
            
            all_tests_passed = all(test["success"] for test in error_tests)
            
            return {
                "success": all_tests_passed,
                "error_tests": error_tests,
                "message": f"Error handling {'working' if all_tests_passed else 'failing'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Error handling test failed"
            }
    
    async def test_live_monitoring(self) -> Dict[str, Any]:
        """Test live monitoring functionality"""
        try:
            # Start multiple active traces
            active_traces = []
            for i in range(3):
                trace_id = self.pipeline_logger.start_trace(
                    rss_feed_id=f"live_monitoring_feed_{i}",
                    article_id=f"live_monitoring_article_{i}",
                    storyline_id=None
                )
                active_traces.append(trace_id)
                
                # Add some checkpoints
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="started",
                    metadata={"test": "live_monitoring"}
                )
            
            # Get live status
            live_status = self.pipeline_logger.get_performance_summary()
            
            # Complete some traces
            for i, trace_id in enumerate(active_traces[:2]):
                self.pipeline_logger.end_trace(trace_id, success=True)
            
            # Get updated live status
            updated_live_status = self.pipeline_logger.get_performance_summary()
            
            return {
                "success": True,
                "active_traces_created": len(active_traces),
                "initial_live_status": live_status,
                "updated_live_status": updated_live_status,
                "remaining_active_traces": len(active_traces) - 2,
                "message": "Live monitoring working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Live monitoring test failed"
            }
    
    async def test_performance_metrics(self) -> Dict[str, Any]:
        """Test performance metrics calculation"""
        try:
            # Create traces with different performance characteristics
            performance_tests = []
            
            for i in range(3):
                trace_id = self.pipeline_logger.start_trace(
                    rss_feed_id=f"perf_metrics_feed_{i}",
                    article_id=f"perf_metrics_article_{i}",
                    storyline_id=None
                )
                
                # Add checkpoints with different durations
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="started",
                    metadata={"test": "performance_metrics"}
                )
                
                # Simulate different processing times
                await asyncio.sleep(0.1 * (i + 1))
                
                self.pipeline_logger.add_checkpoint(
                    trace_id=trace_id,
                    stage=PipelineStage.RSS_FEED_DISCOVERY,
                    status="completed",
                    metadata={"test": "performance_metrics"}
                )
                
                # End trace
                trace = self.pipeline_logger.end_trace(trace_id, success=True)
                performance_tests.append({
                    "trace_id": trace_id,
                    "duration_ms": trace.total_duration_ms,
                    "checkpoint_count": len(trace.checkpoints)
                })
            
            # Get performance summary
            performance_summary = self.pipeline_logger.get_performance_summary()
            
            return {
                "success": True,
                "performance_tests": performance_tests,
                "performance_summary": performance_summary,
                "message": "Performance metrics calculation working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Performance metrics test failed"
            }
    
    async def test_trace_completion(self) -> Dict[str, Any]:
        """Test trace completion and cleanup"""
        try:
            # Create a trace
            trace_id = self.pipeline_logger.start_trace(
                rss_feed_id="test_trace_completion",
                article_id="test_article_completion",
                storyline_id=None
            )
            
            # Add some checkpoints
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_DISCOVERY,
                status="started",
                metadata={"test": "trace_completion"}
            )
            
            self.pipeline_logger.add_checkpoint(
                trace_id=trace_id,
                stage=PipelineStage.RSS_FEED_DISCOVERY,
                status="completed",
                metadata={"test": "trace_completion"}
            )
            
            # Check trace exists before completion
            trace_before = self.pipeline_logger.get_trace(trace_id)
            trace_exists_before = trace_before is not None
            
            # Complete trace
            completed_trace = self.pipeline_logger.end_trace(trace_id, success=True)
            
            # Check trace is removed from active traces
            trace_after = self.pipeline_logger.get_trace(trace_id)
            trace_exists_after = trace_after is not None
            
            return {
                "success": trace_exists_before and not trace_exists_after and completed_trace is not None,
                "trace_exists_before": trace_exists_before,
                "trace_exists_after": trace_exists_after,
                "completed_trace": completed_trace is not None,
                "trace_duration_ms": completed_trace.total_duration_ms if completed_trace else 0.0,
                "message": "Trace completion and cleanup working"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Trace completion test failed"
            }
    
    async def generate_test_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Pipeline Tracking Test Report")
        
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
            "system": "Pipeline Tracking System"
        }
        
        # Save report to file
        report_filename = f"pipeline_tracking_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        logger.info("=" * 60)
        logger.info("📊 PIPELINE TRACKING TEST REPORT SUMMARY")
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
    tester = PipelineTrackingTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
