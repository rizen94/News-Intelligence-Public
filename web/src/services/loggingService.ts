/**
 * Production Logging Service
 * Structured logging for production and development environments
 * Includes error tracking, performance monitoring, and user action logging
 */

export enum LogLevel {
  DEBUG = 'debug',
  INFO = 'info',
  WARN = 'warn',
  ERROR = 'error',
  CRITICAL = 'critical',
}

export interface LogEntry {
  level: LogLevel;
  message: string;
  timestamp: string;
  context?: Record<string, any>;
  error?: Error;
  userId?: string;
  sessionId?: string;
  url?: string;
  userAgent?: string;
}

export interface ErrorContext {
  error: Error;
  component?: string;
  action?: string;
  props?: any;
  state?: any;
  userId?: string;
  url?: string;
}

class LoggingService {
  private sessionId: string;
  private userId: string | null = null;
  private logBuffer: LogEntry[] = [];
  private maxBufferSize = 100;
  private isProduction: boolean;
  private enableRemoteLogging: boolean = false;
  private remoteLoggingEndpoint: string = '/api/system_monitoring/logs';

  constructor() {
    this.sessionId = this.generateSessionId();
    this.isProduction = import.meta.env.PROD;
    this.enableRemoteLogging = this.isProduction;

    // Load user ID from storage if available
    if (typeof window !== 'undefined') {
      this.userId = localStorage.getItem('userId') || null;
    }

    // Flush logs periodically
    if (this.enableRemoteLogging) {
      setInterval(() => this.flushLogs(), 30000); // Every 30 seconds
    }

    // Flush logs before page unload
    if (typeof window !== 'undefined') {
      window.addEventListener('beforeunload', () => this.flushLogs());
    }
  }

  private generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private createLogEntry(
    level: LogLevel,
    message: string,
    context?: Record<string, any>,
    error?: Error,
  ): LogEntry {
    return {
      level,
      message,
      timestamp: new Date().toISOString(),
      context,
      error: error ? {
        name: error.name,
        message: error.message,
        stack: error.stack,
      } as Error : undefined,
      userId: this.userId || undefined,
      sessionId: this.sessionId,
      url: typeof window !== 'undefined' ? window.location.href : undefined,
      userAgent: typeof navigator !== 'undefined' ? navigator.userAgent : undefined,
    };
  }

  /**
   * Log a debug message (development only)
   */
  debug(message: string, context?: Record<string, any>): void {
    if (!this.isProduction) {
      const entry = this.createLogEntry(LogLevel.DEBUG, message, context);
      this.logBuffer.push(entry);
      console.debug(`[DEBUG] ${message}`, context || '');
    }
  }

  /**
   * Log an info message
   */
  info(message: string, context?: Record<string, any>): void {
    const entry = this.createLogEntry(LogLevel.INFO, message, context);
    this.logBuffer.push(entry);

    if (!this.isProduction) {
      console.log(`[INFO] ${message}`, context || '');
    }

    this.checkBufferSize();
  }

  /**
   * Log a warning
   */
  warn(message: string, context?: Record<string, any>): void {
    const entry = this.createLogEntry(LogLevel.WARN, message, context);
    this.logBuffer.push(entry);

    console.warn(`[WARN] ${message}`, context || '');

    // Send warnings to remote in production
    if (this.enableRemoteLogging) {
      this.sendLogToRemote(entry);
    }

    this.checkBufferSize();
  }

  /**
   * Log an error
   */
  error(message: string, error?: Error, context?: Record<string, any>): void {
    const entry = this.createLogEntry(LogLevel.ERROR, message, context, error);
    this.logBuffer.push(entry);

    console.error(`[ERROR] ${message}`, error || context || '');

    // Always send errors to remote
    if (this.enableRemoteLogging) {
      this.sendLogToRemote(entry);
    }

    this.checkBufferSize();
  }

  /**
   * Log a critical error (always sent to remote)
   */
  critical(message: string, error?: Error, context?: Record<string, any>): void {
    const entry = this.createLogEntry(LogLevel.CRITICAL, message, context, error);
    this.logBuffer.push(entry);

    console.error(`[CRITICAL] ${message}`, error || context || '');

    // Always send critical errors immediately
    this.sendLogToRemote(entry, true);

    this.checkBufferSize();
  }

  /**
   * Log user actions for analytics
   */
  logUserAction(action: string, details?: Record<string, any>): void {
    this.info(`User Action: ${action}`, {
      type: 'user_action',
      action,
      ...details,
    });
  }

  /**
   * Log API calls
   */
  logApiCall(
    method: string,
    url: string,
    status: number,
    duration: number,
    error?: Error,
  ): void {
    const context = {
      type: 'api_call',
      method,
      url,
      status,
      duration,
    };

    if (error || status >= 400) {
      this.error(`API Error: ${method} ${url}`, error, context);
    } else if (duration > 1000) {
      this.warn(`Slow API Call: ${method} ${url} took ${duration}ms`, context);
    } else {
      this.debug(`API Call: ${method} ${url}`, context);
    }
  }

  /**
   * Log performance metrics
   */
  logPerformance(operation: string, duration: number, context?: Record<string, any>): void {
    const perfContext = {
      type: 'performance',
      operation,
      duration,
      ...context,
    };

    if (duration > 1000) {
      this.warn(`Slow Operation: ${operation} took ${duration}ms`, perfContext);
    } else {
      this.debug(`Performance: ${operation}`, perfContext);
    }
  }

  /**
   * Log React component errors
   */
  logComponentError(errorContext: ErrorContext): void {
    const { error, component, action, props, state } = errorContext;

    this.error(
      `Component Error in ${component || 'Unknown'}`,
      error,
      {
        type: 'component_error',
        component,
        action,
        props: this.sanitizeForLogging(props),
        state: this.sanitizeForLogging(state),
      },
    );
  }

  /**
   * Sanitize data for logging (remove sensitive info, avoid circular refs)
   */
  private sanitizeForLogging(data: any, seen: WeakSet<object> = new WeakSet()): any {
    if (!data || typeof data !== 'object') {
      return data;
    }
    if (seen.has(data)) {
      return '[Circular]';
    }
    // Error objects often have circular refs - represent simply
    if (data instanceof Error) {
      return { name: data.name, message: data.message };
    }
    seen.add(data);

    const sensitiveKeys = ['password', 'token', 'apiKey', 'secret', 'authorization'];
    const sanitized = Array.isArray(data) ? [...data] : { ...data };

    for (const key in sanitized) {
      if (Object.prototype.hasOwnProperty.call(sanitized, key)) {
        if (sensitiveKeys.some(sk => key.toLowerCase().includes(sk))) {
          sanitized[key] = '[REDACTED]';
        } else if (typeof sanitized[key] === 'object' && sanitized[key] !== null) {
          sanitized[key] = this.sanitizeForLogging(sanitized[key], seen);
        }
      }
    }

    return sanitized;
  }

  /**
   * Send log entry to remote server
   */
  private async sendLogToRemote(entry: LogEntry, immediate: boolean = false): Promise<void> {
    if (!this.enableRemoteLogging) return;

    try {
      const response = await fetch(this.remoteLoggingEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(entry),
        // Don't wait for response if not immediate
        signal: immediate ? undefined : AbortSignal.timeout(2000),
      });

      if (!response.ok && immediate) {
        console.error('Failed to send log to remote:', response.status);
      }
    } catch (error) {
      // Silently fail for non-critical logs
      if (immediate) {
        console.error('Error sending log to remote:', error);
      }
    }
  }

  /**
   * Flush all buffered logs to remote
   */
  async flushLogs(): Promise<void> {
    if (!this.enableRemoteLogging || this.logBuffer.length === 0) {
      return;
    }

    const logsToSend = [...this.logBuffer];
    this.logBuffer = [];

    try {
      await fetch(this.remoteLoggingEndpoint + '/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ logs: logsToSend }),
        signal: AbortSignal.timeout(5000),
      });
    } catch (error) {
      // Re-add logs to buffer if send failed
      this.logBuffer.unshift(...logsToSend);
      // Keep only recent logs
      if (this.logBuffer.length > this.maxBufferSize) {
        this.logBuffer = this.logBuffer.slice(-this.maxBufferSize);
      }
    }
  }

  /**
   * Check buffer size and flush if needed
   */
  private checkBufferSize(): void {
    if (this.logBuffer.length >= this.maxBufferSize) {
      // Remove oldest logs, keep the most recent
      this.logBuffer = this.logBuffer.slice(-this.maxBufferSize);

      // Flush if remote logging is enabled
      if (this.enableRemoteLogging) {
        this.flushLogs().catch(() => {
          // Silently fail - logs are already trimmed
        });
      }
    }
  }

  /**
   * Get recent logs (for debugging)
   */
  getRecentLogs(level?: LogLevel, limit: number = 50): LogEntry[] {
    let logs = [...this.logBuffer];

    if (level) {
      logs = logs.filter(log => log.level === level);
    }

    return logs.slice(-limit);
  }

  /**
   * Clear log buffer
   */
  clearLogs(): void {
    this.logBuffer = [];
  }

  /**
   * Set user ID for logging
   */
  setUserId(userId: string): void {
    this.userId = userId;
    if (typeof window !== 'undefined') {
      localStorage.setItem('userId', userId);
    }
  }

  /**
   * Get session ID
   */
  getSessionId(): string {
    return this.sessionId;
  }
}

// Export singleton instance
export const loggingService = new LoggingService();

// Make available globally in development
if (import.meta.env.DEV && typeof window !== 'undefined') {
  (window as any).loggingService = loggingService;
}

export default loggingService;

