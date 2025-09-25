// Cursor AI Workflow Integration
// This file provides automation for AI development methodology

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class AIWorkflowEnforcer {
  constructor() {
    this.sessionActive = false;
    this.sessionBranch = null;
    this.sessionLog = 'AI_SESSION_LOG.md';
    this.enforcementScripts = {
      status: './scripts/enforce_methodology.sh status',
      check: './scripts/enforce_methodology.sh check',
      start: './scripts/ai_session_start.sh',
      end: './scripts/ai_session_end.sh',
      promote: './scripts/ai_session_promote.sh',
      rollback: './scripts/ai_session_rollback.sh'
    };
  }

  // Check if AI session is active
  isSessionActive() {
    try {
      const currentBranch = execSync('git branch --show-current', { encoding: 'utf8' }).trim();
      return currentBranch.startsWith('ai-session-');
    } catch (error) {
      return false;
    }
  }

  // Get current system status
  getSystemStatus() {
    try {
      const status = execSync(this.enforcementScripts.status, { encoding: 'utf8' });
      return {
        success: true,
        status: status,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Start AI session
  startSession(description) {
    try {
      const result = execSync(`${this.enforcementScripts.start} "${description}"`, { encoding: 'utf8' });
      this.sessionActive = true;
      this.sessionBranch = execSync('git branch --show-current', { encoding: 'utf8' }).trim();
      return {
        success: true,
        result: result,
        sessionBranch: this.sessionBranch,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // End AI session
  endSession() {
    try {
      const result = execSync(this.enforcementScripts.end, { encoding: 'utf8' });
      return {
        success: true,
        result: result,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Promote session to master
  promoteSession() {
    try {
      const result = execSync(this.enforcementScripts.promote, { encoding: 'utf8' });
      this.sessionActive = false;
      this.sessionBranch = null;
      return {
        success: true,
        result: result,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Rollback session
  rollbackSession() {
    try {
      const result = execSync(this.enforcementScripts.rollback, { encoding: 'utf8' });
      this.sessionActive = false;
      this.sessionBranch = null;
      return {
        success: true,
        result: result,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Validate changes
  validateChanges() {
    try {
      const result = execSync(this.enforcementScripts.check, { encoding: 'utf8' });
      return {
        success: true,
        result: result,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Get session log
  getSessionLog() {
    try {
      if (fs.existsSync(this.sessionLog)) {
        const log = fs.readFileSync(this.sessionLog, 'utf8');
        return {
          success: true,
          log: log,
          timestamp: new Date().toISOString()
        };
      } else {
        return {
          success: false,
          error: 'Session log not found',
          timestamp: new Date().toISOString()
        };
      }
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Check for port conflicts
  checkPortConflicts() {
    try {
      const ports = ['3000', '8000', '80', '5432', '6379', '9090'];
      const conflicts = [];
      
      for (const port of ports) {
        try {
          const result = execSync(`netstat -tlnp | grep ":${port} "`, { encoding: 'utf8' });
          if (result.trim()) {
            conflicts.push(port);
          }
        } catch (error) {
          // Port not in use
        }
      }
      
      return {
        success: true,
        conflicts: conflicts,
        timestamp: new Date().toISOString()
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }

  // Get enforcement status
  getEnforcementStatus() {
    return {
      sessionActive: this.isSessionActive(),
      sessionBranch: this.sessionBranch,
      systemStatus: this.getSystemStatus(),
      portConflicts: this.checkPortConflicts(),
      timestamp: new Date().toISOString()
    };
  }
}

// Export for use in Cursor
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AIWorkflowEnforcer;
}

// Global access for Cursor
if (typeof window !== 'undefined') {
  window.AIWorkflowEnforcer = AIWorkflowEnforcer;
}
