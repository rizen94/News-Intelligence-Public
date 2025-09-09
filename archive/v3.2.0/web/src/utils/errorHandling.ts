/**
 * Error Handling Utilities for News Intelligence System v3.0
 * Centralized error handling and logging
 */

import { APIResponse, ErrorResponse } from '../types/api';

// Error Types
export enum ErrorType {
  NETWORK = 'NETWORK_ERROR',
  API = 'API_ERROR',
  VALIDATION = 'VALIDATION_ERROR',
  AUTHENTICATION = 'AUTHENTICATION_ERROR',
  AUTHORIZATION = 'AUTHORIZATION_ERROR',
  NOT_FOUND = 'NOT_FOUND_ERROR',
  SERVER = 'SERVER_ERROR',
  UNKNOWN = 'UNKNOWN_ERROR',
}

// Custom Error Classes
export class AppError extends Error {
  constructor(
    message: string,
    public type: ErrorType,
    public code?: string,
    public details?: Record<string, any>
  ) {
    super(message);
    this.name = 'AppError';
  }
}

export class APIError extends AppError {
  constructor(
    message: string,
    public statusCode: number,
    code?: string,
    details?: Record<string, any>
  ) {
    super(message, ErrorType.API, code, details);
    this.name = 'APIError';
  }
}

export class ValidationError extends AppError {
  constructor(
    message: string,
    public field?: string,
    details?: Record<string, any>
  ) {
    super(message, ErrorType.VALIDATION, 'VALIDATION_ERROR', details);
    this.name = 'ValidationError';
  }
}

// Error Logger
export class ErrorLogger {
  private static instance: ErrorLogger;
  private errors: Array<{ error: Error; timestamp: Date; context?: any }> = [];

  static getInstance(): ErrorLogger {
    if (!ErrorLogger.instance) {
      ErrorLogger.instance = new ErrorLogger();
    }
    return ErrorLogger.instance;
  }

  log(error: Error, context?: any): void {
    const errorEntry = {
      error,
      timestamp: new Date(),
      context,
    };

    this.errors.push(errorEntry);

    // Log to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error logged:', error, context);
    }

    // In production, send to error tracking service
    if (process.env.NODE_ENV === 'production') {
      this.sendToErrorService(errorEntry);
    }
  }

  private sendToErrorService(errorEntry: { error: Error; timestamp: Date; context?: any }): void {
    // TODO: Implement error tracking service (e.g., Sentry, LogRocket)
    console.error('Production error:', errorEntry);
  }

  getErrors(): Array<{ error: Error; timestamp: Date; context?: any }> {
    return [...this.errors];
  }

  clearErrors(): void {
    this.errors = [];
  }
}

// Error Handler
export class ErrorHandler {
  private static logger = ErrorLogger.getInstance();

  static handle(error: unknown, context?: any): AppError {
    let appError: AppError;

    if (error instanceof AppError) {
      appError = error;
    } else if (error instanceof Error) {
      appError = new AppError(
        error.message,
        ErrorType.UNKNOWN,
        'UNKNOWN_ERROR',
        { originalError: error }
      );
    } else {
      appError = new AppError(
        'An unknown error occurred',
        ErrorType.UNKNOWN,
        'UNKNOWN_ERROR',
        { originalError: error }
      );
    }

    this.logger.log(appError, context);
    return appError;
  }

  static handleAPIError(response: any, context?: any): APIError {
    const errorMessage = response?.error || response?.message || 'API request failed';
    const statusCode = response?.status || 500;
    const errorCode = response?.error_code || 'API_ERROR';

    const apiError = new APIError(errorMessage, statusCode, errorCode, {
      response,
      context,
    });

    this.logger.log(apiError, context);
    return apiError;
  }

  static handleValidationError(message: string, field?: string, context?: any): ValidationError {
    const validationError = new ValidationError(message, field, context);
    this.logger.log(validationError, context);
    return validationError;
  }
}

// Error Boundary Props
export interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
  resetOnPropsChange?: boolean;
  resetKeys?: Array<string | number>;
}

// Error Recovery Utilities
export const ErrorRecovery = {
  retry: async <T>(
    fn: () => Promise<T>,
    maxRetries: number = 3,
    delay: number = 1000
  ): Promise<T> => {
    let lastError: Error;

    for (let i = 0; i < maxRetries; i++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error as Error;
        
        if (i < maxRetries - 1) {
          await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)));
        }
      }
    }

    throw lastError!;
  },

  withFallback: async <T>(
    fn: () => Promise<T>,
    fallback: T
  ): Promise<T> => {
    try {
      return await fn();
    } catch (error) {
      ErrorHandler.handle(error);
      return fallback;
    }
  },
};

// Error Message Utilities
export const ErrorMessages = {
  [ErrorType.NETWORK]: 'Network connection failed. Please check your internet connection.',
  [ErrorType.API]: 'Server error occurred. Please try again later.',
  [ErrorType.VALIDATION]: 'Please check your input and try again.',
  [ErrorType.AUTHENTICATION]: 'Please log in to continue.',
  [ErrorType.AUTHORIZATION]: 'You do not have permission to perform this action.',
  [ErrorType.NOT_FOUND]: 'The requested resource was not found.',
  [ErrorType.SERVER]: 'Server error occurred. Please try again later.',
  [ErrorType.UNKNOWN]: 'An unexpected error occurred. Please try again.',
};

export const getErrorMessage = (error: AppError): string => {
  return ErrorMessages[error.type] || ErrorMessages[ErrorType.UNKNOWN];
};

// API Response Error Checking
export const isAPIError = (response: any): response is ErrorResponse => {
  return response && response.success === false && response.error;
};

export const isAPISuccess = <T>(response: any): response is APIResponse<T> => {
  return response && response.success === true && response.data !== undefined;
};


