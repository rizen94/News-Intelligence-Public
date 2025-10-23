# Cursor AI Workflow - Methodology Enforcement

## 🎯 **Your Role as Human Developer**

When vibecoding with Cursor AI, you need to be the **enforcement gatekeeper**. Here's your checklist:

### **Before Starting Any AI Session**
```bash
# 1. Check current system status
./scripts/enforce_methodology.sh status

# 2. Verify you're on master branch
git branch --show-current

# 3. Ensure working directory is clean
git status

# 4. Start AI session properly
./scripts/ai_session_start.sh "Feature: [Your description]"
```

### **During AI Development Session**
- **Review every change** the AI makes before proceeding
- **Ask AI to explain reasoning** for each modification
- **Test functionality** after each significant change
- **Validate** that changes don't break existing features

### **After AI Session Completes**
```bash
# 1. Run comprehensive validation
./scripts/enforce_methodology.sh check

# 2. Test all affected functionality
./scripts/test_pipeline.sh

# 3. Review all changes
git diff master

# 4. Decide: Promote or Rollback
./scripts/ai_session_promote.sh
# OR
./scripts/ai_session_rollback.sh
```

---

## 🤖 **AI Assistant Responsibilities**

### **What I Will Do:**
1. **Always start sessions properly** using the enforcement scripts
2. **Explain reasoning** for every change I make
3. **Ask for your approval** before proceeding with major changes
4. **Document all changes** in the session log
5. **Run validation checks** after making changes
6. **Respect the production branch** - never work directly on it

### **What I Will NOT Do:**
1. **Never work directly on master** without proper session setup
2. **Never promote changes** without your explicit approval
3. **Never skip validation steps**
4. **Never make changes** without explaining the reasoning
5. **Never break existing functionality** without your knowledge

---

## 📋 **Cursor Session Checklist**

### **Pre-Session Setup** (Your Responsibility)
- [ ] Run `./scripts/enforce_methodology.sh status`
- [ ] Verify on master branch
- [ ] Ensure working directory clean
- [ ] Start AI session: `./scripts/ai_session_start.sh "Description"`

### **During Session** (Both Our Responsibility)
- [ ] AI explains each change before making it
- [ ] Human reviews and approves each change
- [ ] AI documents changes in session log
- [ ] Human tests functionality after significant changes
- [ ] Both validate no breaking changes

### **Post-Session** (Your Responsibility)
- [ ] Run `./scripts/enforce_methodology.sh check`
- [ ] Test all affected functionality manually
- [ ] Review `git diff master` for all changes
- [ ] Decide: Promote or Rollback
- [ ] Update session log with decision

---

## 🚨 **Critical Enforcement Points**

### **1. Session Boundaries**
```bash
# ALWAYS start with this:
./scripts/ai_session_start.sh "Feature: [Description]"

# NEVER let AI work without proper session setup
# NEVER skip the human approval gate
```

### **2. Change Validation**
```bash
# After each significant change:
./scripts/enforce_methodology.sh check

# Before session ends:
./scripts/test_pipeline.sh
```

### **3. Human Approval Gate**
```bash
# ALWAYS review before promoting:
git diff master

# ALWAYS test manually:
curl http://localhost:8000/api/health/
curl http://localhost:80

# ALWAYS decide explicitly:
./scripts/ai_session_promote.sh
# OR
./scripts/ai_session_rollback.sh
```

---

## 🔧 **Quick Commands for Cursor Sessions**

### **Start New AI Session**
```bash
./scripts/ai_session_start.sh "Feature: Add new component"
```

### **Check Session Status**
```bash
./scripts/enforce_methodology.sh status
```

### **Validate Changes**
```bash
./scripts/enforce_methodology.sh check
```

### **End Session (Your Choice)**
```bash
# Promote to master
./scripts/ai_session_promote.sh

# OR Rollback entire session
./scripts/ai_session_rollback.sh
```

---

## 📊 **Session Documentation**

### **AI_SESSION_LOG.md** (Auto-created)
This file tracks:
- Session intent and description
- All changes made by AI
- AI reasoning for each change
- Human validation checklist
- Promotion decision

### **Your Validation Checklist**
- [ ] All changes reviewed by human
- [ ] All functionality tested manually
- [ ] No breaking changes detected
- [ ] Documentation updated appropriately
- [ ] System integration validated

---

## 🎯 **Example Cursor Session**

### **1. You Start Session**
```bash
./scripts/ai_session_start.sh "Feature: Add new dashboard widget"
```

### **2. AI Makes Changes**
- AI explains: "I'm adding a new React component for the dashboard"
- You review: "Looks good, proceed"
- AI makes changes and documents them

### **3. AI Continues**
- AI explains: "I'm updating the API to support the new widget"
- You review: "Make sure it doesn't break existing endpoints"
- AI makes changes and validates

### **4. Session Ends**
```bash
# You run validation
./scripts/enforce_methodology.sh check

# You test manually
curl http://localhost:8000/api/health/
curl http://localhost:80

# You decide
./scripts/ai_session_promote.sh
```

---

## 🚨 **Red Flags to Watch For**

### **AI Trying to Skip Steps**
- AI suggests working directly on master
- AI wants to skip validation checks
- AI doesn't explain reasoning for changes
- AI tries to promote without your approval

### **System Issues**
- Port conflicts (development + production running)
- Git working directory not clean
- System checks failing
- Breaking changes detected

### **Your Response**
- **Stop the session** immediately
- **Run diagnostics**: `./scripts/enforce_methodology.sh status`
- **Fix issues** before continuing
- **Restart session** properly if needed

---

## 🎯 **Current Status**

### **Enforcement Ready** ✅
- **Scripts Created**: AI session management tools
- **Documentation**: Complete workflow guide
- **Validation**: Comprehensive check system
- **Rollback**: Complete rollback capability

### **Your Next Steps**
1. **Test the workflow** with a small change
2. **Familiarize yourself** with the enforcement scripts
3. **Practice the validation** process
4. **Use this guide** for all future AI sessions

---

*Last Updated: $(date)*
*Status: Cursor AI Workflow Established*
*Version: 1.0*
