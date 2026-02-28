/**
 * Debug Helper Utilities
 * Industry-standard debugging tools for frontend development
 * Based on Stack Overflow best practices and professional workflows
 */

interface DebugConfig {
  enabled: boolean;
  logLevel: 'error' | 'warn' | 'info' | 'debug';
  trackPerformance: boolean;
  trackApiCalls: boolean;
  trackStateChanges: boolean;
}

class DebugHelper {
  private config: DebugConfig;
  private performanceMarks: Map<string, number> = new Map();
  private apiCallLog: Array<{
    url: string;
    method: string;
    status?: number;
    duration: number;
    timestamp: number;
  }> = [];

  constructor() {
    this.config = {
      enabled: import.meta.env.DEV,
      logLevel: 'debug',
      trackPerformance: true,
      trackApiCalls: true,
      trackStateChanges: true,
    };
  }

  /**
   * Log API calls with detailed information
   * Stack Overflow tip: Always log request/response for debugging
   */
  logApiCall(
    url: string,
    method: string,
    status?: number,
    duration?: number,
    error?: any,
  ): void {
    if (!this.config.enabled || !this.config.trackApiCalls) return;

    const logEntry = {
      url,
      method,
      status,
      duration: duration || 0,
      timestamp: Date.now(),
    };

    this.apiCallLog.push(logEntry);

    // Keep only last 100 calls
    if (this.apiCallLog.length > 100) {
      this.apiCallLog.shift();
    }

    if (error) {
      console.error('❌ API Error:', {
        url,
        method,
        error: error.message,
        status: error.response?.status,
        data: error.response?.data,
      });
    } else {
      console.log(`🌐 ${method} ${url}`, {
        status,
        duration: duration ? `${duration.toFixed(2)}ms` : 'N/A',
        timestamp: new Date().toISOString(),
      });
    }
  }

  /**
   * Log state changes in components
   * React best practice: Track state mutations
   */
  logStateChange(
    component: string,
    stateName: string,
    prevValue: any,
    nextValue: any,
  ): void {
    if (!this.config.enabled || !this.config.trackStateChanges) return;

    console.log(`🔄 ${component}.${stateName} changed:`, {
      prev: prevValue,
      next: nextValue,
      timestamp: new Date().toISOString(),
    });
  }

  /**
   * Measure performance of functions
   * Performance debugging standard
   */
  measurePerformance<T>(label: string, fn: () => T): T {
    if (!this.config.enabled || !this.config.trackPerformance) {
      return fn();
    }

    const start = performance.now();
    const result = fn();
    const end = performance.now();
    const duration = end - start;

    console.log(`⏱️ ${label}: ${duration.toFixed(2)}ms`);

    // Warn if operation takes too long
    if (duration > 100) {
      console.warn(`⚠️ Slow operation detected: ${label} took ${duration.toFixed(2)}ms`);
    }

    return result;
  }

  /**
   * Async performance measurement
   */
  async measurePerformanceAsync<T>(
    label: string,
    fn: () => Promise<T>,
  ): Promise<T> {
    if (!this.config.enabled || !this.config.trackPerformance) {
      return fn();
    }

    const start = performance.now();
    const result = await fn();
    const end = performance.now();
    const duration = end - start;

    console.log(`⏱️ ${label}: ${duration.toFixed(2)}ms`);

    if (duration > 1000) {
      console.warn(`⚠️ Slow async operation: ${label} took ${duration.toFixed(2)}ms`);
    }

    return result;
  }

  /**
   * Start a performance mark
   */
  startMark(label: string): void {
    if (!this.config.enabled) return;
    this.performanceMarks.set(label, performance.now());
    performance.mark(label);
  }

  /**
   * End a performance mark and log duration
   */
  endMark(label: string): number | null {
    if (!this.config.enabled) return null;

    const startTime = this.performanceMarks.get(label);
    if (!startTime) {
      console.warn(`⚠️ No start mark found for: ${label}`);
      return null;
    }

    const duration = performance.now() - startTime;
    this.performanceMarks.delete(label);
    performance.mark(`${label}-end`);
    performance.measure(label, label, `${label}-end`);

    console.log(`📊 ${label}: ${duration.toFixed(2)}ms`);
    return duration;
  }

  /**
   * Check network status
   * Useful for debugging connection issues
   */
  async checkNetworkStatus(apiUrl?: string): Promise<boolean> {
    try {
      const url = apiUrl || window.location.origin;
      const response = await fetch(`${url}/api/v4/system_monitoring/health`, {
        method: 'HEAD',
        cache: 'no-cache',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch (error) {
      console.error('❌ Network check failed:', error);
      return false;
    }
  }

  /**
   * Get API call statistics
   * Useful for performance analysis
   */
  getApiCallStats(): {
    total: number;
    averageDuration: number;
    errors: number;
    slowCalls: number;
    } {
    const calls = this.apiCallLog;
    const total = calls.length;
    const durations = calls.map((c) => c.duration).filter((d) => d > 0);
    const averageDuration =
      durations.length > 0
        ? durations.reduce((a, b) => a + b, 0) / durations.length
        : 0;
    const errors = calls.filter((c) => !c.status || c.status >= 400).length;
    const slowCalls = calls.filter((c) => c.duration > 1000).length;

    return {
      total,
      averageDuration: Math.round(averageDuration),
      errors,
      slowCalls,
    };
  }

  /**
   * Log component render information
   * React DevTools alternative for debugging
   */
  logRender(componentName: string, props?: any, state?: any): void {
    if (!this.config.enabled) return;

    console.group(`🎨 ${componentName} rendered`);
    if (props) console.log('Props:', props);
    if (state) console.log('State:', state);
    console.log('Timestamp:', new Date().toISOString());
    console.groupEnd();
  }

  /**
   * Monitor localStorage changes
   * Useful for debugging persistence issues
   */
  monitorLocalStorage(): void {
    if (!this.config.enabled) return;

    const originalSetItem = localStorage.setItem;
    const originalRemoveItem = localStorage.removeItem;
    const originalClear = localStorage.clear;

    localStorage.setItem = function(key: string, value: string) {
      console.log('💾 localStorage.setItem:', { key, value });
      originalSetItem.apply(this, [key, value]);
    };

    localStorage.removeItem = function(key: string) {
      console.log('🗑️ localStorage.removeItem:', key);
      originalRemoveItem.apply(this, [key]);
    };

    localStorage.clear = function() {
      console.log('🧹 localStorage.clear');
      originalClear.apply(this);
    };
  }

  /**
   * Monitor window events
   * Useful for debugging user interactions
   */
  monitorWindowEvents(): void {
    if (!this.config.enabled) return;

    const events = ['resize', 'scroll', 'focus', 'blur'];
    events.forEach((event) => {
      window.addEventListener(event, (e) => {
        console.log(`🪟 Window event: ${event}`, e);
      });
    });
  }

  /**
   * Get debug information summary
   * Useful for bug reports
   */
  getDebugInfo(): {
    userAgent: string;
    viewport: { width: number; height: number };
    localStorage: Record<string, string>;
    apiStats: ReturnType<typeof this.getApiCallStats>;
    timestamp: string;
    } {
    const localStorageData: Record<string, string> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key) {
        localStorageData[key] = localStorage.getItem(key) || '';
      }
    }

    return {
      userAgent: navigator.userAgent,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
      localStorage: localStorageData,
      apiStats: this.getApiCallStats(),
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Export debug information
   * Useful for sharing with team
   */
  exportDebugInfo(): string {
    const info = this.getDebugInfo();
    return JSON.stringify(info, null, 2);
  }

  /**
   * Clear all debug logs
   */
  clearLogs(): void {
    this.apiCallLog = [];
    this.performanceMarks.clear();
    console.clear();
  }

  /**
   * Enable/disable debugging
   */
  setEnabled(enabled: boolean): void {
    this.config.enabled = enabled;
    console.log(`🔧 Debug mode ${enabled ? 'enabled' : 'disabled'}`);
  }

  /**
   * Set log level
   */
  setLogLevel(level: DebugConfig['logLevel']): void {
    this.config.logLevel = level;
    console.log(`🔧 Log level set to: ${level}`);
  }
}

// Export singleton instance
export const debugHelper = new DebugHelper();

// Auto-initialize in development
if (import.meta.env.DEV) {
  // Make debugHelper available globally for console access
  (window as any).debugHelper = debugHelper;

  // Monitor localStorage by default
  debugHelper.monitorLocalStorage();

  console.log(
    '%c🐛 Debug Helper Active',
    'color: #4CAF50; font-size: 16px; font-weight: bold;',
  );
  console.log('Access debug tools with: window.debugHelper');
  console.log('Available methods:', Object.getOwnPropertyNames(Object.getPrototypeOf(debugHelper)).filter(name => name !== 'constructor'));
}

export default debugHelper;

