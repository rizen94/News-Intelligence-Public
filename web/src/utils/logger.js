/**
 * News Intelligence System v3.0 - Frontend Logging Utility
 * Centralized logging system for consistent error handling and debugging
 */

class Logger {
  /**
   * Log informational messages
   * @param {string} message - The log message
   * @param {any} data - Optional data to log
   */
  static info(message, data = null) {
    if (import.meta.env.DEV) {
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
   * @param {string} message - The error message
   * @param {Error|any} error - Optional error object
   */
  static error(message, error = null) {
    if (import.meta.env.DEV) {
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
   * @param {string} message - The warning message
   * @param {any} data - Optional data to log
   */
  static warn(message, data = null) {
    if (import.meta.env.DEV) {
      if (data) {
        console.warn(`[WARN] ${message}`, data);
      } else {
        console.warn(`[WARN] ${message}`);
      }
    }
  }

  /**
   * Log debug messages (only in development)
   * @param {string} message - The debug message
   * @param {any} data - Optional data to log
   */
  static debug(message, data = null) {
    if (import.meta.env.DEV) {
      if (data) {
        console.debug(`[DEBUG] ${message}`, data);
      } else {
        console.debug(`[DEBUG] ${message}`);
      }
    }
  }

  /**
   * Log API requests
   * @param {string} method - HTTP method
   * @param {string} url - Request URL
   * @param {any} data - Optional request data
   */
  static apiRequest(method, url, data = null) {
    const message = `API Request: ${method.toUpperCase()} ${url}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log API responses
   * @param {number} status - HTTP status code
   * @param {string} url - Response URL
   * @param {any} data - Optional response data
   */
  static apiResponse(status, url, data = null) {
    const message = `API Response: ${status} ${url}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log API errors
   * @param {string} message - Error message
   * @param {Error} error - Error object
   * @param {string} url - Request URL
   */
  static apiError(message, error, url = null) {
    const fullMessage = url ? `${message} - ${url}` : message;
    this.error(fullMessage, error);
  }

  /**
   * Log component lifecycle events
   * @param {string} componentName - Name of the component
   * @param {string} event - Lifecycle event (mounted, unmounted, etc.)
   * @param {any} data - Optional data
   */
  static componentLifecycle(componentName, event, data = null) {
    const message = `Component ${componentName}: ${event}`;
    if (data) {
      this.debug(message, data);
    } else {
      this.debug(message);
    }
  }

  /**
   * Log user actions
   * @param {string} action - User action description
   * @param {any} data - Optional action data
   */
  static userAction(action, data = null) {
    const message = `User Action: ${action}`;
    if (data) {
      this.info(message, data);
    } else {
      this.info(message);
    }
  }

  /**
   * Log performance metrics
   * @param {string} operation - Operation name
   * @param {number} duration - Duration in milliseconds
   * @param {any} metadata - Optional metadata
   */
  static performance(operation, duration, metadata = null) {
    const message = `Performance: ${operation} took ${duration}ms`;
    if (metadata) {
      this.info(message, metadata);
    } else {
      this.info(message);
    }
  }
}

export default Logger;
