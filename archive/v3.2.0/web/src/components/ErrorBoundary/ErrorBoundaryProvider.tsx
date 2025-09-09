/**
 * Error Boundary Provider for News Intelligence System v3.0
 * Provides error boundary context and recovery mechanisms
 */

import React, { createContext, useContext, useState, useCallback } from 'react';
import { ErrorHandler, AppError, ErrorType } from '../utils/errorHandling';
import ErrorBoundary from './ErrorBoundary';

interface ErrorContextType {
  errors: AppError[];
  addError: (error: AppError) => void;
  clearErrors: () => void;
  clearError: (index: number) => void;
  hasErrors: boolean;
}

const ErrorContext = createContext<ErrorContextType | undefined>(undefined);

export const useErrorContext = () => {
  const context = useContext(ErrorContext);
  if (!context) {
    throw new Error('useErrorContext must be used within an ErrorBoundaryProvider');
  }
  return context;
};

interface ErrorBoundaryProviderProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error: AppError; retry: () => void }>;
}

export const ErrorBoundaryProvider: React.FC<ErrorBoundaryProviderProps> = ({
  children,
  fallback: FallbackComponent,
}) => {
  const [errors, setErrors] = useState<AppError[]>([]);

  const addError = useCallback((error: AppError) => {
    setErrors(prev => [...prev, error]);
  }, []);

  const clearErrors = useCallback(() => {
    setErrors([]);
  }, []);

  const clearError = useCallback((index: number) => {
    setErrors(prev => prev.filter((_, i) => i !== index));
  }, []);

  const handleError = useCallback((error: Error, errorInfo: React.ErrorInfo) => {
    const appError = ErrorHandler.handle(error, { errorInfo });
    addError(appError);
  }, [addError]);

  const contextValue: ErrorContextType = {
    errors,
    addError,
    clearErrors,
    clearError,
    hasErrors: errors.length > 0,
  };

  return (
    <ErrorContext.Provider value={contextValue}>
      <ErrorBoundary
        onError={handleError}
        fallback={FallbackComponent ? (
          <FallbackComponent error={errors[0] || new AppError('Unknown error', ErrorType.UNKNOWN)} retry={() => clearErrors()} />
        ) : undefined}
      >
        {children}
      </ErrorBoundary>
    </ErrorContext.Provider>
  );
};

// Global error handler
export const GlobalErrorHandler = {
  handle: (error: unknown, context?: any) => {
    const appError = ErrorHandler.handle(error, context);
    
    // In development, show error in console
    if (process.env.NODE_ENV === 'development') {
      console.error('Global error:', appError, context);
    }
    
    return appError;
  },
};

// ErrorRecovery is already defined in ../utils/errorHandling
// Import it instead of redefining it here
