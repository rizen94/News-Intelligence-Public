# Configuration System Analysis Plan

## Objective
Analyze the configuration system of the News Intelligence system to:
1. Map all configuration sources and their purposes
2. Identify duplicated or conflicting configuration
3. Find hardcoded values that should be configurable
4. Evaluate environment-specific configuration management
5. Assess configuration loading and access patterns

## Approach
This analysis will examine:
- Configuration file types and locations (YAML, Python, environment variables)
- Configuration loading mechanisms and singleton patterns
- Duplication across configuration sources
- Hardcoded values scattered throughout the codebase
- Environment-specific configurations and feature flags
- Configuration validation and default handling

## Files to Analyze

### Core Configuration (api/config/)
- runtime.py - Main runtime configuration and environment variable handling
- settings.py - Django-style settings configuration
- database.py / database_targets.py - Database connection configuration
- paths.py - Path definitions and directory structures
- logging_config.py - Logging configuration
- investigation_tables.py - NRI investigation table definitions
- orchestrator_governance.py/yaml - Orchestrator configuration
- schedulers.yaml - Scheduled job definitions
- nri_resolution_config.py - NRI resolution configuration
- context_centric.yaml - Context-centric configuration
- domain_synthesis_config.yaml - Domain synthesis configuration
- Various domain-specific YAML configs in api/config/domains/

### Domain Configuration
- api/config/domains/*.yaml - Domain definitions and activation status
- api/config/domains/specs/*.domain.json - Domain specification files
- api/config/domains/specs/generated/* - Generated domain specifications

### Environment and Secrets
- .env files and environment variable usage
- Secrets management approach
- Configuration precedence and override patterns

## Analysis Phases

### Phase 1: Configuration Source Mapping
- Identify all configuration files and their locations
- Catalog configuration loading mechanisms
- Map configuration ownership by domain/function
- Identify singleton vs instantiation patterns

### Phase 2: Duplication and Conflict Detection
- Find duplicate configuration keys across files
- Identify conflicting values for same configuration
- Detect hardcoded values that duplicate configuration
- Analyze configuration override precedence

### Phase 3: Hardcoded Value Identification
- Search for configuration-like values hardcoded in code
- Find magic numbers, strings, and configuration equivalents
- Identify environment-specific values in code
- Locate feature flags and toggles implemented in code

### Phase 4: Environment and Deployment Analysis
- Examine environment-specific configuration handling
- Analyze configuration for different deployment environments
- Review secrets management and credential handling
- Evaluate configuration validation and error handling

### Phase 5: Access Pattern Evaluation
- Review how services access configuration
- Identify tight coupling to specific configuration sources
- Analyze configuration caching and performance implications
- Assess testability and mockability of configuration access

## Expected Deliverables
1. Configuration Source Inventory - Catalog of all configuration sources
2. Duplication Report - Duplicate and conflicting configuration items
3. Hardcoded Values Report - Configuration values found in code
4. Environment Configuration Analysis - Environment-specific handling
5. Configuration Access Patterns - How configuration is consumed
6. Consolidation Recommendations - Prioritized improvements

## Investigation Methods
- Use grep and semantic search to find configuration access patterns
- Analyze configuration loading and initialization code
- Check for direct os.environ.get usage outside of config layer
- Examine configuration validation and default value handling
- Review configuration documentation and usage guidelines