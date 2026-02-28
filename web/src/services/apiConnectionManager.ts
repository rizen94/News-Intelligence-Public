/**
 * Simplified API Connection Manager
 * Single axios instance with minimal interceptors
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import API_CONFIG, { getCurrentApiUrl } from '../config/apiConfig';
import { getCurrentDomain } from '../utils/domainHelper';
import errorHandler from './errorHandler';

class APIConnectionManager {
  private apiInstance: AxiosInstance;

  constructor() {
    // Create single axios instance
    this.apiInstance = axios.create({
      baseURL: getCurrentApiUrl(),
      timeout: API_CONFIG.timeout,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Setup minimal interceptors
    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor - only domain injection
    this.apiInstance.interceptors.request.use(
      (config) => {
        // Add domain to request if needed
        if (config.url?.includes('/api/v4/')) {
          const domain = getCurrentDomain();
          if (config.url && !config.url.includes(`/${domain}/`)) {
            const match = config.url.match(/\/api\/v4\/(.+)$/);
            if (match) {
              const pathAfterV4 = match[1];
              const firstSegment = pathAfterV4.split('/')[0];
              // Don't inject domain for system_monitoring, route_supervisor, or other global routes
              const globalRoutes = ['politics', 'finance', 'science-tech', 'system_monitoring', 'route_supervisor', 'watchlist', 'monitoring'];
              if (!globalRoutes.includes(firstSegment)) {
                config.url = `/api/v4/${domain}/${pathAfterV4}`;
              }
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

    // Response interceptor - only error handling
    this.apiInstance.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        // Simple error handling
        if (!error.response) {
          errorHandler.handleNetworkError(error, { url: error.config?.url });
        } else {
          errorHandler.handleApiError(error, { url: error.config?.url });
        }
        return Promise.reject(error);
      },
    );
  }

  public getApiInstance(): AxiosInstance {
    return this.apiInstance;
  }

  public async testConnection(): Promise<boolean> {
    try {
      const response = await axios.get(`${getCurrentApiUrl()}/api/v4/system_monitoring/health`, {
        timeout: 5000,
      });
      return response.status === 200;
    } catch {
      return false;
    }
  }

  // Simple connection state for components that need it
  public getConnectionState(): { isConnected: boolean } {
    // Return a simple state - components can call testConnection() for actual status
    return { isConnected: true }; // Optimistic - actual status requires testConnection()
  }

  // Cleanup method for App.tsx
  public cleanup(): void {
    // No cleanup needed in simplified version
  }
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
