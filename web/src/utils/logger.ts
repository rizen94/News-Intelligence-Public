/**
 * News Intelligence System v3.0 - Frontend Logging Utility (TypeScript)
 * Centralized logging system for consistent error handling and debugging
 */

export interface LogData {
  [key: string]: any;
}

export interface PerformanceMetadata {
  operation: string;
  duration: number;
  timestamp: number;
  metadata?: LogData;
}

export interface UserActionData {
  action: string;
  component?: string;
  data?: LogData;
}

export interface ComponentLifecycleData {
  component: string;
  event: 'mounted' | 'unmounted' | 'updated' | 'error';
  data?: LogData;
}

export interface APILogData {
  method: string;
  url: string;
  data?: LogData;
  status?: number;
  error?: Error;
}

class Logger {
  /**
   * Log informational messages
   * @param message - The log message
   * @param data - Optional data to log
   */
  static info(message: string, data?: LogData): void {
    if (process.env['NODE_ENV'] === 'development') {
      if (data) {
        console.log(`[INFO] ${message}`, data);
      } else {
        console.log(`[INFO] ${message}`);
      }
    }
    // In production, you could send to a logging service
    // this.sendToLoggingService('info', message, data);
  }

  /**
   * Log error messages
   * @param message - The error message
   * @param error - Optional error object
   */
  static error(message: string, error?: Error | LogData): void {
    if (process.env['NODE_ENV'] === 'development') {
      if (error) {
        console.error(`[ERROR] ${message}`, error);
      } else {
        console.error(`[ERROR] ${message}`);
      }
    }
    // In production, send to error tracking service
    // this.sendToErrorService(message, error);
  }

  /**
   * Log warning messages
   * @param message - The warning message
   * @param data - Optional data to log
   */
  static warn(message: string, data?: LogData): void {
    if (process.env['NODE_ENV'] === 'development') {
      if (data) {
        console.warn(`[WARN] ${message}`, data);
      } else {
        console.warn(`[WARN] ${message}`);
      }
    }
  }

  /**
   * Log debug messages (only in development)
   * @param message - The debug message
   * @param data - Optional data to log
   */
  static debug(message: string, data?: LogData): void {
    if (process.env['NODE_ENV'] === 'development') {
      if (data) {
        console.debug(`[DEBUG] ${message}`, data);
      } else {
        console.debug(`[DEBUG] ${message}`);
      }
    }
  }

  /**
   * Log API requests
   * @param method - HTTP method
   * @param url - Request URL
   * @param data - Optional request data
   */
  static apiRequest(method: string, url: string, data?: LogData): void {
    const message = `API Request: ${method.toUpperCase()} ${url}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log API responses
   * @param status - HTTP status code
   * @param url - Response URL
   * @param data - Optional response data
   */
  static apiResponse(status: number, url: string, data?: LogData): void {
    const message = `API Response: ${status} ${url}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log API errors
   * @param message - Error message
   * @param error - Error object
   * @param url - Request URL
   */
  static apiError(message: string, error: Error, url?: string): void {
    const fullMessage = url ? `${message} - ${url}` : message;
    this.error(fullMessage, error);
  }

  /**
   * Log component lifecycle events
   * @param componentName - Name of the component
   * @param event - Lifecycle event
   * @param data - Optional data
   */
  static componentLifecycle(
    componentName: string,
    event: string,
    data?: LogData,
  ): void {
    const message = `Component ${componentName}: ${event}`;
    if (data) {
      this.debug(message, data);
    } else {
      this.debug(message);
    }
  }

  /**
   * Log user actions
   * @param action - User action description
   * @param data - Optional action data
   */
  static userAction(action: string, data?: LogData): void {
    const message = `User Action: ${action}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log performance metrics
   * @param operation - Operation name
   * @param duration - Duration in milliseconds
   * @param metadata - Optional metadata
   */
  static performance(
    operation: string,
    duration: number,
    metadata?: LogData,
  ): void {
    const message = `Performance: ${operation} took ${duration}ms`;
    if (metadata) {
      this.info(message, metadata);
    } else {
      this.info(message);
    }
  }

  /**
   * Log system events
   * @param event - System event description
   * @param data - Optional event data
   */
  static systemEvent(event: string, data?: LogData): void {
    const message = `System Event: ${event}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log security events
   * @param event - Security event description
   * @param data - Optional event data
   */
  static securityEvent(event: string, data?: LogData): void {
    const message = `Security Event: ${event}`;
    if (data) {
      this.warn(message, data);
    } else {
      this.warn(message);
    }
  }

  /**
   * Log business events
   * @param event - Business event description
   * @param data - Optional event data
   */
  static businessEvent(event: string, data?: LogData): void {
    const message = `Business Event: ${event}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }
}

export default Logger;
