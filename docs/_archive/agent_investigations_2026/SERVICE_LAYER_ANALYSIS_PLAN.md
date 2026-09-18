# Service Layer Analysis Plan

## Objective
Analyze the service layer of the News Intelligence system to identify:
1. Duplicate or overlapping service functionality
2. Opportunities for consolidation and simplification
3. Services that violate domain boundaries
4. Underdeveloped or incomplete service implementations

## Approach
This analysis will examine:
- Service organization and categorization
- Duplicate service functionality across domains
- Service layer dependencies and coupling
- Entity-related services (as specifically requested)
- Background service responsibilities
- Service initialization and lifecycle management

## Files to Analyze

### Core Services (api/services/)
- article_entity_extraction_service.py
- entity_enrichment_service.py
- entity_resolution_service.py
- entity_organizer_service.py
- entity_profile_builder_service.py
- entity_profile_sync_service.py
- entity_knowledge_connector.py
- entity_seed_catalog_service.py
- entity_relational_expansion_service.py
- entity_cleanup_service.py
- pattern_entity_extractor.py
- claim_extraction_service.py
- event_extraction_service.py
- event_deduplication_service.py
- extracted_claims_dedupe_service.py
- fact_verification_service.py
- content_refinement_queue_service.py
- intelligence_analysis_service.py
- deep_content_synthesis.py
- article_content_enrichment_service.py
- dossier_compiler_service.py
- graph_connection_processor_service.py
- graph_connection_queue_service.py
- legislative_reference_service.py
- gpr_epu_import_service.py
- ai_storyline_discovery.py
- dossierservice (if exists)
- automation_manager.py
- backlog_metrics.py
- backlog_trend_service.py
- nightly_ingest_window_service.py
- nightly_phase_idle.py
- orchestrator_coordinator.py
- enhancement_orchestrator_service.py
- embeddings_worker_service.py
- cross_domain_service.py

### Domain Services (api/domains/*/services/)
- content_analysis/services/topic_clustering_service.py
- content_analysis/services/topic_fast_match_service.py
- finance/services/metals_dev.py
- finance/services/commodity_registry.py
- intelligence_hub/routes/* (some services may be in routes)
- storyline_management/services/storyline_service.py
- storyline_management/services/proactive_detection_service.py
- system_monitoring/services/* (if any)

### NRI Core Services (api/nri_core/)
- All services in nri_core/services/, evidence/, loop/, spine/, vault/

## Analysis Phases

### Phase 1: Service Extraction and Categorization
- Extract all service classes and their methods
- Categorize by domain/function
- Identify service responsibilities and dependencies

### Phase 2: Duplicate Service Detection
- Identify services with overlapping functionality
- Find services that perform similar operations
- Detect copy-pasted code between services
- Identify services that could be merged

### Phase 3: Entity-Related Service Analysis (Specific Request)
- Focus on entity extraction, enrichment, resolution, organization services
- Analyze data flow between entity services
- Identify duplication in entity handling logic
- Check for consistent interfaces and data models

### Phase 4: Dependency and Coupling Analysis
- Map service dependencies
- Identify tight coupling between services
- Find services that violate domain boundaries
- Detect circular dependencies

### Phase 5: Background Service Analysis
- Examine initialization in api/main.py
- Identify orchestration patterns
- Analyze scheduling and triggering mechanisms
- Check for redundant background processes

### Phase 6: Consolidation Recommendations
- Produce prioritized recommendations for service consolidation
- Identify services that should be split or refactored
- Suggest improved service organization
- Estimate effort for recommended changes

## Expected Deliverables
1. Service Inventory - Catalog of all services with responsibilities
2. Duplicate Service Report - Overlapping functionality identified
3. Entity Service Analysis - Detailed look at entity-related services
4. Dependency Map - Service coupling and dependency analysis
5. Consolidation Plan - Prioritized recommendations with effort estimates

## Investigation Methods
- Use grep and semantic search to find service definitions
- Analyze service method signatures and responsibilities
- Check service initialization and registration patterns
- Examine service-to-service calls
- Review service tests (if any) to understand intended behavior