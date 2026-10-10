/**
 * API Configuration
 * Centralized API configuration with environment variable support and persistence.
 *
 * Connection flow:
 * - Default (no VITE_API_URL, no localStorage): base URL is ''. Requests are relative
 *   (e.g. /api/...). Production public site: https://news-intelligence-ag.duckdns.org
 *   (same-origin /api via nginx). In Vite dev, /api proxies to localhost:8000.
 * - If you set an API URL (e.g. http://host:8000 or with a path): it is
 *   stored in localStorage. Domain-prefixed routes use that full base; context-centric
 *   (flat /api/...) routes use origin only (getApiOrigin()) so paths stay /api/...
 *   and do not double-prefix (e.g. /api/... stays /api/...).
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

/** API origin only (no path). Use for context-centric and other flat /api/... routes so paths like /api/tracked_events/... resolve correctly. */
export const getApiOrigin = (): string => {
  const base = getApiBaseUrl();
  if (!base || base === '') return '';
  try {
    const u = new URL(base);
    return u.origin;
  } catch {
    return base;
  }
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
export const HEALTH_CHECK_ENDPOINT = '/api/system_monitoring/health';

export default API_CONFIG;
