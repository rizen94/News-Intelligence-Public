/**
 * API Configuration
 * Centralized API configuration with environment variable support and persistence
 */

// Get API base URL from environment or use default
const getApiBaseUrl = (): string => {
  // Check Vite environment variable first
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL;
  }

  // Check localStorage for persisted API URL
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('news_intelligence_api_url');
    if (stored) {
      return stored;
    }
  }

  // Default: use relative URL so Vite proxy handles it (works for localhost or network access)
  return '';
};

// Get API timeout from environment or use default
const getApiTimeout = (): number => {
  const timeout = import.meta.env.VITE_API_TIMEOUT;
  return timeout ? parseInt(timeout, 10) : 30000;
};

// Persist API URL to localStorage
export const setApiBaseUrl = (url: string): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('news_intelligence_api_url', url);
    // Trigger event so axios instance can update
    window.dispatchEvent(new CustomEvent('apiUrlChanged', { detail: { url } }));
  }
};

// Get current API base URL
export const getCurrentApiUrl = (): string => {
  return getApiBaseUrl();
};

// API Configuration
export const API_CONFIG = {
  baseURL: getApiBaseUrl(),
  timeout: getApiTimeout(),
  retryAttempts: 3,
  retryDelay: 1000, // 1 second
  // healthCheckInterval removed - no automatic health checks
  connectionTimeout: 5000, // 5 seconds for initial connection
};

// Health check endpoint
export const HEALTH_CHECK_ENDPOINT = '/api/v4/system_monitoring/health';

export default API_CONFIG;

