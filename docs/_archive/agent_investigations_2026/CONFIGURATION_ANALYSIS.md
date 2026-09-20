# News Intelligence Configuration System Analysis

## Executive Summary
Analysis of the configuration system reveals a layered approach with clear separation of concerns:
- **runtime.py**: Single source of truth for environment variables (NRI unification)
- **settings.py**: Central application configuration (paths, resources, models, feature flags)
- **database_targets.py**: Database connection configuration
- **domain YAML files**: Per-domain configuration and specifications
- **Various specialized configs**: For logging, monitoring, commodities, etc.

The system follows good practices with centralized configuration management but shows opportunities for consolidation and improved organization.

## Configuration Architecture Overview

### Core Configuration Files

1. **`api/config/runtime.py`** - Single Source for Environment Variables
   - Purpose: Provides unified access to environment variables for both News Intelligence and NRI (investigation) systems
   - Key Features:
     - LRU-cached `get_runtime_config()` function returns merged settings
     - Helper functions for typed environment variable access (`env_str`, `env_bool`, `env_int`, `env_float`)
     - Investigation schema management (pre/post-migration handling)
     - Feature flags for NRI components
     - Ollama configuration for dual-host routing

2. **`api/config/settings.py`** - Central Application Configuration
   - Purpose: Main configuration hub for paths, resource limits, model settings, and API behavior
   - Key Sections:
     - Path definitions (imported from `config.paths`)
     - Archive storage configuration
     - Directory creation on startup
     - GPU and resource limits (VRAM/RAM allocation)
     - Ollama model configuration and dual-host routing policies
     - Database connection settings
     - Feature flags (SQL explorer, logging levels, CORS, security, rate limiting)
     - Domain-specific configuration getters (RSS ingest, finance, politics, etc.)
     - Topic clustering parameters
     - Public web authentication settings

3. **`api/config/database_targets.py`** - Database Connection Configuration
   - Purpose: Defines database connection targets for different usage patterns
   - Key Functions:
     - `news_intel_connect_kwargs()`: Connection parameters for news_intel pool
     - `news_intel_dsn()`: DSN string construction
     - (Incomplete function at end appears to be copied incorrectly)

4. **`api/config/database.py`** - Compatibility Shim
   - Purpose: Re-exports from `shared.database.connection` for backward compatibility
   - Ensures all DB access uses the single pooled connection in shared module

### Domain-Specific Configuration

5. **Domain YAML Files** (`api/config/domains/*.yaml`)
   - Purpose: Per-domain activation and basic configuration
   - Files: `artificial-intelligence.yaml`, `finance.yaml`, `legal.yaml`, `medicine.yaml`, `politics.yaml`
   - Pattern: Each defines `is_active: true/false` and potentially domain-specific settings

6. **Domain Specification Files** (`api/config/domains/specs/*.{json,yaml}`)
   - Purpose: Detailed domain schemas and configurations
   - Types:
     - JSON Schema files (`domain.spec.schema.json`, `_template.domain.json`)
     - Domain-specific specifications (`*.domain.json`)
     - Generated stubs (`*.stub.yaml` in `generated/` subdirectory)

### Specialized Configuration Files

7. **Resource and Infrastructure Configs**
   - `commodity_registry.yaml`: Commodity definitions and metadata
   - `commodity_map_overlays.yaml`: Geographic overlay configurations
   - `monitoring_devices.yaml`: Device monitoring configurations
   - `government_sources.yaml`: Government API source configurations
   - `sources.yaml`: Data source definitions
   - `reference_events_seed.yaml`: Reference event data
   - `seed_world_entities.yaml`: World entity seed data
   - `historical_arcs.yaml`: Historical narrative arc definitions
   - `finance_schedule.yaml`: Financial data collection schedules
   - `newsroom.yaml`: Newsroom configuration
   - `domain_synthesis_config.yaml`: Content synthesis settings
   - `content_quality_config.py`: Content quality thresholds and rules
   - `orchestrator_governance.{py,yaml}`: Orchestrator behavior and permissions
   - `nri_resolution_config.py`: NRI-specific resolution configuration
   - `context_centric.yaml` and `context_centric_config.py`: Context-centric service configuration
   - `logging_config.py`: Logging configuration

8. **Web Frontend Configuration**
   - `web/src/config/apiConfig.ts`: API configuration for frontend
   - `web/src/config/apiRoutes.ts`: API route definitions for frontend

## Configuration Flow and Dependencies

```
Environment Variables
        ↓
api/config/runtime.py ← Single source of truth for env vars
        ↓
api/config/settings.py ← Main application configuration (imports runtime)
        ↓
Individual service modules ← Import specific settings as needed
        ↓
Domain-specific YAML configs ← Referenced by domain services
        ↓
Shared database connections ← Via shared.database.connection
```

## Key Observations and Assessment

### Strengths
1. **Clear Separation of Concerns**: Environment variables → Application settings → Domain configs
2. **Single Source for Env Vars**: `runtime.py` prevents scattered `os.getenv()` calls
3. **Typed Accessors**: Helper functions provide type safety and default values
4. **Domain Isolation**: Each domain has its own YAML configuration file
5. **Feature Flags**: Runtime-toggleable features via environment variables
6. **Backward Compatibility**: Database shim ensures consistent connection handling

### Areas for Improvement
1. **Incomplete Function**: `database_targets.py` has a malformed function at the end (lines 49-55 appear to be incorrectly pasted)
2. **Configuration Scattering**: 54+ config files spread across multiple directories
3. **YAML vs Python Config Mix**: Some configs in YAML, some in Python (could benefit from consistency)
4. **Domain Config Variation**: Some domains have rich YAML configs, others minimal
5. **Hardcoded Values**: Some values that could be environment-configurable are hardcoded (e.g., rate limits)
6. **Configuration Validation**: Limited visible validation of configuration values

### Duplicate/Redundant Configuration Patterns
1. **Ollama Host Configuration**: Defined in both `runtime.py` (lines 92-93) and `settings.py` (lines 67, 69-70)
2. **Database Configuration**: Appears in `runtime.py`, `settings.py` (lines 130-134), and `database_targets.py`
3. **Path Definitions**: Imported from `config.paths` in settings but also referenced elsewhere

## Recommendations for Configuration System Consolidation

### Priority 0 (Immediate - 1-2 days)
1. **Fix the broken function in `database_targets.py`** (lines 49-55)
2. **Consolidate Ollama host configuration** to a single source of truth
3. **Audit and consolidate database configuration** sources

### Priority 1 (Short-term - 3-5 days)
1. **Create a configuration index/document** that maps all config files to their purpose
2. **Standardize configuration format** where beneficial (consider moving simple configs to YAML)
3. **Implement basic configuration validation** for critical values

### Priority 2 (Medium-term - 1-2 weeks)
1. **Consider hierarchical configuration structure** with base/override patterns
2. **Evaluate external configuration management tools** (consul, etcd, or simple file watching)
3. **Create configuration documentation** for operators and developers

### Priority 3 (Long-term)
1. **Implement configuration versioning** and change management
2. **Add configuration-driven feature flags** with UI for management
3. **Consider encryption for sensitive configuration values** (secrets management)

## Impact Assessment
- **Risk of Change**: Low to Medium (configuration changes are generally low-risk if backward compatible)
- **Benefit**: Improved maintainability, reduced configuration drift, easier onboarding
- **Effort Estimate**: 3-5 days for initial cleanup and standardization
"""