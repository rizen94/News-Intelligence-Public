/**
 * Error Boundary Component
 * Catches React component errors and provides error UI
 * Includes comprehensive error logging
 */

import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Box, Typography, Button, Paper, Alert } from '@mui/material';
import { ErrorOutline, Refresh, Home } from '@mui/icons-material';
import loggingService from '../../services/loggingService';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  errorId: string | null;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // Generate unique error ID
    const errorId = `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    return {
      hasError: true,
      error,
      errorId,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log error with full context
    loggingService.logComponentError({
      error,
      component: errorInfo.componentStack?.split('\n')[1]?.trim() || 'Unknown',
      props: this.props,
      state: this.state,
    });

    // Log critical error
    loggingService.critical(
      `React Error Boundary caught error: ${error.message}`,
      error,
      {
        errorId: this.state.errorId,
        componentStack: errorInfo.componentStack,
        errorBoundary: true,
      }
    );

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    this.setState({
      errorInfo,
    });
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
    });

    // Log recovery
    loggingService.info('Error boundary reset - user attempted recovery');
  };

  handleGoHome = (): void => {
    window.location.href = '/';
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback;
      }

      // Default error UI
      return (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            padding: 3,
            backgroundColor: '#f5f5f5',
          }}
        >
          <Paper
            elevation={3}
            sx={{
              maxWidth: 600,
              width: '100%',
              padding: 4,
            }}
          >
            <Box sx={{ textAlign: 'center', mb: 3 }}>
              <ErrorOutline sx={{ fontSize: 64, color: 'error.main', mb: 2 }} />
              <Typography variant="h4" gutterBottom>
                Something went wrong
              </Typography>
              <Typography variant="body1" color="text.secondary" sx={{ mb: 2 }}>
                We're sorry, but something unexpected happened. Our team has been notified.
              </Typography>
              {this.state.errorId && (
                <Typography variant="caption" color="text.secondary">
                  Error ID: {this.state.errorId}
                </Typography>
              )}
            </Box>

            {import.meta.env.DEV && this.state.error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                <Typography variant="subtitle2" gutterBottom>
                  {this.state.error.name}: {this.state.error.message}
                </Typography>
                {this.state.error.stack && (
                  <Box
                    component="pre"
                    sx={{
                      fontSize: '0.75rem',
                      overflow: 'auto',
                      maxHeight: 200,
                      mt: 1,
                    }}
                  >
                    {this.state.error.stack}
                  </Box>
                )}
              </Alert>
            )}

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
              <Button
                variant="contained"
                startIcon={<Refresh />}
                onClick={this.handleReset}
              >
                Try Again
              </Button>
              <Button
                variant="outlined"
                startIcon={<Home />}
                onClick={this.handleGoHome}
              >
                Go Home
              </Button>
            </Box>

            {import.meta.env.DEV && this.state.errorInfo && (
              <Box sx={{ mt: 3 }}>
                <Typography variant="subtitle2" gutterBottom>
                  Component Stack:
                </Typography>
                <Box
                  component="pre"
                  sx={{
                    fontSize: '0.75rem',
                    overflow: 'auto',
                    maxHeight: 200,
                    backgroundColor: '#f5f5f5',
                    padding: 1,
                    borderRadius: 1,
                  }}
                >
                  {this.state.errorInfo.componentStack}
                </Box>
              </Box>
            )}
          </Paper>
        </Box>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

