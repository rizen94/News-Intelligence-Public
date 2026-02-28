/**
 * Global Error Handler
 * Catches and logs all unhandled errors
 * Provides centralized error handling
 */

import loggingService from './loggingService';

class ErrorHandler {
  private initialized: boolean = false;

  /**
   * Initialize global error handlers
   */
  initialize(): void {
    if (this.initialized) {
      return;
    }

    // Handle unhandled JavaScript errors and resource loading errors
    window.addEventListener('error', (event) => {
      // Check if it's a resource loading error
      const target = event.target;
      if (target && target instanceof HTMLElement) {
        const tagName = target.tagName;
        if (tagName === 'IMG' || tagName === 'SCRIPT' || tagName === 'LINK') {
          this.handleResourceError(target);
          return;
        }
      }

      // Otherwise, it's a JavaScript error
      this.handleError({
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error,
      });
    }, true); // Use capture phase to catch resource errors

    // Handle unhandled promise rejections
    window.addEventListener('unhandledrejection', (event) => {
      this.handleUnhandledRejection(event.reason);
    });

    this.initialized = true;
    loggingService.info('Global error handler initialized');
  }

  /**
   * Handle JavaScript errors
   */
  private handleError(errorInfo: {
    message: string;
    filename?: string;
    lineno?: number;
    colno?: number;
    error?: Error;
  }): void {
    const error = errorInfo.error || new Error(errorInfo.message);

    loggingService.error(
      `Unhandled JavaScript Error: ${errorInfo.message}`,
      error,
      {
        type: 'javascript_error',
        filename: errorInfo.filename,
        lineno: errorInfo.lineno,
        colno: errorInfo.colno,
        url: window.location.href,
      },
    );
  }

  /**
   * Handle unhandled promise rejections
   */
  private handleUnhandledRejection(reason: any): void {
    const error = reason instanceof Error
      ? reason
      : new Error(String(reason));

    loggingService.error(
      `Unhandled Promise Rejection: ${error.message}`,
      error,
      {
        type: 'unhandled_promise_rejection',
        reason: reason,
        url: window.location.href,
      },
    );
  }

  /**
   * Handle resource loading errors
   */
  private handleResourceError(element: HTMLElement): void {
    const tagName = element.tagName.toLowerCase();
    const src = (element as HTMLImageElement).src ||
                (element as HTMLLinkElement).href ||
                (element as HTMLScriptElement).src ||
                'unknown';

    loggingService.warn(
      `Resource loading error: ${tagName} failed to load`,
      {
        type: 'resource_error',
        tagName,
        src,
        url: window.location.href,
      },
    );
  }

  /**
   * Handle API errors
   */
  handleApiError(error: any, context?: Record<string, any>): void {
    const errorMessage = error?.response?.data?.message ||
                        error?.message ||
                        'Unknown API error';

    const status = error?.response?.status;
    const url = error?.config?.url;

    loggingService.error(
      `API Error: ${errorMessage}`,
      error,
      {
        type: 'api_error',
        status,
        url,
        method: error?.config?.method,
        ...context,
      },
    );
  }

  /**
   * Handle network errors
   */
  handleNetworkError(error: any, context?: Record<string, any>): void {
    loggingService.error(
      `Network Error: ${error.message || 'Connection failed'}`,
      error,
      {
        type: 'network_error',
        ...context,
      },
    );
  }

  /**
   * Handle validation errors
   */
  handleValidationError(field: string, message: string, value?: any): void {
    loggingService.warn(
      `Validation Error: ${field} - ${message}`,
      {
        type: 'validation_error',
        field,
        message,
        value: value ? String(value).substring(0, 100) : undefined,
      },
    );
  }

  /**
   * Handle timeout errors
   */
  handleTimeoutError(operation: string, timeout: number): void {
    loggingService.warn(
      `Timeout Error: ${operation} exceeded ${timeout}ms`,
      {
        type: 'timeout_error',
        operation,
        timeout,
      },
    );
  }
}

// Export singleton instance
export const errorHandler = new ErrorHandler();

// Auto-initialize
if (typeof window !== 'undefined') {
  errorHandler.initialize();
}

export default errorHandler;

