# Development Methodology

**Last Updated**: December 2024  
**Status**: Active Development Standards

---

## 🎯 Core Principles

### 1. Environment Separation
- **DEVELOPMENT**: Local development with hot-reload, debugging, mock data
- **PRODUCTION**: Live system with real data, optimized performance, monitoring
- **NEVER**: Mix development and production environments

### 2. Git Branch Strategy
- **Master Branch**: Active development, testing, experimentation
- **Production Branch**: Stable, working version ready for production use
- **Rule**: Only promote tested, working code to production

### 3. Root Cause Analysis
- **Always**: Identify underlying system issues before applying fixes
- **Never**: Apply quick fixes without understanding the problem
- **Focus**: Configuration, security, and architecture before code changes

### 4. AI-Assisted Development
- **Session-Based**: Complete feature implementation in one AI interaction
- **Human Review**: Human validates entire session before promotion
- **Atomic Changes**: All related changes committed together
- **No Partial Promotions**: Either entire session works or entire session is rejected

---

## 🏗️ Environment Management

### Production Environment ✅ ACTIVE
```bash
# Services
Frontend: http://localhost:80 (Docker container)
API: http://localhost:8000 (Docker container)
Database: localhost:5432 (Docker container)
Cache: localhost:6379 (Docker container)
Ollama: http://localhost:11434 (User-level service)

# Status: Fully operational with real data
# Purpose: Live system for actual use
```

### Development Environment 🔧 READY
```bash
# Services (when needed)
Frontend: http://localhost:3001 (React dev server)
API: http://localhost:8001 (Development API)
Database: localhost:5433 (Development database)

# Status: Clean, ready for new features
# Purpose: Code development, debugging, component testing
```

---

## 🔄 Git Workflow

### Development Process
```bash
# 1. Start development work
git checkout master

# 2. Make changes and test thoroughly
# ... development work ...

# 3. Commit working changes
git add .
git commit -m "Feature: Description of changes"

# 4. Test thoroughly before promoting
```

### Production Promotion
```bash
# 1. Only promote when you have a WORKING, TESTED version
git checkout production

# 2. Merge the working changes from master
git merge master

# 3. Tag this as a production release
git tag -a v3.0.2 -m "Production Release: Stable working version"

# 4. Push to remote (if you have one)
git push origin production
git push origin v3.0.2
```

### Emergency Rollback
```bash
# If something breaks, rollback to last known good production version
git checkout production
git log --oneline  # Find the last good commit
git reset --hard <last-good-commit-hash>

# Or rollback master to match production
git checkout master
git reset --hard production
```

---

## 🤖 AI-Assisted Development Workflow

### Phase 1: Pre-Session Validation
```bash
# 1. Check system is in stable state
./scripts/enforce_methodology.sh check

# 2. Create session branch
git checkout -b ai-session-$(date +%Y%m%d-%H%M%S)

# 3. Document session intent
echo "AI Session: [Description of changes]" > AI_SESSION_LOG.md
```

### Phase 2: AI Development Session
- AI makes changes across multiple files
- Human reviews changes in real-time
- AI explains reasoning for each change
- Human validates each change before proceeding

### Phase 3: Post-Session Validation
```bash
# 1. Run comprehensive checks
./scripts/enforce_methodology.sh check

# 2. Test all affected functionality
./scripts/test_pipeline.sh

# 3. Validate system integration
curl http://localhost:8000/api/health/
curl http://localhost:80
```

### Phase 4: Human Approval Gate
```bash
# 1. Human reviews all changes
git diff master

# 2. Human tests functionality manually
# 3. Human approves or rejects entire session
# 4. If approved: promote to master
# 5. If rejected: rollback entire session
```

---

## 🚨 Critical Rules

### DO:
1. **Always develop on master branch**
2. **Test thoroughly before promoting to production**
3. **Commit working versions to production branch**
4. **Use production branch as your stable reference**
5. **Tag production releases with version numbers**
6. **Check high-level issues (configuration, security) before code changes**
7. **Perform root cause analysis for persistent problems**
8. **Always create session branches for AI work**
9. **Document every AI change with rationale**
10. **Validate entire session before promotion**
11. **Maintain human approval gate for all AI work**

### DON'T:
1. **Never develop directly on production branch**
2. **Never promote untested code to production**
3. **Never delete the production branch**
4. **Never force-push to production branch**
5. **Never run development and production simultaneously**
6. **Never apply quick fixes without understanding the problem**
7. **Never let AI work directly on master or production**
8. **Never promote AI changes without human validation**
9. **Never mix AI and human changes in same session**
10. **Never skip post-session validation**
11. **Never allow partial AI sessions to be promoted**

---

## 🔧 Quick Commands

### Start Development
```bash
git checkout master
# Make your changes
```

### Start AI Session
```bash
./scripts/ai_session_start.sh "Feature: [Your description]"
```

### Promote to Production
```bash
git checkout production
git merge master
git tag -a v3.0.2 -m "Production Release: New feature"
```

### End AI Session
```bash
# Promote to master
./scripts/ai_session_promote.sh

# OR Rollback entire session
./scripts/ai_session_rollback.sh
```

### Emergency Rollback
```bash
git checkout production
git reset --hard HEAD~1  # Go back one commit
```

### Check Status
```bash
git branch -v  # See all branches and their latest commits
git log --oneline -5  # See last 5 commits
./scripts/enforce_methodology.sh status
```

---

## 📋 Quality Assurance

### Before Production Promotion
- [ ] All tests pass
- [ ] No compilation errors
- [ ] No ESLint errors
- [ ] Frontend builds successfully
- [ ] API endpoints respond correctly
- [ ] Database schema is up to date
- [ ] All navigation links work
- [ ] Real data displays correctly

### Production Verification
- [ ] Frontend accessible at http://localhost:80
- [ ] API accessible at http://localhost:8000
- [ ] Database healthy and responsive
- [ ] All Docker containers running
- [ ] No port conflicts
- [ ] All services communicating correctly

### AI Session Validation
- [ ] All changes reviewed by human
- [ ] All functionality tested manually
- [ ] No breaking changes detected
- [ ] Documentation updated appropriately
- [ ] System integration validated

---

## 🎯 AI Development Best Practices

### 1. Session Scope
- **Keep sessions focused** on single features or fixes
- **Avoid massive refactoring** in single AI session
- **Break complex changes** into multiple AI sessions
- **Document session boundaries** clearly

### 2. Human Oversight
- **Review every AI change** before proceeding
- **Test functionality manually** after AI changes
- **Understand AI reasoning** for each change
- **Maintain veto power** over AI decisions

### 3. Quality Assurance
- **Run full test suite** after AI session
- **Check for regressions** in existing functionality
- **Validate system integration** after changes
- **Ensure documentation** is updated appropriately

### 4. Rollback Strategy
- **Always maintain rollback capability**
- **Document rollback steps** for each session
- **Test rollback procedure** before promoting
- **Keep session atomic** for easy rollback

---

## 📊 Session Documentation Template

### AI_SESSION_LOG.md
```markdown
# AI Development Session

## Session Information
- **Date**: $(date)
- **Branch**: ai-session-$(date +%Y%m%d-%H%M%S)
- **Human**: [Your name]
- **AI Assistant**: [AI system used]

## Session Intent
[Description of what the AI session aims to accomplish]

## Changes Made
- **File 1**: [Description of changes]
- **File 2**: [Description of changes]
- **File 3**: [Description of changes]

## AI Reasoning
[Explanation of why AI made these specific changes]

## Human Validation
- [ ] All changes reviewed by human
- [ ] All functionality tested manually
- [ ] No breaking changes detected
- [ ] Documentation updated appropriately

## Promotion Decision
- [ ] Approved for promotion to master
- [ ] Rejected - rollback required
- [ ] Requires additional changes

## Notes
[Any additional notes or concerns]
```

---

## 🔧 Enforcement Tools

### Pre-commit Hooks
```bash
# Check for compilation errors
npm run build

# Check for linting errors
npm run lint

# Check for type errors
npm run type-check
```

### Production Deployment Checklist
```bash
# 1. Verify all services are healthy
curl http://localhost:8000/api/health/

# 2. Test frontend accessibility
curl http://localhost:80

# 3. Verify database connectivity
psql -h localhost -p 5432 -U newsapp -d news_intelligence -c "SELECT 1;"

# 4. Check Docker container status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### AI Session Management Scripts
```bash
# Start AI session
./scripts/ai_session_start.sh "Feature: Add new dashboard component"

# End AI session with validation
./scripts/ai_session_end.sh

# Promote AI session to master
./scripts/ai_session_promote.sh

# Rollback AI session
./scripts/ai_session_rollback.sh

# Track all files changed by AI
./scripts/track_ai_changes.sh

# Validate AI changes don't break existing functionality
./scripts/validate_ai_changes.sh

# Generate AI session report
./scripts/generate_ai_report.sh
```

---

## 🎯 Current Status

### Production Branch ✅ STABLE
- **Status**: All TypeScript errors fixed, ESLint configured, API working
- **Docker System**: Fully operational (ports 80, 8000, 5432)
- **Database**: Schema applied, all tables created
- **Frontend**: All components working, navigation fixed

### Master Branch 🔧 DEVELOPMENT
- **Status**: Ready for new development work
- **Environment**: Clean, ready for new features

### AI Development Ready ✅
- **Session Management**: Scripts created for AI session workflow
- **Human Gates**: Approval process established
- **Rollback Strategy**: Complete rollback capability maintained
- **Documentation**: AI session logging system implemented

---

## 📚 Related Documentation

- **Coding Standards**: `docs/CODING_STYLE_GUIDE.md`
- **API Reference**: `docs/API_REFERENCE.md`
- **Deployment Guide**: `docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`

---

*Last Updated: December 2024*  
*Status: Methodology Established and Active*  
*Version: 2.0*

