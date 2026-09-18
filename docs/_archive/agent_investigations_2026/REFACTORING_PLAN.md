# News Intelligence System Refactoring Plan

## Executive Summary
This plan outlines a systematic approach to eliminate duplication and improve design while maintaining full backward compatibility and functionality. The approach follows a phased strategy with built-in verification steps to ensure no regressions.

## Guiding Principles
1. **Never break existing functionality** - All changes must be backward compatible
2. **Incremental improvements** - Small, verifiable changes over massive rewrites
3. **Comprehensive testing** - Each change includes verification steps
4. **Observability first** - Add monitoring before making changes
5. **Rollback capability** - Every change must be reversible

## Phase 0: Preparation and Monitoring (Week 0)

### 0.1 Establish Baseline Metrics
- [ ] Document current API response times for critical endpoints
- [ ] Measure database connection pool utilization under normal load
- [ ] Capture current error rates and failure patterns
- [ ] Create performance benchmarks for key operations

### 0.2 Implement Observability Enhancements
- [ ] Add Prometheus metrics for API endpoint latency and error rates
- [ ] Create database connection pool monitoring dashboard
- [ ] Implement distributed tracing for cross-service calls
- [ ] Add audit logging for all modified endpoints

### 0.3 Create Safety Nets
- [ ] Set up feature flag system for gradual rollouts
- [ ] Implement automated rollback mechanisms based on error thresholds
- [ ] Create blue-green deployment capability for critical services
- [ ] Establish canary deployment procedures

## Phase 1: API Routes Consolidation (Weeks 1-3)

### 1.1 Health Check Consolidation (Low Risk)
**Target**: 6+ duplicate `/health` endpoints → 1 centralized endpoint

**Changes**:
- Create `/api/health` endpoint in `api/domains/system_monitoring/routes/health.py`
- Accept optional `domain` query parameter for domain-specific checks
- Maintain all existing individual `/health` endpoints temporarily
- Add deprecation warnings to old endpoints pointing to new endpoint

**Verification Steps**:
1. Deploy new endpoint alongside existing ones
2. Verify new endpoint returns same data as individual endpoints
3. Monitor usage shift from old to new endpoints
4. After 2 weeks, begin returning 301 redirects from old to new
5. After 4 weeks, remove old endpoints entirely

### 1.2 Deduplication Endpoint Merge (Low Risk)
**Target**: 2 identical deduplication endpoints → 1 unified service

**Changes**:
- Create `api/domains/content_analysis/routes/deduplication.py`
- Merge functionality from `rss_duplicate_management.py` and `article_deduplication.py`
- Maintain backward compatibility during transition
- Use feature flags to route traffic to new endpoint

**Verification Steps**:
1. Deploy new unified endpoint
2. Run both old and new endpoints in parallel
3. Compare response formats and performance
4. Gradually shift traffic using feature flags
5. Decommission old endpoints after validation

### 1.3 Storyline CRUD Consolidation (Medium Risk)
**Target**: 3 files implementing overlapping storyline CRUD → 1 unified router

**Changes**:
- Create `api/domains/storyline_management/routes/storyline_crud_unified.py`
- Implement all CRUD operations in single file with clear separation
- Maintain backward compatibility with existing endpoints
- Add comprehensive unit and integration tests

**Verification Steps**:
1. Implement new router alongside existing ones
2. Verify all existing functionality works through new interface
3. Use traffic mirroring to validate behavior matches
4. Gradually migrate clients to new endpoint
5. Remove old implementations after validation period

### 1.4 Legacy Endpoint Deprecation (Low Risk)
**Target**: 3 legacy endpoints → proper deprecation with migration path

**Changes**:
- `/api/articles/recent` → return 410 with migration guidance to `/api/{domain}/articles`
- `/api/rss_feeds` → return 410 with guidance to domain-specific endpoints
- `/api/fetch_articles` → return 410 with guidance to proper domain endpoints
- Add `Deprecation` header with sunset date
- Log deprecated endpoint usage for monitoring

**Verification Steps**:
1. Implement deprecation responses
2. Monitor usage of deprecated endpoints
3. Provide clear migration paths in response bodies
4. After notice period, change to 404 or remove entirely

## Phase 2: Domain Boundary Fixes (Weeks 4-6)

### 2.1 Finance → News Aggregation Dependency (Medium Risk)
**Target**: Remove direct service imports between domains

**Solutions** (choose one):
Option A: Domain Events
- Finance domain publishes article-related events
- News Aggregation domain consumes relevant events
- Use existing event infrastructure or implement lightweight event bus

Option B: Shared Query Service
- Create shared article query service in infrastructure layer
- Both domains use this service instead of direct calls
- Implement proper caching and rate limiting

**Verification Steps**:
1. Implement chosen solution alongside existing code
2. Verify financial reporting still works correctly
3. Monitor event flow or service usage
4. Gradually switch traffic to new implementation
5. Remove old direct imports after validation

### 2.2 Content Analysis → Storyline Management Dependency (Medium Risk)
**Target**: Eliminate direct imports between domains

**Approach**: Similar to 2.1 - use domain events or shared services

**Verification Steps**:
1. Implement event-driven or service-based communication
2. Verify topic clustering and storyline functionality
3. Monitor for any performance impact
4. Gradually transition and remove old dependencies

## Phase 3: Service Layer Improvements (Weeks 7-9)

### 3.1 Entity Service Consolidation (Low-Medium Risk)
**Target**: Reduce duplication in entity-related services

**Specific Improvements**:
- Extract common validation utilities to shared module
- Create standardized error handling patterns
- Implement shared merge conflict resolution strategies
- Standardize logging and metrics across entity services

**Verification Steps**:
1. Create shared utility modules
2. Refactor one service at a time to use new utilities
3. Run full test suite after each change
4. Monitor performance and error rates
5. Proceed to next service only after successful validation

### 3.2 Knowledge Connector Optimization (Low Risk)
**Target**: Improve efficiency of external knowledge lookups

**Improvements**:
- Add intelligent caching layer with TTL
- Implement request batching for bulk operations
- Add circuit breaker pattern for external service failures
- Standardize fallback chains across services

**Verification Steps**:
1. Implement caching layer with metrics
2. Measure cache hit rates and performance improvement
3. Verify data freshness requirements are met
4. Roll out to all services using knowledge connector

## Phase 4: Database Optimization (Weeks 10-12)

### 4.1 Connection Pool Tuning (Low Risk)
**Target**: Optimize pool sizes based on actual usage

**Steps**:
1. Collect 2 weeks of baseline metrics
2. Analyze peak usage patterns for each pool type
3. Adjust pool sizes based on 95th percentile usage + 20% buffer
4. Implement automatic alerts for sustained high utilization
5. Consider implementing dynamic pool sizing (future phase)

**Verification Steps**:
1. Monitor for connection wait times and timeouts
2. Verify no increase in connection errors
3. Ensure adequate capacity during peak loads
4. Document new baseline for future adjustments

### 4.2 Enhanced Monitoring (Low Risk)
**Target**: Improve database observability

**Implementations**:
- Add query performance tracking with explain plans
- Implement deadlock detection and alerting
- Add connection leak detection with stack traces
- Create slow query log analysis dashboard

## Phase 5: Configuration Consolidation (Weeks 13-14)

### 5.1 Unified Database Configuration (Low Risk)
**Target**: Consolidate database configuration sources

**Changes**:
- Move all database configuration to `shared/database/config.py`
- Maintain backward compatibility aliases
- Add validation and default values
- Ensure all existing code paths continue to work

**Verification Steps**:
1. Verify all configuration access patterns still work
2. Test with various environment variable combinations
3. Validate fallback behaviors remain intact
4. Ensure no performance impact

## Verification and Validation Strategy

### Continuous Verification
- **Automated Tests**: Run full test suite after every change
- **Integration Tests**: Validate end-to-end workflows
- **Performance Tests**: Ensure no degradation in response times
- **Security Scans**: Verify no new vulnerabilities introduced

### Progressive Validation
- **Canary Releases**: Route 5% of traffic to new implementation
- **Metrics Monitoring**: Track error rates, latency, throughput
- **User Feedback**: Monitor for reported issues
- **Rollback Triggers**: Automatic rollback if error rate > 1% or latency > 2x baseline

### Documentation Updates
- Update API documentation for changed endpoints
- Maintain backward compatibility notes in documentation
- Create migration guides for breaking changes
- Update architecture decision records (ADRs)

## Risk Mitigation Strategies

### Backup and Recovery
- **Database**: Ensure point-in-time recovery is tested and working
- **Code**: Use feature flags and branch-by-abstraction patterns
- **Configuration**: Implement configuration versioning and rollback

### Monitoring and Alerting
- **Real-time Dashboards**: Track key metrics during rollouts
- **Automated Alerts**: Page on anomaly detection
- **Health Checks**: Enhanced endpoint health verification
- **Synthetic Transactions**: Continuous end-to-end validation

### Team Coordination
- **Change Freeze Windows**: Avoid deployments during peak business hours
- **Pair Programming**: Critical changes done with reviewer present
- **Post-Incident Reviews**: Blameless retrospectives for any issues
- **Knowledge Sharing**: Document lessons learned throughout process

## Success Metrics

### Quantitative Goals
- Reduce route file count by 40% (58 → 35 files)
- Eliminate 100% of exact duplicate endpoints
- Reduce functional duplication by 80%
- Achieve 95% consistency in naming and response formats
- Maintain or improve API response times (p95 < 200ms)
- Keep error rate below 0.1% during transition

### Qualitative Goals
- Improved developer onboarding experience
- Clearer domain boundaries and responsibilities
- Easier maintenance and extension
- Better alignment with DDD principles
- Reduced cognitive load for contributors

## Rollback Plan

### Immediate Rollback (< 1 hour)
- Feature flag toggle to revert to old behavior
- Database connection pool size reset to previous values
- Configuration rollback via environment variables

### Short-term Rollback (< 24 hours)
- Git revert of specific changes
- Database migration rollback procedures
- Service restart with previous configuration

### Long-term Rollback (> 24 hours)
- Full environment restoration from backup
- Database point-in-time recovery
- Complete service stack rollback

## Timeline and Milestones

### Week 0: Preparation
- Monitoring baseline established
- Observability tools deployed
- Safety mechanisms in place

### Weeks 1-3: API Consolidation
- Health checks unified
- Deduplication merged
- Storyline CRUD consolidated
- Legacy endpoints deprecated

### Weeks 4-6: Domain Boundary Fixes
- Cross-domain dependencies eliminated
- Event-driven or service-based communication implemented

### Weeks 7-9: Service Layer Improvements
- Shared utilities implemented
- Entity services optimized
- Knowledge connector enhanced

### Weeks 10-12: Database Optimization
- Connection pools tuned
- Monitoring enhanced
- Performance baselines established

### Weeks 13-14: Configuration Consolidation
- Unified configuration implemented
- Final validation completed

## Next Steps
1. Begin Phase 0 preparations immediately
2. Schedule daily standups to review progress and blockers
3. Conduct weekly retrospectives to adjust plan as needed
4. Prepare rollback procedures before each major change
5. Communicate changes to all stakeholders in advance

This systematic approach ensures we can safely improve the codebase while maintaining full functionality and providing multiple safety nets throughout the process.