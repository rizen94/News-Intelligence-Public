/**
 * API Connection Manager
 * Manages API connection health, retries, and persistence
 */

import axios, { AxiosInstance, AxiosError, AxiosRequestConfig } from 'axios';
import API_CONFIG, { HEALTH_CHECK_ENDPOINT, getCurrentApiUrl, setApiBaseUrl } from '../config/apiConfig';
import { getCurrentDomain } from '../utils/domainHelper';
import loggingService from './loggingService';
import errorHandler from './errorHandler';

interface ConnectionState {
  isConnected: boolean;
  lastHealthCheck: number | null;
  consecutiveFailures: number;
  apiUrl: string;
}

class APIConnectionManager {
  private apiInstance: AxiosInstance;
  private connectionState: ConnectionState;
  private healthCheckInterval: number | null = null;
  private retryQueue: Array<() => Promise<any>> = [];

  constructor() {
    this.connectionState = {
      isConnected: false,
      lastHealthCheck: null,
      consecutiveFailures: 0,
      apiUrl: getCurrentApiUrl(),
    };

    // Create axios instance with configuration
    this.apiInstance = axios.create({
      baseURL: this.connectionState.apiUrl,
      timeout: API_CONFIG.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Setup interceptors
    this.setupInterceptors();

    // Start health checking
    this.startHealthCheck();

    // Listen for API URL changes
    if (typeof window !== 'undefined') {
      window.addEventListener('apiUrlChanged', this.handleApiUrlChange);
    }
  }

  private setupInterceptors(): void {
    // Request interceptor
    this.apiInstance.interceptors.request.use(
      (config) => {
        // Track request start time
        (config as any).metadata = { startTime: Date.now() };

        // Add domain to request if not present
        if (!config.url?.includes('/api/v4/')) {
          return config;
        }

        // Ensure domain is in URL
        const domain = getCurrentDomain();
        if (config.url && !config.url.includes(`/${domain}/`)) {
          // Extract path after /api/v4/
          const match = config.url.match(/\/api\/v4\/(.+)$/);
          if (match) {
            const pathAfterV4 = match[1];
            // Check if domain is already in path
            if (!['politics', 'finance', 'science-tech'].includes(pathAfterV4.split('/')[0])) {
              config.url = `/api/v4/${domain}/${pathAfterV4}`;
            }
          }
        }

        return config;
      },
      (error) => {
        errorHandler.handleApiError(error, { type: 'request_error' });
        return Promise.reject(error);
      },
    );

    // Response interceptor with retry logic
    this.apiInstance.interceptors.response.use(
      (response) => {
        // Reset failure count on success
        this.connectionState.consecutiveFailures = 0;
        this.connectionState.isConnected = true;
        this.connectionState.lastHealthCheck = Date.now();

        // Log successful API call
        const config = response.config as AxiosRequestConfig & { 
          metadata?: { startTime?: number };
        };
        const duration = Date.now() - (config.metadata?.startTime || Date.now());
        loggingService.logApiCall(
          config.method?.toUpperCase() || 'GET',
          config.url || 'unknown',
          response.status,
          duration
        );

        return response;
      },
      async(error: AxiosError) => {
        const config = error.config as AxiosRequestConfig & { 
          _retry?: boolean; 
          _retryCount?: number;
          metadata?: { startTime?: number };
        };
        const startTime = config.metadata?.startTime || Date.now();
        const duration = Date.now() - startTime;

        // Log API call with error
        loggingService.logApiCall(
          config.method?.toUpperCase() || 'UNKNOWN',
          config.url || 'unknown',
          error.response?.status || 0,
          duration,
          error
        );

        // Don't retry if already retried or if it's a non-retryable error
        if (config._retry || !this.shouldRetry(error)) {
          this.connectionState.consecutiveFailures += 1;
          if (this.connectionState.consecutiveFailures >= 3) {
            this.connectionState.isConnected = false;
            loggingService.warn('API connection marked as disconnected after 3 consecutive failures');
          }
          
          // Handle error based on type
          if (!error.response) {
            errorHandler.handleNetworkError(error, { url: config.url });
          } else {
            errorHandler.handleApiError(error, { url: config.url });
          }
          
          return Promise.reject(error);
        }

        // Set retry flag
        config._retry = true;
        config._retryCount = (config._retryCount || 0) + 1;

        loggingService.info(`Retrying API call: ${config.method} ${config.url} (attempt ${config._retryCount})`);

        // Wait before retrying
        await this.delay(API_CONFIG.retryDelay * config._retryCount);

        // Retry the request
        return this.apiInstance.request(config);
      },
    );
  }

  private shouldRetry(error: AxiosError): boolean {
    if (!error.config) {
      return false;
    }

    // Don't retry if max retries reached
    const retryCount = (error.config as any)._retryCount || 0;
    if (retryCount >= API_CONFIG.retryAttempts) {
      return false;
    }

    // Retry on network errors or 5xx errors
    if (!error.response) {
      return true; // Network error
    }

    const status = error.response.status;
    return status >= 500 && status < 600; // Server errors
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private async performHealthCheck(): Promise<boolean> {
    const startTime = Date.now();
    try {
      const response = await axios.get(`${this.connectionState.apiUrl}${HEALTH_CHECK_ENDPOINT}`, {
        timeout: API_CONFIG.connectionTimeout,
      });

      if (response.status === 200) {
        this.connectionState.isConnected = true;
        this.connectionState.consecutiveFailures = 0;
        this.connectionState.lastHealthCheck = Date.now();
        
        const duration = Date.now() - startTime;
        loggingService.debug('API health check successful', { duration });
        return true;
      }
    } catch (error: any) {
      const duration = Date.now() - startTime;
      loggingService.warn('API health check failed', {
        error: error.message,
        duration,
        consecutiveFailures: this.connectionState.consecutiveFailures + 1,
      });
      
      this.connectionState.consecutiveFailures += 1;
      if (this.connectionState.consecutiveFailures >= 3) {
        this.connectionState.isConnected = false;
        loggingService.error('API connection lost after multiple health check failures');
      }
    }

    this.connectionState.lastHealthCheck = Date.now();
    return false;
  }

  private startHealthCheck(): void {
    // Perform initial health check
    this.performHealthCheck();

    // Set up periodic health checks
    this.healthCheckInterval = window.setInterval(() => {
      this.performHealthCheck();
    }, API_CONFIG.healthCheckInterval);
  }

  private handleApiUrlChange = (event: CustomEvent): void => {
    const newUrl = event.detail?.url;
    if (newUrl && newUrl !== this.connectionState.apiUrl) {
      this.connectionState.apiUrl = newUrl;
      this.apiInstance.defaults.baseURL = newUrl;
      // Reset connection state
      this.connectionState.isConnected = false;
      this.connectionState.consecutiveFailures = 0;
      // Perform immediate health check
      this.performHealthCheck();
    }
  };

  public getApiInstance(): AxiosInstance {
    return this.apiInstance;
  }

  public getConnectionState(): ConnectionState {
    return { ...this.connectionState };
  }

  public isConnected(): boolean {
    return this.connectionState.isConnected;
  }

  public async testConnection(): Promise<boolean> {
    return await this.performHealthCheck();
  }

  public updateApiUrl(url: string): void {
    setApiBaseUrl(url);
  }

  public cleanup = (): void => {
    if (this.healthCheckInterval) {
      window.clearInterval(this.healthCheckInterval);
      this.healthCheckInterval = null;
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('apiUrlChanged', this.handleApiUrlChange);
    }
  };
}

// Singleton instance
let connectionManagerInstance: APIConnectionManager | null = null;

export const getAPIConnectionManager = (): APIConnectionManager => {
  if (!connectionManagerInstance) {
    connectionManagerInstance = new APIConnectionManager();
  }
  return connectionManagerInstance;
};

export default getAPIConnectionManager;

