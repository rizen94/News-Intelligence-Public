# Investigation Plan: Using Repomix and MemPalace MCP for News Intelligence

## Objective
Use repomix to analyze the News Intelligence codebase and MemPalace MCP to store/retrieve institutional knowledge while developing locally and deploying via rsync to the Widow server.

## Phase 1: Environment Setup Verification
1. Confirm we're working in the News Intelligence project directory
2. Verify connection to Widow server (192.168.93.101)
3. Check that repomix is available and configured
4. Confirm MemPalace MCP is accessible

## Phase 2: Baseline Analysis with Repomix
Create a comprehensive baseline of the current codebase:
```bash
# Generate XML summary of core components
repomix --style xml --output baseline.xml \
  --token-count-tree 500 \
  api/ api/config/ api/domains/ api/services/ api/shared/

# Generate markdown summary for easier reading
repomix --style markdown --output baseline.md \
  --token-count-tree 300 \
  api/ api/config/ api/domains/ api/services/ api/shared/

# Get file statistics for overview
repomix --no-files --token-count-tree 100 --output stats.json .
```

## Phase 3: MemPalace Knowledge Integration
Explore and leverage existing institutional knowledge:
```bash
# Explore Memory Palace structure
mempalace_list_wings
mempalace_list_rooms --wing "News Intelligence"

# Search for relevant existing knowledge
mempalace_search --query "news intelligence" --limit 10
mempalace_search --query "rss collector" --wing "News Intelligence" --limit 5
mempalace_search --query "storyline" --wing "News Intelligence" --limit 5
mempalace_search --query "entity extraction" --wing "News Intelligence" --limit 5
```

## Phase 4: Development Workflow
Establish a cyclic workflow for local development and deployment:

### 4.1 Pre-Change Analysis
1. Use repomix to examine target areas before modification
2. Search MemPalace for related historical decisions
3. Check current git status and recent commits

### 4.2 Local Development
1. Make changes in `/home/pete/Documents/projects/News Intelligence/`
2. Test locally if possible
3. Use repomix to verify changes are captured correctly

### 4.3 Deployment to Widow
1. Use rsync to synchronize changes:
   ```bash
   rsync -avz --progress \
     --exclude='.git/' --exclude='__pycache__/' --exclude='*.pyc' \
     /home/pete/Documents/projects/News Intelligence/ \
     widow:/home/pete/Documents/projects/News Intelligence/
   ```
2. Verify sync completion

### 4.4 Post-Deployment Verification
1. Use repomix on Widow to verify deployed code matches source
2. Run basic health checks on Widow
3. Update MemPalace with any new discoveries

## Phase 5: Targeted Investigations
For specific areas of interest:

### 5.1 Domain Configuration Analysis
```bash
# Analyze all domain configurations
repomix --style xml --output domains.xml api/config/domains/

# Check MemPalace for domain-related decisions
mempalace_search --query "domain.*yaml" --wing "News Intelligence" --limit 15
```

### 5.2 Service Deep Dives
```bash
# Example: Article Entity Extraction Service
repomix --style xml --output entity_extraction.xml \
  api/services/article_entity_extraction_service.py \
  api/shared/services/llm_service.py \
  api/shared/services/ollama_model_caller.py

# Search for related memories
mempalace_search --query "entity extraction" --wing "News Intelligence" --limit 10
```

### 5.3 Configuration Validation
```bash
# Check key configuration files
repomix --style xml --output config_check.xml \
  api/config/settings.py \
  api/config/paths.py \
  api/config/database_targets.py \
  api/config/orchestrator_governance.yaml
```

## Phase 6: Knowledge Capture
After investigations or changes, update MemPalace:
```bash
# Example: Store findings about a specific component
# This would use MemPalace MCP tools to create/update memories
mempalace_add_drawer --wing "News Intelligence" --room "backend" --drawer "investigation_findings_$(date +%Y%m%d)"
```

## Expected Outcomes
1. Comprehensive understanding of codebase structure via repomix outputs
2. Leveraged institutional knowledge from MemPalace
3. Efficient development cycle with local editing and Widow deployment
4. Continuous knowledge capture in MemPalace for team reference
5. Ability to quickly investigate specific components or changes

## Tools Utilization Summary
- **Repomix**: Codebase analysis, change tracking, pre/post-deployment verification
- **MemPalace MCP**: Institutional knowledge storage/retrieval, team collaboration, decision tracking
- **Rsync**: Local-to-Widow synchronization for development/deployment
- **Git**: Version control and change tracking

This approach creates a tight integration between code analysis, knowledge management, and development workflow specifically tailored to the News Intelligence system's development model.