/**
 * Standardized Error Handler
 * Provides consistent error message formatting across all pages
 */

export interface ErrorInfo {
  message: string;
  userFriendly: string;
  actionable?: string;
}

/**
 * Convert technical errors to user-friendly messages
 */
export const formatError = (error: any): ErrorInfo => {
  // Network/Connection errors
  if (
    error?.code === 'ECONNREFUSED' ||
    error?.message?.includes('Network Error') ||
    error?.message?.includes('fetch') ||
    !error?.response
  ) {
    return {
      message: error?.message || 'Network error',
      userFriendly:
        'Cannot connect to the server. Please check your connection and try again.',
      actionable: 'Make sure the API server is running on port 8000.',
    };
  }

  // 404 Not Found
  if (error?.response?.status === 404) {
    return {
      message: error?.message || 'Not found',
      userFriendly: 'The requested resource was not found.',
      actionable: 'Please check the URL or try refreshing the page.',
    };
  }

  // 500 Server Error
  if (error?.response?.status >= 500) {
    return {
      message: error?.message || 'Server error',
      userFriendly: 'The server encountered an error. Please try again later.',
      actionable: 'If the problem persists, please check the server logs.',
    };
  }

  // 400 Bad Request
  if (error?.response?.status === 400) {
    return {
      message: error?.message || 'Invalid request',
      userFriendly:
        error?.response?.data?.detail ||
        'Invalid request. Please check your input and try again.',
    };
  }

  // Generic error
  return {
    message: error?.message || 'An error occurred',
    userFriendly:
      error?.response?.data?.detail ||
      error?.message ||
      'An unexpected error occurred. Please try again.',
  };
};

/**
 * Get user-friendly error message
 */
export const getUserFriendlyError = (error: any): string => {
  return formatError(error).userFriendly;
};

/**
 * Get actionable error message (includes guidance)
 */
export const getActionableError = (error: any): string => {
  const errorInfo = formatError(error);
  if (errorInfo.actionable) {
    return `${errorInfo.userFriendly} ${errorInfo.actionable}`;
  }
  return errorInfo.userFriendly;
};
