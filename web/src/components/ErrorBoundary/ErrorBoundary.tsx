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
  isChunkLoad: boolean;
}

function isChunkLoadError(error: Error | null): boolean {
  if (!error) return false;
  const msg = `${error.name || ''} ${error.message || ''}`.toLowerCase();
  return (
    msg.includes('failed to fetch dynamically imported module') ||
    msg.includes('importing a module script failed') ||
    msg.includes('loading chunk') ||
    msg.includes('chunkloaderror') ||
    error.name === 'ChunkLoadError'
  );
}

/** Stale tab still running pre-fix Assemble UI (entity objects as React children). */
function isStaleEntityObjectRenderError(error: Error | null): boolean {
  if (!error) return false;
  const msg = `${error.message || ''}`;
  return (
    /Minified React error #31/i.test(msg) ||
    /Objects are not valid as a React child/i.test(msg) ||
    (/entity_type/i.test(msg) && /role/i.test(msg) && /object with keys/i.test(msg))
  );
}

const CHUNK_RELOAD_KEY = 'ni_chunk_reload_ts';

function maybeReloadForStaleBundle(error: Error): boolean {
  if (typeof window === 'undefined') return false;
  if (!isChunkLoadError(error) && !isStaleEntityObjectRenderError(error)) return false;
  try {
    const last = Number(sessionStorage.getItem(CHUNK_RELOAD_KEY) || '0');
    if (Date.now() - last > 15_000) {
      sessionStorage.setItem(CHUNK_RELOAD_KEY, String(Date.now()));
      window.location.reload();
      return true;
    }
  } catch {
    window.location.reload();
    return true;
  }
  return false;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      isChunkLoad: false,
    };
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    const errorId = `error_${Date.now()}_${Math.random()
      .toString(36)
      .substr(2, 9)}`;
    const chunk = isChunkLoadError(error) || isStaleEntityObjectRenderError(error);

    maybeReloadForStaleBundle(error);

    try {
      sessionStorage.setItem(
        'ni_last_boundary_error',
        JSON.stringify({
          errorId,
          message: error.message,
          name: error.name,
          at: new Date().toISOString(),
        })
      );
    } catch {
      // ignore
    }

    return {
      hasError: true,
      error,
      errorId,
      isChunkLoad: chunk,
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    try {
      loggingService.logComponentError({
        error,
        component: errorInfo.componentStack?.split('\n')[1]?.trim() || 'Unknown',
        // Never pass React element trees into the logger (circular / non-serializable).
        props: { hasChildren: Boolean(this.props.children) },
        state: {
          hasError: this.state.hasError,
          errorId: this.state.errorId,
          isChunkLoad: this.state.isChunkLoad,
        },
      });
      loggingService.critical(
        `React Error Boundary caught error: ${error.message}`,
        error,
        {
          errorId: this.state.errorId,
          componentStack: errorInfo.componentStack,
          errorBoundary: true,
          isChunkLoad: isChunkLoadError(error),
        }
      );
    } catch {
      // Logging must never take down the recovery UI.
    }

    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    this.setState({ errorInfo });
  }

  handleReset = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: null,
      isChunkLoad: false,
    });
    loggingService.info('Error boundary reset - user attempted recovery');
  };

  handleReload = (): void => {
    window.location.reload();
  };

  handleGoHome = (): void => {
    window.location.href = '/';
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      const message = this.state.error?.message || 'Unknown error';
      const chunk = this.state.isChunkLoad;

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
              <Typography variant='h4' gutterBottom>
                {chunk ? 'App update required' : 'Something went wrong'}
              </Typography>
              <Typography variant='body1' color='text.secondary' sx={{ mb: 2 }}>
                {chunk
                  ? 'This browser tab is still running an older UI build (common after a deploy). Use Reload — a normal refresh is not always enough if the tab has been open a while.'
                  : 'Unexpected error in the page. Reload usually clears it; if it persists, copy the message below.'}
              </Typography>
              {this.state.errorId && (
                <Typography variant='caption' color='text.secondary' display='block'>
                  Error ID: {this.state.errorId}
                </Typography>
              )}
            </Box>

            <Alert severity={chunk ? 'info' : 'error'} sx={{ mb: 2, textAlign: 'left' }}>
              <Typography variant='subtitle2' gutterBottom>
                {this.state.error?.name || 'Error'}
              </Typography>
              <Typography variant='body2' sx={{ wordBreak: 'break-word' }}>
                {message}
              </Typography>
            </Alert>

            <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
              <Button variant='contained' startIcon={<Refresh />} onClick={this.handleReload}>
                Reload page
              </Button>
              {!chunk && (
                <Button variant='outlined' startIcon={<Refresh />} onClick={this.handleReset}>
                  Try again
                </Button>
              )}
              <Button variant='outlined' startIcon={<Home />} onClick={this.handleGoHome}>
                Go home
              </Button>
            </Box>

            {import.meta.env.DEV && this.state.errorInfo && (
              <Box sx={{ mt: 3 }}>
                <Typography variant='subtitle2' gutterBottom>
                  Component Stack:
                </Typography>
                <Box
                  component='pre'
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
