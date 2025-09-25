# Cursor AI Enforcement Integration

## 🎯 **Desktop App Integration**

This file provides Cursor with enforcement rules and automation for AI-assisted development.

### **Enforcement Rules**
- **Always start AI sessions** with proper validation
- **Require human approval** for all changes
- **Block direct production changes** without proper workflow
- **Auto-validate changes** after AI modifications
- **Maintain session boundaries** and documentation

### **Automation Triggers**
- **On Cursor Start**: Check system status and show enforcement status
- **Before AI Changes**: Validate session is properly started
- **After AI Changes**: Run validation checks automatically
- **On File Save**: Check for methodology compliance
- **On Git Operations**: Enforce branch rules and session boundaries

---

## 🤖 **AI Assistant Instructions**

### **When Starting AI Work:**
1. **Check if session is started** - If not, prompt user to start session
2. **Validate system status** - Run enforcement checks
3. **Explain changes** - Always explain reasoning before making changes
4. **Ask for approval** - Get human approval before proceeding

### **When Making Changes:**
1. **Document changes** - Update session log with all modifications
2. **Run validation** - Check for breaking changes
3. **Test functionality** - Verify changes don't break existing features
4. **Maintain rollback** - Ensure rollback capability is maintained

### **When Ending AI Work:**
1. **Run final validation** - Comprehensive system checks
2. **Update session log** - Document all changes and validation results
3. **Prompt for decision** - Ask human to promote or rollback
4. **Clean up session** - Proper session termination

---

## 🚨 **Enforcement Triggers**

### **Automatic Checks:**
- **System Status**: Check on Cursor startup
- **Session Validation**: Check before AI changes
- **Change Validation**: Check after AI modifications
- **Branch Rules**: Enforce master/production branch rules
- **Port Conflicts**: Detect development/production conflicts

### **Human Prompts:**
- **Session Start**: Prompt to start AI session properly
- **Change Approval**: Ask for approval before major changes
- **Promotion Decision**: Ask to promote or rollback session
- **Validation Results**: Show validation results and ask for action

---

## 📋 **Desktop App Workflow**

### **1. Cursor Startup**
```
✅ Check system status
✅ Show enforcement status
✅ Validate current branch
✅ Check for port conflicts
✅ Display session status
```

### **2. Before AI Work**
```
⚠️  Check if session is started
⚠️  If not, prompt to start session
⚠️  Validate system status
⚠️  Check branch rules
```

### **3. During AI Work**
```
🔄 Document each change
🔄 Run validation checks
🔄 Ask for human approval
🔄 Update session log
```

### **4. After AI Work**
```
✅ Run final validation
✅ Update session log
✅ Prompt for promotion decision
✅ Clean up session
```

---

## 🔧 **Configuration Options**

### **Enforcement Levels:**
- **Strict**: All rules enforced, no exceptions
- **Moderate**: Most rules enforced, some flexibility
- **Relaxed**: Basic rules enforced, more flexibility

### **Automation Options:**
- **Auto-start sessions**: Automatically start AI sessions
- **Auto-validation**: Automatically run validation checks
- **Auto-promotion**: Automatically promote approved sessions
- **Auto-rollback**: Automatically rollback rejected sessions

### **Notification Options:**
- **Status notifications**: Show system status on startup
- **Validation notifications**: Show validation results
- **Promotion reminders**: Remind about promotion decisions
- **Rollback warnings**: Warn about rollback decisions

---

## 🎯 **Usage Instructions**

### **For Human Developer:**
1. **Open Cursor** - Enforcement status will be shown
2. **Start AI session** - Use "Start AI Session" command
3. **Work with AI** - AI will prompt for approvals
4. **End session** - Use "End AI Session" command
5. **Decide promotion** - Choose to promote or rollback

### **For AI Assistant:**
1. **Check session status** - Ensure session is started
2. **Explain changes** - Always explain before making changes
3. **Ask for approval** - Get human approval before proceeding
4. **Document changes** - Update session log with all modifications
5. **Run validation** - Check for breaking changes

---

*Last Updated: $(date)*
*Status: Cursor Desktop Integration Ready*
*Version: 1.0*
