/**
 * Simplified API Connection Manager
 * Single axios instance with minimal interceptors
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import API_CONFIG, {
  getCurrentApiUrl,
  getApiOrigin,
} from '../config/apiConfig';
import { getCurrentDomain, isRegistryDomainPathSegment } from '../utils/domainHelper';
import errorHandler from './errorHandler';

class APIConnectionManager {
  private apiInstance: AxiosInstance;
  // #region agent log
  private static _debugReqStart = new WeakMap<object, number>();
  private _emitApiDebug(payload: Record<string, unknown>): void {
    const body = {
      sessionId: 'c062dd',
      timestamp: Date.now(),
      ...payload,
    };
    fetch('http://127.0.0.1:7678/ingest/79eeed92-cd4a-41d4-872f-8f142138548b', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': 'c062dd',
      },
      body: JSON.stringify(body),
    }).catch(() => {});
  }
  // #endregion

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
    // Request interceptor - use current API URL every time, then domain injection
    this.apiInstance.interceptors.request.use(
      config => {
        // Always use current base URL (fixes stale value after settings change or late localStorage)
        // Add domain to request if needed; detect global (flat /api/...) routes
        if (config.url?.includes('/api/')) {
          const match = config.url.match(/\/api\/(.+)$/);
          const firstSegment = match ? match[1].split('/')[0] : '';
          /**
           * First path segment after /api/ that is NOT a registry domain key — keep URL flat
           * (no /api/{currentDomain}/ injection). Domain keys (politics, finance, …) are handled
           * separately via isRegistryDomainPathSegment.
           *
           * Add a segment here when the backend exposes a global namespace at /api/<segment>/...
           * (e.g. article dedup under /api/articles/..., intelligence hub under /api/intelligence/...).
           */
          const globalApiPrefixes = [
            'system_monitoring',
            'route_supervisor',
            'watchlist',
            'monitoring',
            'orchestrator',
            'context_centric',
            'entity_profiles',
            'contexts',
            'tracked_events',
            'claims',
            'pattern_discoveries',
            'processed_documents',
            'entity_dossiers',
            'entity_positions',
            'narrative_threads',
            'synthesis',
            'entities',
            'articles',
            'storylines',
            'intelligence',
            'public',
            'deduplication',
            'topics',
          ];
          const isGlobalRoute =
            globalApiPrefixes.includes(firstSegment) ||
            isRegistryDomainPathSegment(firstSegment);
          // Global routes (context_centric, entity_profiles, etc.) use origin-only base so path stays /api/...
          if (isGlobalRoute) {
            const origin = getApiOrigin();
            config.baseURL = origin !== '' ? origin : getCurrentApiUrl();
          } else {
            config.baseURL = getCurrentApiUrl();
            const domain = getCurrentDomain();
            if (config.url && !config.url.includes(`/${domain}/`)) {
              const pathAfterApi = match ? match[1] : '';
              if (pathAfterApi) config.url = `/api/${domain}/${pathAfterApi}`;
            }
          }
        } else {
          config.baseURL = getCurrentApiUrl();
        }
        // #region agent log
        if (config.url) {
          APIConnectionManager._debugReqStart.set(config, Date.now());
          this._emitApiDebug({
            hypothesisId: 'C',
            location: 'apiConnectionManager.ts:request',
            message: 'api_request_start',
            runId: 'frontend-audit',
            data: {
              method: (config.method || 'get').toUpperCase(),
              url: config.url,
              baseURL: config.baseURL || '',
              timeout: config.timeout ?? API_CONFIG.timeout,
            },
          });
        }
        // #endregion
        return config;
      },
      error => {
        errorHandler.handleApiError(error, { type: 'request_error' });
        return Promise.reject(error);
      }
    );

    // Response interceptor - only error handling
    this.apiInstance.interceptors.response.use(
      response => {
        // #region agent log
        const started = APIConnectionManager._debugReqStart.get(response.config);
        const durationMs =
          typeof started === 'number' ? Date.now() - started : null;
        this._emitApiDebug({
          hypothesisId: durationMs != null && durationMs > 2000 ? 'A' : 'E',
          location: 'apiConnectionManager.ts:response',
          message: 'api_request_ok',
          runId: 'frontend-audit',
          data: {
            method: (response.config.method || 'get').toUpperCase(),
            url: response.config.url || '',
            status: response.status,
            durationMs,
          },
        });
        // #endregion
        return response;
      },
      (error: AxiosError) => {
        // #region agent log
        const cfg = error.config;
        const started = cfg ? APIConnectionManager._debugReqStart.get(cfg) : undefined;
        const durationMs =
          typeof started === 'number' ? Date.now() - started : null;
        this._emitApiDebug({
          hypothesisId: error.response ? 'B' : 'D',
          location: 'apiConnectionManager.ts:response_error',
          message: 'api_request_fail',
          runId: 'frontend-audit',
          data: {
            method: (cfg?.method || 'get').toUpperCase(),
            url: cfg?.url || '',
            status: error.response?.status ?? null,
            code: error.code || null,
            durationMs,
            isTimeout: error.code === 'ECONNABORTED',
            detail:
              typeof error.response?.data === 'object'
                ? JSON.stringify(error.response?.data).slice(0, 200)
                : String(error.message || '').slice(0, 200),
          },
        });
        // #endregion
        // Simple error handling
        if (!error.response) {
          errorHandler.handleNetworkError(error, { url: error.config?.url });
        } else {
          errorHandler.handleApiError(error, { url: error.config?.url });
        }
        return Promise.reject(error);
      }
    );
  }

  public getApiInstance(): AxiosInstance {
    return this.apiInstance;
  }

  public async testConnection(): Promise<boolean> {
    try {
      // Use same base as request interceptor: origin for global-style routes so path stays /api/...
      const base = getCurrentApiUrl();
      const origin = getApiOrigin();
      const healthBase = origin !== '' ? origin : base;
      const healthUrl = !healthBase
        ? '/api/system_monitoring/health'
        : `${healthBase.replace(/\/$/, '')}/api/system_monitoring/health`;
      const response = await axios.get(healthUrl, { timeout: 15000 });
      return response.status === 200;
    } catch (err: unknown) {
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
