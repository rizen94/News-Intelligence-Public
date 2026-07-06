# News Intelligence System Investigation & Testing Plan
## Using Repomix and MemPalace MCP

## Overview
This plan outlines how to use repomix for code analysis and the MemPalace MCP service to investigate and test the News Intelligence system. The system is developed on Widow (192.168.93.101) with code synced via rsync.

## Part 1: Using Repomix for Code Analysis

### 1.1 Repository Overview
```bash
# Get a compact XML representation of key directories
repomix --style xml --output news_intelligence_summary.xml \
  --token-count-tree 300 \
  api/ api/config/ api/domains/ api/services/ api/shared/

# Get a markdown version for easier reading
repomix --style markdown --output news_intelligence_summary.md \
  --token-count-tree 200 \
  api/ api/config/ api/domains/ api/services/ api/shared/
```

### 1.2 Focused Analysis
```bash
# Analyze specific domains
repomix --style xml --output ai_domain.xml api/domains/artificial-intelligence/

# Analyze configuration
repomix --style xml --output config_analysis.xml api/config/

# Analyze services
repomix --style xml --output services_analysis.xml api/services/

# Get file statistics
repomix --no-files --token-count-tree 100 --output file_stats.json .
```

### 1.3 Change Analysis
```bash
# See what's changed in the git repo
repomix --include-diffs --style xml --output changes_since_last_commit.xml .

# See recent commit history with code
repomix --include-logs --include-logs-count 10 --style xml --output recent_changes.xml .
```

## Part 2: Using MemPalace MCP for Memory Investigation

### 2.1 Explore Memory Structure
```bash
# List all wings in MemPalace
mempalace_list_wings

# List rooms in News Intelligence wing
mempalace_list_rooms --wing "News Intelligence"

# List drawers in a specific room
mempalace_list_drawers --wing "News Intelligence" --room "backend"
```

### 2.2 Search Memories
```bash
# Search for recent News Intelligence memories
mempalace_search --query "news intelligence" --wing "News Intelligence" --limit 10

# Search for specific components
mempalace_search --query "rss collector" --wing "News Intelligence" --limit 5
mempalace_search --query "storyline" --wing "News Intelligence" --limit 5
mempalace_search --query "entity extraction" --wing "News Intelligence" --limit 5

# Search configuration files
mempalace_search --query "domain.*yaml" --wing "News Intelligence" --limit 10
```

### 2.3 Examine Specific Memories
```bash
# Get a specific memory by reading from MemPalace
# (You would need the specific memory ID from search results)
mempalace_get_drawer --wing "News Intelligence" --room "backend" --drawer "rss_collector_config"
```

## Part 3: Combined Investigation Workflow

### 3.1 Pre-Change Analysis
1. Use repomix to get current state of codebase
2. Search MemPalace for related memories and documentation
3. Review current configuration in api/config/
4. Check recent changes with git diff

### 3.2 Making Changes
1. Edit files in /home/pete/Documents/projects/News Intelligence/
2. Test changes locally
3. Use rsync to synchronize to Widow:
   ```bash
   # Example rsync command (adjust as needed)
   rsync -avz --progress --exclude='.git/' --exclude='__pycache__/' \
     /home/pete/Documents/projects/News Intelligence/ \
     widow:/home/pete/Documents/projects/News Intelligence/
   ```

### 3.3 Post-Change Verification
1. Use repomix to verify changes were captured correctly
2. Search MemPalace to see if any related memories were updated
3. Run system tests on Widow
4. Update MemPalace with new findings if needed

### 3.4 Documentation Updates
1. Update relevant documentation in docs/ directory
2. Use repomix to include updated docs in analysis package
3. Store important findings in MemPalace for future reference

## Part 4: Specific Investigation Tasks

### 4.1 Domain Configuration Analysis
```bash
# Analyze all domain configurations
repomix --style xml --output domains_config.xml api/config/domains/

# Check for recent changes in domain configs
mempalace_search --query "domain.*yaml" --wing "News Intelligence" --limit 20
```

### 4.2 Service Investigation
```bash
# Analyze a specific service (example: article_entity_extraction_service)
repomix --style xml --output entity_extraction.xml \
  api/services/article_entity_extraction_service.py \
  api/shared/services/llm_service.py \
  api/shared/services/ollama_model_caller.py

# Search for related memories
mempalace_search --query "entity extraction" --wing "News Intelligence" --limit 10
```

### 4.3 Configuration Validation
```bash
# Check configuration files
repomix --style xml --output config_validation.xml \
  api/config/settings.py \
  api/config/paths.py \
  api/config/database_targets.py \
  api/config/orchestrator_governance.yaml

# Validate against schema if available
```

### 4.4 Pipeline Analysis
```bash
# Analyze pipeline components
repomix --style xml --output pipeline_analysis.xml \
  api/shared/pipeline_article_selection.py \
  api/shared/pipeline_pass_marker.py \
  api/services/automation_manager.py \
  api/services/pipeline_schedule_service.py
```

## Part 5: Automated Investigation Scripts

Create helper scripts to combine repomix and MemPalace:

### 5.1 change_investigator.sh
```bash
#!/bin/bash
# Investigates recent changes and stores findings in MemPalace

# Get recent changes
repomix --include-diffs --include-logs-count 5 --style xml --output /tmp/changes.xml .

# Extract key information and store in MemPalace
# (Implementation would depend on MemPalace API)
```

### 5.2 domain_analyzer.sh
```bash
#!/bin/bash
# Analyzes a specific domain and stores results

DOMAIN=$1
if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <domain-name>"
  exit 1
fi

repomix --style xml --output "/tmp/${domain}_analysis.xml" \
  "api/config/domains/${DOMAIN}.yaml" \
  "api/config/domains/specs/${DOMAIN}.domain.json" \
  "api/domains/${DOMAIN}/"*

# Store results in MemPalace
```

)
This plan of an investigative approach that leverages both:
1. **Repomix** for comprehensive codebase analysis and change tracking
2. **MemPalace MCP** for storing and retrieving institutional knowledge about the system

The workflow enables:
- Understanding current state of the codebase
- Tracking changes over time
- Maintaining institutional knowledge
- Facilitating team collaboration
- Ensuring consistency between development and production environments

By using these tools together, you can effectively investigate, modify, and validate the News Intelligence system while maintaining a knowledge base of your findings.