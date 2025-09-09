import React, { Component, ErrorInfo, ReactNode } from 'react';
import {
  Box,
  Typography,
  Button,
  Paper,
  useTheme,
  useMediaQuery,
  Alert,
  AlertTitle,
  Collapse,
  IconButton
} from '@mui/material';
import {
  Error as ErrorIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon
} from '@mui/icons-material';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
  expanded: boolean;
}

class ResponsiveErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      expanded: false
    };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      errorInfo: null,
      expanded: false
    };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({
      error,
      errorInfo
    });

    // Call the onError callback if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Log error to console in development
    if (process.env.NODE_ENV === 'development') {
      console.error('Error caught by boundary:', error, errorInfo);
    }
  }

  handleRetry = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      expanded: false
    });
  };

  handleToggleExpanded = () => {
    this.setState(prevState => ({
      expanded: !prevState.expanded
    }));
  };

  render() {
    if (this.state.hasError) {
      // Custom fallback UI
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return <ErrorFallback
        error={this.state.error}
        errorInfo={this.state.errorInfo}
        onRetry={this.handleRetry}
        onToggleExpanded={this.handleToggleExpanded}
        expanded={this.state.expanded}
      />;
    }

    return this.props.children;
  }
}

interface ErrorFallbackProps {
  error: Error | null;
  errorInfo: ErrorInfo | null;
  onRetry: () => void;
  onToggleExpanded: () => void;
  expanded: boolean;
}

const ErrorFallback: React.FC<ErrorFallbackProps> = ({
  error,
  errorInfo,
  onRetry,
  onToggleExpanded,
  expanded
}) => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '200px',
        p: 2,
        width: '100%'
      }}
    >
      <Paper
        elevation={2}
        sx={{
          p: isMobile ? 2 : 3,
          maxWidth: isMobile ? '100%' : 600,
          width: '100%',
          textAlign: 'center'
        }}
      >
        <Box sx={{ mb: 2 }}>
          <ErrorIcon
            sx={{
              fontSize: isMobile ? 48 : 64,
              color: theme.palette.error.main,
              mb: 1
            }}
          />
        </Box>

        <Typography
          variant={isMobile ? 'h6' : 'h5'}
          component="h2"
          gutterBottom
          sx={{ fontWeight: 600 }}
        >
          Something went wrong
        </Typography>

        <Typography
          variant="body1"
          color="text.secondary"
          sx={{ mb: 3 }}
        >
          We encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
        </Typography>

        <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center', flexWrap: 'wrap' }}>
          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            onClick={onRetry}
            size={isMobile ? 'medium' : 'large'}
          >
            Try Again
          </Button>

          <Button
            variant="outlined"
            onClick={() => window.location.reload()}
            size={isMobile ? 'medium' : 'large'}
          >
            Refresh Page
          </Button>
        </Box>

        {process.env.NODE_ENV === 'development' && error && (
          <Box sx={{ mt: 3 }}>
            <Button
              variant="text"
              endIcon={expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
              onClick={onToggleExpanded}
              size="small"
            >
              {expanded ? 'Hide' : 'Show'} Error Details
            </Button>

            <Collapse in={expanded}>
              <Alert severity="error" sx={{ mt: 2, textAlign: 'left' }}>
                <AlertTitle>Error Details</AlertTitle>
                <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem' }}>
                  {error.toString()}
                </Typography>
                {errorInfo && (
                  <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontSize: '0.75rem', mt: 1 }}>
                    {errorInfo.componentStack}
                  </Typography>
                )}
              </Alert>
            </Collapse>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default ResponsiveErrorBoundary;

